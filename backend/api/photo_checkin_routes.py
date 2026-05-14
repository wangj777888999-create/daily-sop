"""
photo_checkin_routes.py
照片人数核对 API 路由（独立文件，不影响 tool_routes.py）
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from typing import Optional, List
import json
import httpx

from tools.photo_checkin import detect_multiple, DEFAULT_FILTER_CONFIG, parse_sessions_from_excel
from tools.db import (
    save_photo_record,
    update_photo_record,
    get_photo_records_by_checkin,
    get_photo_records_by_date,
)

router = APIRouter()

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
MAX_FILE_SIZE_MB = 20


# ──────────────────── 解析月度核对表 ────────────────────

@router.post("/tools/photo-checkin/parse-sessions")
async def parse_sessions(table_file: UploadFile = File(...)):
    """
    上传月底核对表 Excel，解析返回课程行列表。
    前端用这份列表让用户选择照片对应哪一行。
    """
    content = await table_file.read()
    try:
        sessions = parse_sessions_from_excel(content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败：{e}")

    return {
        "filename": table_file.filename,
        "session_count": len(sessions),
        "sessions": sessions,
    }


# ──────────────────── 上传照片 + 推理 ────────────────────

@router.post("/tools/photo-checkin/detect")
async def detect_photos(
    photos: List[UploadFile] = File(...),
    row_index: Optional[int] = Form(None),
    filter_config_json: Optional[str] = Form(None),
):
    """
    接收照片列表，执行 YOLO 推理，返回识别结果（不写库）。
    row_index 对应核对表中的行号，用于前端关联比对。
    """
    if not photos:
        raise HTTPException(status_code=400, detail="未上传任何照片")
    if len(photos) > 10:
        raise HTTPException(status_code=400, detail="单次最多上传 10 张照片")

    filter_config = DEFAULT_FILTER_CONFIG.copy()
    if filter_config_json:
        try:
            filter_config.update(json.loads(filter_config_json))
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="filter_config_json 格式错误")

    images = []
    for photo in photos:
        ext = "." + (photo.filename or "").rsplit(".", 1)[-1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的图片格式 {ext}，仅支持 {ALLOWED_EXTENSIONS}",
            )
        content = await photo.read()
        if len(content) > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail=f"图片 {photo.filename} 超过 {MAX_FILE_SIZE_MB}MB 限制",
            )
        images.append((photo.filename or f"photo_{len(images)}.jpg", content))

    try:
        results = detect_multiple(images, filter_config)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return {
        "row_index": row_index,
        "photo_count": len(results),
        "results": results,
    }


# ──────────────────── 确认保存 ────────────────────

@router.post("/tools/photo-checkin/confirm")
async def confirm_records(body: dict):
    """
    将推理结果写入 photo_checkin_records 表。
    body: {
      "checkin_id": int | null,   # 可选，保留兼容字段
      "records": [{ filename, detected_count, raw_count, confidence_avg, filter_config }, ...]
    }
    """
    checkin_id = body.get("checkin_id")
    records = body.get("records", [])
    if not records:
        raise HTTPException(status_code=400, detail="records 不能为空")

    saved_ids = []
    for rec in records:
        new_id = save_photo_record(
            checkin_id=checkin_id,
            photo_filename=rec.get("filename", "unknown"),
            detected_count=rec.get("detected_count", 0),
            raw_count=rec.get("raw_count", 0),
            confidence_avg=rec.get("confidence_avg", 0.0),
            filter_config=rec.get("filter_config", DEFAULT_FILTER_CONFIG),
            status="confirmed",
        )
        saved_ids.append(new_id)

    return {"saved": len(saved_ids), "ids": saved_ids}


# ──────────────────── 人工修正 ────────────────────

@router.patch("/tools/photo-checkin/records/{record_id}")
async def patch_record(record_id: int, body: dict):
    manual_count = body.get("manual_count")
    note = body.get("note", "")
    status = body.get("status", "confirmed")
    if status not in ("confirmed", "flagged", "pending"):
        raise HTTPException(status_code=400, detail="status 无效")
    ok = update_photo_record(record_id, manual_count, note, status)
    return {"success": ok}


# ──────────────────── 查询历史 ────────────────────

@router.get("/tools/photo-checkin/records")
async def get_records(
    date: Optional[str] = Query(None),
    checkin_id: Optional[int] = Query(None),
):
    if checkin_id:
        records = get_photo_records_by_checkin(checkin_id)
    elif date:
        records = get_photo_records_by_date(date)
    else:
        raise HTTPException(status_code=400, detail="需要提供 date 或 checkin_id 参数")
    return {"records": records, "count": len(records)}


# ──────────────────── 模型验证（含被拒绝框详情） ────────────────────

@router.post("/tools/photo-checkin/validate")
async def validate_photos(
    photos: List[UploadFile] = File(...),
    filter_config_json: Optional[str] = Form(None),
):
    """
    验证端点：返回完整检测信息，包含被过滤框及原因。
    供「YOLO 模型验证与调参」工具使用，不写库。
    """
    if not photos:
        raise HTTPException(status_code=400, detail="未上传任何照片")
    if len(photos) > 20:
        raise HTTPException(status_code=400, detail="单次最多上传 20 张照片")

    filter_config = DEFAULT_FILTER_CONFIG.copy()
    if filter_config_json:
        try:
            filter_config.update(json.loads(filter_config_json))
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="filter_config_json 格式错误")

    images = []
    for photo in photos:
        ext = "." + (photo.filename or "").rsplit(".", 1)[-1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的图片格式 {ext}",
            )
        content = await photo.read()
        if len(content) > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail=f"图片 {photo.filename} 超过 {MAX_FILE_SIZE_MB}MB 限制",
            )
        images.append((photo.filename or f"photo_{len(images)}.jpg", content))

    try:
        results = detect_multiple(images, filter_config, include_rejected=True)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return {
        "photo_count": len(results),
        "filter_config": filter_config,
        "results": results,
    }


# ──────────────────── URL 批量导入验证 ────────────────────

_URL_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_URL_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AI-Analyst-Bot/1.0)"}


@router.post("/tools/photo-checkin/validate-urls")
async def validate_photos_from_urls(body: dict):
    """
    接收 URL 列表，后端下载后执行 YOLO 推理，返回识别结果（含被过滤框详情）。

    body: {
      "urls": ["https://...", ...],   # 最多 20 条
      "filter_config": { ... }        # 可选，同 /validate
    }
    """
    urls: List[str] = body.get("urls", [])
    if not urls:
        raise HTTPException(status_code=400, detail="未提供任何 URL")
    if len(urls) > 20:
        raise HTTPException(status_code=400, detail="单次最多 20 个 URL")

    # 基本格式校验
    for u in urls:
        if not isinstance(u, str) or not u.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail=f"无效 URL：{u}")

    filter_config = {**DEFAULT_FILTER_CONFIG, **body.get("filter_config", {})}

    # 并发下载所有图片
    images: List[tuple] = []   # (filename, bytes, source_url)
    url_errors: List[dict] = []

    async with httpx.AsyncClient(timeout=_URL_TIMEOUT, headers=_URL_HEADERS, follow_redirects=True) as client:
        for url in urls:
            filename = url.rsplit("/", 1)[-1].split("?")[0] or "photo.jpg"
            # 确保有扩展名
            if "." not in filename[-6:]:
                filename += ".jpg"
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")
                if not any(t in content_type for t in ("image/", "application/octet-stream")):
                    url_errors.append({"url": url, "error": f"非图片响应 ({content_type})"})
                    continue
                content = resp.content
                if len(content) > MAX_FILE_SIZE_MB * 1024 * 1024:
                    url_errors.append({"url": url, "error": f"超过 {MAX_FILE_SIZE_MB}MB"})
                    continue
                images.append((filename, content, url))
            except httpx.HTTPStatusError as e:
                url_errors.append({"url": url, "error": f"HTTP {e.response.status_code}"})
            except httpx.TimeoutException:
                url_errors.append({"url": url, "error": "请求超时（30s）"})
            except Exception as e:
                url_errors.append({"url": url, "error": str(e)[:120]})

    if not images:
        raise HTTPException(
            status_code=400,
            detail=f"全部 URL 下载失败：{[e['error'] for e in url_errors]}",
        )

    try:
        results = detect_multiple(
            [(fn, b) for fn, b, _ in images],
            filter_config,
            include_rejected=True,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # 补充 source_url 字段
    for i, (_, _, url) in enumerate(images):
        results[i]["source_url"] = url

    return {
        "photo_count": len(results),
        "error_count": len(url_errors),
        "filter_config": filter_config,
        "results": results,
        "url_errors": url_errors,
    }
