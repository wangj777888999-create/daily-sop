"""月度源数据存储层 — 每月上传一次，所有工具复用"""
import os
from typing import Dict, Any, Optional, List

from tools.db import (
    upsert_monthly_upload_meta,
    get_monthly_upload_meta,
    delete_monthly_upload_meta,
    list_monthly_upload_periods,
)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
UPLOAD_BASE = os.path.join(DATA_DIR, "monthly_uploads")

# key -> (存储文件名, 显示名, 用途说明)
FILE_KEYS: Dict[str, tuple] = {
    "skjl":         ("skjl.xlsx",         "上课记录",    "校内月报 / 校外月报 / 折扣率"),
    "finance":      ("finance.xls",       "财务统计明细", "校内月报 / 校外月报"),
    "teaching_fee": ("teaching_fee.xlsx", "校外课时费",  "校外月报"),
    "venue_fee":    ("venue_fee.xlsx",    "场地费",      "校外月报"),
    "refund":       ("refund.xls",        "退款导出",    "校内月报"),
    "last_month":   ("last_month.xlsx",   "上月分析报告", "校外月报（可选）"),
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def _stored_path(year: int, month: int, key: str) -> str:
    filename, _, _ = FILE_KEYS[key]
    return os.path.join(UPLOAD_BASE, str(year), str(month), filename)


def save_monthly_file(
    year: int, month: int, key: str, filename: str, data: bytes
) -> Dict[str, Any]:
    if key not in FILE_KEYS:
        raise ValueError(f"未知文件类型: {key}，可用: {list(FILE_KEYS)}")
    if len(data) > MAX_FILE_SIZE:
        raise ValueError(f"文件过大（{len(data) // 1024 // 1024} MB），上限 50 MB")

    path = _stored_path(year, month, key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)

    rel_path = os.path.relpath(path, DATA_DIR)
    upsert_monthly_upload_meta(year, month, key, filename, rel_path, len(data))

    return {
        "key": key,
        "original_name": filename,
        "size": len(data),
        "path": rel_path,
    }


def get_monthly_file_bytes(year: int, month: int, key: str) -> Optional[bytes]:
    if key not in FILE_KEYS:
        return None
    path = _stored_path(year, month, key)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return f.read()


def get_monthly_status(year: int, month: int) -> Dict[str, Any]:
    meta_rows = get_monthly_upload_meta(year, month)
    meta_by_key = {r["file_key"]: r for r in meta_rows}

    files: Dict[str, Any] = {}
    for key, (_, label, usage) in FILE_KEYS.items():
        if key in meta_by_key:
            row = meta_by_key[key]
            files[key] = {
                "uploaded": True,
                "label": label,
                "usage": usage,
                "original_name": row["original_name"],
                "size": row["file_size"],
                "uploaded_at": row["uploaded_at"],
            }
        else:
            files[key] = {
                "uploaded": False,
                "label": label,
                "usage": usage,
            }

    return {"year": year, "month": month, "files": files}


def delete_monthly_file(year: int, month: int, key: str) -> bool:
    if key not in FILE_KEYS:
        return False
    path = _stored_path(year, month, key)
    if os.path.exists(path):
        os.remove(path)
    return delete_monthly_upload_meta(year, month, key)


def list_monthly_periods() -> List[Dict[str, Any]]:
    return list_monthly_upload_periods()
