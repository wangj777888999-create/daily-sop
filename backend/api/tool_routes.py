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
    get_checkin_by_date, update_checkin_record, delete_checkin_record,
    save_monthly_analysis, get_monthly_analyses, delete_batch, delete_monthly_analysis,
    save_consolidation, get_consolidation, update_consolidation_status,
    get_consolidations, delete_consolidation,
)
from tools.campus_monthly import preview_monthly, process_monthly, UPLOAD_DIR
from tools.offcampus_monthly import preview_offcampus, process_offcampus
from tools.offcampus_monthly import UPLOAD_DIR as OFFCAMPUS_UPLOAD_DIR
from tools.checkin_consolidation import (
    load_month_records, save_consolidation_data, load_consolidation_data, export_excel,
)
from tools.course_types import (
    load_all as ct_load_all, add_record as ct_add, update_record as ct_update,
    delete_record as ct_delete, import_from_excel as ct_import, export_to_excel as ct_export,
    get_type_options as ct_options,
)

CHECKIN_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "checkin_output")
CONSOLIDATION_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "consolidation_output")

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
        "unmapped_courses": result.get("unmapped_courses", []),
    }


@router.get("/tools/daily-checkin/download/{batch_id}")
async def daily_checkin_download(batch_id: int):
    batches = get_batches(limit=100)
    batch = next((b for b in batches if b["id"] == batch_id), None)
    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在")

    # Regenerate Excel from current SQLite data (reflects user edits)
    records = get_checkin_by_date(batch["batch_date"])
    if not records:
        raise HTTPException(status_code=404, detail="该日期无签到数据")

    import pandas as pd
    from tools.daily_checkin import _generate_excel

    # Map SQLite columns → Chinese column names expected by _generate_excel
    col_map = {
        "department": "部门", "school_name": "学校名称", "course_type": "课程类型",
        "course_name": "课程名称", "coach_name": "教练姓名", "course_date": "课程日期",
        "start_time": "开课时间", "end_time": "下课时间", "sign_in_time": "签到时间",
        "sign_out_time": "签退时间", "sign_status": "签到状态",
        "actual_count": "实际上课人次", "expected_count": "课程应到人次",
        "confirmed_revenue": "确认收入", "remark": "备注",
    }
    df = pd.DataFrame(records)
    df = df.rename(columns=col_map)
    df = df[[c for c in col_map.values() if c in df.columns]]

    excel_bytes = _generate_excel(df)

    output_filename = batch.get("output_filename", f"{batch['batch_date']}_教练签到.xlsx")
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


# ──────────────────── Daily Check-in Record CRUD ────────────────────

@router.get("/tools/daily-checkin/records/{check_date}")
async def daily_checkin_records(check_date: str):
    records = get_checkin_by_date(check_date)
    return {"check_date": check_date, "records": records, "count": len(records)}


@router.put("/tools/daily-checkin/record/{record_id}")
async def daily_checkin_update_record(record_id: int, body: dict):
    success = update_checkin_record(record_id, body)
    if not success:
        raise HTTPException(status_code=404, detail="记录不存在或无有效更新字段")
    return {"updated": True, "id": record_id}


@router.delete("/tools/daily-checkin/record/{record_id}")
async def daily_checkin_delete_record(record_id: int):
    info = delete_checkin_record(record_id)
    if not info:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"deleted": True, "id": record_id, "record": info}


# ──────────────────── Campus Monthly Analysis ────────────────────

@router.post("/tools/campus-monthly/preview")
async def campus_monthly_preview(
    year: int = Form(...),
    month: int = Form(...),
):
    consolidation = get_consolidation(year, month)
    if consolidation and consolidation["status"] == "confirmed":
        records = load_consolidation_data(consolidation["filename"])
    else:
        records = get_checkin_by_month(year, month)
    preview = preview_monthly(year, month, records)
    preview["year"] = year
    preview["month"] = month
    preview["data_source"] = "consolidated" if (consolidation and consolidation["status"] == "confirmed") else "raw"
    return preview


@router.post("/tools/campus-monthly/process")
async def campus_monthly_process(
    year: int = Form(...),
    month: int = Form(...),
    finance_file: Optional[UploadFile] = File(None),
    course_type_file: Optional[UploadFile] = File(None),
    refund_file: Optional[UploadFile] = File(None),
):
    consolidation = get_consolidation(year, month)
    if consolidation and consolidation["status"] == "confirmed":
        records = load_consolidation_data(consolidation["filename"])
    else:
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
        "unmapped_courses": result.get("unmapped_courses", []),
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


# ──────────────────── Check-in Consolidation ────────────────────

@router.post("/tools/checkin-consolidation/load")
async def checkin_consolidation_load(year: int = Form(...), month: int = Form(...)):
    # 优先加载已整合的 JSON，保留补签等修改；无整合时从 SQLite 加载原始数据
    consolidation = get_consolidation(year, month)
    if consolidation and consolidation.get("filename"):
        try:
            records = load_consolidation_data(consolidation["filename"])
            transformed = load_month_records(records)
            return {
                "records": transformed,
                "count": len(transformed),
                "from_consolidation": True,
                "status": consolidation["status"],
                "consolidation_id": consolidation["id"],
            }
        except FileNotFoundError:
            pass  # 文件丢失，回退到 SQLite

    records = get_checkin_by_month(year, month)
    if not records:
        raise HTTPException(status_code=400, detail=f"{year}年{month}月无签到数据")
    transformed = load_month_records(records)
    return {"records": transformed, "count": len(transformed), "from_consolidation": False}


@router.post("/tools/checkin-consolidation/save")
async def checkin_consolidation_save(
    year: int = Form(...),
    month: int = Form(...),
    records: str = Form(...),
):
    parsed_records = json.loads(records)
    result = save_consolidation_data(year, month, parsed_records)
    consolidation_id = save_consolidation(
        year, month, result["record_count"], result["filename"], status="draft"
    )

    # 查回当前记录确认状态
    consolidation = get_consolidation(year, month)
    return {
        "id": consolidation["id"],
        "record_count": result["record_count"],
        "status": consolidation["status"],
    }


@router.post("/tools/checkin-consolidation/confirm")
async def checkin_consolidation_confirm(id: int = Form(...)):
    success = update_consolidation_status(id, "confirmed")
    if not success:
        raise HTTPException(status_code=404, detail="整合记录不存在")
    return {"confirmed": True, "id": id}


@router.post("/tools/checkin-consolidation/unconfirm")
async def checkin_consolidation_unconfirm(id: int = Form(...)):
    success = update_consolidation_status(id, "draft")
    if not success:
        raise HTTPException(status_code=404, detail="整合记录不存在")
    return {"unconfirmed": True, "id": id, "status": "draft"}


@router.get("/tools/checkin-consolidation/status/{year}/{month}")
async def checkin_consolidation_status(year: int, month: int):
    consolidation = get_consolidation(year, month)
    if not consolidation:
        return {"exists": False}
    return {"exists": True, **consolidation}


@router.get("/tools/checkin-consolidation/history")
async def checkin_consolidation_history(limit: int = Query(50, ge=1, le=200)):
    return get_consolidations(limit)


@router.get("/tools/checkin-consolidation/download/{consolidation_id}")
async def checkin_consolidation_download(consolidation_id: int):
    consolidations = get_consolidations(limit=200)
    item = next((c for c in consolidations if c["id"] == consolidation_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")

    filename = item.get("filename", "")
    if not filename:
        raise HTTPException(status_code=404, detail="该记录无生成文件")

    filepath = os.path.join(CONSOLIDATION_OUTPUT_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="文件不存在，请重新整合")

    records = load_consolidation_data(filename)
    excel_bytes = export_excel(records)
    download_name = f"{item['year']}年{item['month']}月签到整合.xlsx"

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(download_name)}"},
    )


@router.delete("/tools/checkin-consolidation/{consolidation_id}")
async def checkin_consolidation_delete(consolidation_id: int):
    info = delete_consolidation(consolidation_id)
    if not info:
        raise HTTPException(status_code=404, detail="记录不存在")
    filename = info.get("filename", "")
    if filename:
        filepath = os.path.join(CONSOLIDATION_OUTPUT_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
    return {"deleted": True, "id": consolidation_id}


# ──────────────────── Off-campus Monthly Analysis ────────────────────

@router.post("/tools/offcampus-monthly/preview")
async def offcampus_monthly_preview(
    skjl_file: UploadFile = File(...),
    cw_file: UploadFile = File(...),
):
    skjl_bytes = await skjl_file.read()
    cw_bytes = await cw_file.read()
    try:
        return preview_offcampus(skjl_bytes, cw_bytes)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败: {str(e)}")


@router.post("/tools/offcampus-monthly/process")
async def offcampus_monthly_process(
    skjl_file: UploadFile = File(...),
    xwksf_file: UploadFile = File(...),
    cw_file: UploadFile = File(...),
    cdf_file: UploadFile = File(...),
    last_month_file: Optional[UploadFile] = File(None),
):
    skjl_bytes = await skjl_file.read()
    xwksf_bytes = await xwksf_file.read()
    cw_bytes = await cw_file.read()
    cdf_bytes = await cdf_file.read()
    last_month_bytes = await last_month_file.read() if last_month_file and last_month_file.filename else None

    try:
        result = process_offcampus(skjl_bytes, xwksf_bytes, cw_bytes, cdf_bytes, last_month_bytes)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"处理失败: {str(e)}")

    # 保存 Excel 到磁盘
    now_str = date.today().strftime("%Y%m%d")
    filename = f"{now_str}_校外分析.xlsx"
    os.makedirs(OFFCAMPUS_UPLOAD_DIR, exist_ok=True)
    filepath = os.path.join(OFFCAMPUS_UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(result["excel_bytes"])

    summary = result["summary"]
    analysis_id = save_monthly_analysis({
        "year": date.today().year,
        "month": date.today().month,
        "analysis_type": "offcampus",
        "filename": filename,
        "record_count": summary["total_records"],
        "department_count": summary["campus_count"],
        "coach_count": summary["coach_count"],
        "sheets": json.dumps(result["sheets"], ensure_ascii=False),
    })

    return {
        "id": analysis_id,
        "filename": filename,
        "sheets": result["sheets"],
        "summary": summary,
    }


@router.get("/tools/offcampus-monthly/download/{analysis_id}")
async def offcampus_monthly_download(analysis_id: int):
    analyses = get_monthly_analyses("offcampus", limit=200)
    analysis = next((a for a in analyses if a["id"] == analysis_id), None)
    if not analysis:
        raise HTTPException(status_code=404, detail="分析记录不存在")

    filepath = os.path.join(OFFCAMPUS_UPLOAD_DIR, analysis["filename"])
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="文件不存在，请重新生成")

    with open(filepath, "rb") as f:
        excel_bytes = f.read()

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(analysis['filename'])}"},
    )


@router.get("/tools/offcampus-monthly/history")
async def offcampus_monthly_history(limit: int = Query(50, ge=1, le=200)):
    return get_monthly_analyses("offcampus", limit)


@router.delete("/tools/offcampus-monthly/analysis/{analysis_id}")
async def offcampus_monthly_delete(analysis_id: int):
    analysis = delete_monthly_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="分析记录不存在")

    filename = analysis.get("filename", "")
    if filename:
        filepath = os.path.join(OFFCAMPUS_UPLOAD_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)

    return {"deleted": True, "analysis_id": analysis_id}


# ──────────────────── Course Types Management ────────────────────

@router.get("/tools/course-types")
async def course_types_list():
    records = ct_load_all()
    return {"records": records, "total": len(records), "type_options": ct_options()}


@router.post("/tools/course-types")
async def course_types_add(course_name: str = Form(...), course_type: str = Form(...)):
    try:
        record = ct_add(course_name, course_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return record


@router.put("/tools/course-types/{index}")
async def course_types_update(index: int, course_type: str = Form(...)):
    try:
        record = ct_update(index, course_type)
    except IndexError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return record


@router.delete("/tools/course-types/{index}")
async def course_types_delete(index: int):
    try:
        removed = ct_delete(index)
    except IndexError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"deleted": True, "record": removed}


@router.post("/tools/course-types/import")
async def course_types_import(file: UploadFile = File(...)):
    data = await file.read()
    try:
        result = ct_import(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.get("/tools/course-types/export")
async def course_types_export():
    excel_bytes = ct_export()
    filename = "课程类型对照表.xlsx"
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
