"""课程类型管理 — JSON 持久化 + Excel 导入导出"""
import io
import os
import json
import logging
from typing import List, Optional

import pandas as pd
from openpyxl import Workbook

try:
    import fcntl
except ImportError:
    import types as _types
    fcntl = _types.ModuleType("fcntl")
    fcntl.LOCK_SH = 1
    fcntl.LOCK_EX = 2
    def _noop(f, flags): pass
    fcntl.flock = _noop

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
DATA_FILE = os.path.join(DATA_DIR, "course_types.json")
SEED_FILE = os.path.join(DATA_DIR, "samples", "26年春课程类型.xlsx")

TYPE_OPTIONS = ["兴趣班", "校队", "梯队", "体育课", "统包课", "晚托班", "社团课"]


# ──────────────────── JSON 读写 ────────────────────

def _read_json() -> list:
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        return json.load(f)


def _write_json(data: list):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)


def _seed_if_empty() -> list:
    """首次使用且 JSON 不存在时，从种子 Excel 自动导入"""
    records = _read_json()
    if records:
        return records
    if not os.path.exists(SEED_FILE):
        return []
    try:
        df = pd.read_excel(SEED_FILE, sheet_name="Sheet1")
        records = df[["课程名称", "类型"]].dropna().to_dict(orient="records")
        _write_json(records)
        logger.info(f"种子数据导入完成: {len(records)} 条课程类型")
    except Exception as e:
        logger.warning(f"种子数据导入失败: {e}")
        return []
    return records


# ──────────────────── CRUD ────────────────────

def load_all() -> list:
    """加载全部课程类型映射"""
    return _seed_if_empty()


def add_record(course_name: str, course_type: str) -> dict:
    """新增一条映射"""
    records = _read_json()
    # 去重检查
    for r in records:
        if r["课程名称"] == course_name:
            raise ValueError(f"课程「{course_name}」已存在")
    record = {"课程名称": course_name, "类型": course_type}
    records.append(record)
    _write_json(records)
    return record


def update_record(index: int, course_type: str) -> dict:
    """修改某条的类型"""
    records = _read_json()
    if index < 0 or index >= len(records):
        raise IndexError(f"索引 {index} 超出范围（共 {len(records)} 条）")
    records[index]["类型"] = course_type
    _write_json(records)
    return records[index]


def delete_record(index: int) -> dict:
    """删除某条"""
    records = _read_json()
    if index < 0 or index >= len(records):
        raise IndexError(f"索引 {index} 超出范围（共 {len(records)} 条）")
    removed = records.pop(index)
    _write_json(records)
    return removed


def import_from_excel(data: bytes) -> dict:
    """从 Excel 批量导入，增量合并（已有课程跳过）"""
    try:
        df = pd.read_excel(io.BytesIO(data), sheet_name="Sheet1", engine="openpyxl")
    except Exception:
        df = pd.read_excel(io.BytesIO(data), sheet_name="Sheet1", engine="xlrd")

    if "课程名称" not in df.columns or "类型" not in df.columns:
        raise ValueError("Excel 必须包含「课程名称」和「类型」两列")

    new_records = df[["课程名称", "类型"]].dropna(subset=["课程名称"]).to_dict(orient="records")
    existing = _read_json()
    existing_names = {r["课程名称"] for r in existing}

    imported = 0
    for rec in new_records:
        if rec["课程名称"] not in existing_names:
            existing.append(rec)
            existing_names.add(rec["课程名称"])
            imported += 1

    _write_json(existing)
    return {
        "imported": imported,
        "skipped": len(new_records) - imported,
        "total": len(existing),
    }


def export_to_excel() -> bytes:
    """导出为 Excel 字节流"""
    records = _seed_if_empty()
    df = pd.DataFrame(records)
    if df.empty:
        df = pd.DataFrame(columns=["课程名称", "类型"])

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Sheet1", index=False)
    buf.seek(0)
    return buf.read()


def get_type_options() -> list:
    """返回预定义类型列表"""
    return TYPE_OPTIONS
