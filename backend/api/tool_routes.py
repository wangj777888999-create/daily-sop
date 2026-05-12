from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from typing import Optional
from datetime import date
from urllib.parse import quote
import io
import json
import os

from tools.daily_checkin import preview_files, process_files
from tools.db import (
    save_checkin_records, get_batches, get_available_months, get_checkin_by_month,
    save_monthly_analysis, get_monthly_analyses,
)
from tools.campus_monthly import preview_monthly, process_monthly, UPLOAD_DIR

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

    batch_date = batch["batch_date"]
    year, month, day = batch_date.split("-")

    records = get_checkin_by_month(int(year), int(month))
    day_records = [r for r in records if r["check_date"] == batch_date]
    if not day_records:
        raise HTTPException(status_code=404, detail="该批次无数据")

    import pandas as pd
    df = pd.DataFrame(day_records)
    # Reorder for export
    export_cols = ['department', 'school_name', 'course_type', 'course_name',
                   'coach_name', 'course_date', 'start_time', 'end_time',
                   'sign_in_time', 'sign_out_time', 'sign_status',
                   'actual_count', 'expected_count', 'confirmed_revenue']
    rename_map = {
        'department': '部门', 'school_name': '学校名称', 'course_type': '课程类型',
        'course_name': '课程名称', 'coach_name': '教练姓名', 'course_date': '课程日期',
        'start_time': '开课时间', 'end_time': '下课时间', 'sign_in_time': '签到时间',
        'sign_out_time': '签退时间', 'sign_status': '签到状态',
        'actual_count': '实际上课人次', 'expected_count': '课程应到人次',
        'confirmed_revenue': '确认收入',
    }
    df = df[[c for c in export_cols if c in df.columns]].rename(columns=rename_map)

    from tools.daily_checkin import _generate_excel
    excel_bytes = _generate_excel(df)

    filename = f"{batch_date}_教练签到分析.xlsx"
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/tools/daily-checkin/history")
async def daily_checkin_history(limit: int = Query(50, ge=1, le=200)):
    return get_batches(limit)


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
