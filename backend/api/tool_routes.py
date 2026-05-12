from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from typing import Optional
from datetime import date
from urllib.parse import quote
import io
import json
import os

from tools.daily_checkin import preview_files, process_files, _generate_excel
from tools.db import (
    save_checkin_records, get_batches, get_available_months, get_checkin_by_month,
    save_monthly_analysis, get_monthly_analyses, delete_batch, delete_monthly_analysis,
)
from tools.campus_monthly import preview_monthly, process_monthly, UPLOAD_DIR

CHECKIN_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "checkin_output")

router = APIRouter()


# ──────────────────── Daily Check-in ────────────────────

@router.post("/tools/daily-checkin/preview")
async def daily_checkin_preview(
    coach_file: UploadFile = File(...),
    finance_file: UploadFile = File(...),
):
    coach_bytes = await coach_file.read()
    finance_bytes = await finance_file.read()
    try:
        preview = preview_files(coach_bytes, finance_bytes)
        return preview
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败: {str(e)}")


@router.post("/tools/daily-checkin/process")
async def daily_checkin_process(
    coach_file: UploadFile = File(...),
    finance_file: UploadFile = File(...),
    check_date: str = Form(""),
):
    coach_bytes = await coach_file.read()
    finance_bytes = await finance_file.read()

    if not check_date:
        check_date = str(date.today())

    try:
        result = process_files(coach_bytes, finance_bytes, check_date)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"处理失败: {str(e)}")

    batch_info = {
        "batch_date": check_date,
        "coach_file": coach_file.filename or "",
        "finance_file": finance_file.filename or "",
    }

    # 保存 Excel 到磁盘：{check_date}_教练签到.xlsx，同日期覆盖
    os.makedirs(CHECKIN_OUTPUT_DIR, exist_ok=True)
    output_filename = f"{check_date}_教练签到.xlsx"
    output_path = os.path.join(CHECKIN_OUTPUT_DIR, output_filename)
    with open(output_path, "wb") as f:
        f.write(result["excel_bytes"])
    batch_info["output_filename"] = output_filename

    batch_id = save_checkin_records(result["records"], batch_info)

    return {
        "batch_id": batch_id,
        "record_count": len(result["records"]),
        "check_date": check_date,
        "summary": result["summary"],
    }


@router.get("/tools/daily-checkin/download/{batch_id}")
async def daily_checkin_download(batch_id: int):
    batches = get_batches(limit=100)
    batch = next((b for b in batches if b["id"] == batch_id), None)
    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在")

    output_filename = batch.get("output_filename", "")
    if not output_filename:
        raise HTTPException(status_code=404, detail="该批次无生成文件")

    filepath = os.path.join(CHECKIN_OUTPUT_DIR, output_filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="文件不存在，请重新处理")

    with open(filepath, "rb") as f:
        excel_bytes = f.read()

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(output_filename)}"},
    )


@router.get("/tools/daily-checkin/history")
async def daily_checkin_history(limit: int = Query(50, ge=1, le=200)):
    return get_batches(limit)


@router.delete("/tools/daily-checkin/batch/{batch_id}")
async def daily_checkin_delete_batch(batch_id: int):
    batch = delete_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在")

    # 删除磁盘文件
    output_filename = batch.get("output_filename", "")
    if output_filename:
        filepath = os.path.join(CHECKIN_OUTPUT_DIR, output_filename)
        if os.path.exists(filepath):
            os.remove(filepath)

    return {"deleted": True, "batch_id": batch_id}


@router.get("/tools/daily-checkin/available-months")
async def daily_checkin_available_months():
    return get_available_months()


# ──────────────────── Campus Monthly Analysis ────────────────────

@router.post("/tools/campus-monthly/preview")
async def campus_monthly_preview(
    year: int = Form(...),
    month: int = Form(...),
):
    records = get_checkin_by_month(year, month)
    preview = preview_monthly(year, month, records)
    preview["year"] = year
    preview["month"] = month
    return preview


@router.post("/tools/campus-monthly/process")
async def campus_monthly_process(
    year: int = Form(...),
    month: int = Form(...),
    finance_file: Optional[UploadFile] = File(None),
    course_type_file: Optional[UploadFile] = File(None),
    refund_file: Optional[UploadFile] = File(None),
):
    records = get_checkin_by_month(year, month)
    if not records:
        raise HTTPException(status_code=400, detail=f"{year}年{month}月无签到数据，请先使用每日签到工具积累数据")

    finance_bytes = await finance_file.read() if finance_file and finance_file.filename else None
    course_type_bytes = await course_type_file.read() if course_type_file and course_type_file.filename else None
    refund_bytes = await refund_file.read() if refund_file and refund_file.filename else None

    try:
        result = process_monthly(year, month, records, finance_bytes, course_type_bytes, refund_bytes)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"处理失败: {str(e)}")

    analysis_id = save_monthly_analysis({
        "year": year, "month": month,
        "analysis_type": "campus",
        "filename": result["filename"],
        "record_count": result["record_count"],
        "department_count": result["department_count"],
        "coach_count": result["coach_count"],
        "sheets": json.dumps(result["sheets"], ensure_ascii=False),
    })

    return {
        "id": analysis_id,
        "filename": result["filename"],
        "sheets": result["sheets"],
        "record_count": result["record_count"],
        "department_count": result["department_count"],
        "coach_count": result["coach_count"],
    }


@router.get("/tools/campus-monthly/download/{analysis_id}")
async def campus_monthly_download(analysis_id: int):
    analyses = get_monthly_analyses("campus", limit=200)
    analysis = next((a for a in analyses if a["id"] == analysis_id), None)
    if not analysis:
        raise HTTPException(status_code=404, detail="分析记录不存在")

    filepath = os.path.join(UPLOAD_DIR, analysis["filename"])
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="文件不存在，请重新生成")

    with open(filepath, "rb") as f:
        excel_bytes = f.read()

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(analysis['filename'])}"},
    )


@router.get("/tools/campus-monthly/history")
async def campus_monthly_history(limit: int = Query(50, ge=1, le=200)):
    return get_monthly_analyses("campus", limit)


@router.delete("/tools/campus-monthly/analysis/{analysis_id}")
async def campus_monthly_delete(analysis_id: int):
    analysis = delete_monthly_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="分析记录不存在")

    # 删除磁盘文件
    filename = analysis.get("filename", "")
    if filename:
        filepath = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)

    return {"deleted": True, "analysis_id": analysis_id}
