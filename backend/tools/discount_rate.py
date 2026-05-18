"""课时费折扣率计算 — 单 Excel 数据源，按课程/教练两级汇总折扣率"""
import io
import json
import os
import logging
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment
from openpyxl.utils.dataframe import dataframe_to_rows

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "discount_rate_output")
CONFIG_PATH = os.path.join(DATA_DIR, "discount_rate_config.json")

# 期望列名 — 用于自动检测表头行
EXPECTED_COLS = {"学员名称", "课程名称", "上课信息", "状态", "创建时间"}


# ──────────────────── 课程配置持久化 ────────────────────

def load_course_configs() -> Dict[str, Dict[str, str]]:
    """
    加载课程配置（申请人数 + 教练）。
    格式：{ "课程名称": { "申请人数": "15", "教练": "邓文凯" }, ... }
    """
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_course_configs(configs: Dict[str, Dict[str, str]]) -> int:
    """
    保存课程配置，返回课程数量。
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(configs, f, ensure_ascii=False, indent=2)
    return len(configs)


# ──────────────────── 工具函数 ────────────────────

def _detect_header_row(expected_cols: set, raw_df: pd.DataFrame) -> int:
    """扫描前 5 行，返回包含最多期望列名的行索引"""
    best_idx, best_count = 0, 0
    for i in range(min(len(raw_df), 5)):
        row_vals = {str(v).strip() for v in raw_df.iloc[i].values if pd.notna(v)}
        count = len(expected_cols & row_vals)
        if count > best_count:
            best_count = count
            best_idx = i
    return best_idx


def _read_excel(data: bytes) -> pd.DataFrame:
    """读取 Excel，自动检测表头"""
    engines = ["openpyxl", "xlrd"]
    for engine in engines:
        try:
            preview = pd.read_excel(io.BytesIO(data), header=None, nrows=5, engine=engine)
            header_idx = _detect_header_row(EXPECTED_COLS, preview)
            return pd.read_excel(io.BytesIO(data), header=header_idx, engine=engine)
        except Exception:
            continue
    raise ValueError("无法读取 Excel 文件")


def _parse_class_info_date(info_str: str) -> str:
    """从 'YYYY-MM-DD HH:MM-HH:MM' 中提取日期部分 'YYYY-MM-DD'"""
    s = str(info_str).strip()
    if " " in s:
        return s.split(" ")[0]
    return s


def _parse_class_info_time(info_str: str) -> str:
    """从 'YYYY-MM-DD HH:MM-HH:MM' 中提取时间范围 'HH:MM-HH:MM'"""
    s = str(info_str).strip()
    if " " in s:
        return s.split(" ", 1)[1]
    return ""


# ──────────────────── 筛选 ────────────────────

def _filter_records(
    df: pd.DataFrame,
    exclude_keywords: List[str],
    exclude_dates: List[str],
) -> pd.DataFrame:
    """两层筛选：先按课程名称关键字，再按日期"""
    result = df.copy()

    # 第一层：课程名称关键字过滤
    if exclude_keywords:
        mask = pd.Series(False, index=result.index)
        for kw in exclude_keywords:
            kw = kw.strip()
            if kw:
                mask = mask | result["课程名称"].astype(str).str.contains(kw, case=False, na=False)
        result = result[~mask]

    # 第二层：日期过滤
    if exclude_dates:
        result["_上课日期"] = result["上课信息"].apply(_parse_class_info_date)
        result = result[~result["_上课日期"].isin(exclude_dates)]
        result = result.drop(columns=["_上课日期"])

    return result


# ──────────────────── 课次统计 ────────────────────

def _calc_session_stats(df: pd.DataFrame) -> pd.DataFrame:
    """按 (课程名称 + 上课日期) 分组，统计每次课的到课/旷课/请假人数"""
    df = df.copy()
    df["_上课日期"] = df["上课信息"].apply(_parse_class_info_date)
    df["_时间范围"] = df["上课信息"].apply(_parse_class_info_time)

    records = []
    for (course, date_str), group in df.groupby(["课程名称", "_上课日期"]):
        arrived = (group["状态"] == "已到").sum()
        absent = (group["状态"] == "旷课").sum()
        leave = (group["状态"] == "请假").sum()
        time_range = group["_时间范围"].iloc[0] if len(group) > 0 else ""
        records.append({
            "课程名称": course,
            "上课日期": date_str,
            "上课信息": f"{date_str} {time_range}" if time_range else date_str,
            "已到": int(arrived),
            "旷课": int(absent),
            "请假": int(leave),
            "排课人数": int(arrived + absent + leave),
        })

    return pd.DataFrame(records)


# ──────────────────── Level 1: 班级汇总 ────────────────────

def _compute_denominator(
    apply_num_val: Any,
    F: int,
    course_name: str,
    threshold_basketball: int,
    threshold_football: int,
) -> int:
    """计算分母规则"""
    str_val = str(apply_num_val).strip() if apply_num_val is not None else ""
    if str_val in ("新", "新开", ""):
        if "篮球" in str(course_name) and F >= threshold_basketball:
            return F
        elif "足球" in str(course_name) and F >= threshold_football:
            return F
        else:
            return 0
    else:
        try:
            G = int(float(str_val))
        except (ValueError, TypeError):
            return F
        return max(F, G)


def _calc_level1(
    session_stats: pd.DataFrame,
    course_edits: Dict[str, Dict[str, Any]],
    threshold_basketball: int,
    threshold_football: int,
) -> List[Dict[str, Any]]:
    """Level 1: 按课程名称聚合，计算每个班的各项指标"""
    rows = []
    for course, grp in session_stats.groupby("课程名称"):
        # 最多人那次课
        max_idx = grp["排课人数"].idxmax()
        max_row = grp.loc[max_idx]
        max_class_info = max_row["上课信息"]
        max_arrived = int(max_row["已到"])
        max_absent = int(max_row["旷课"])
        max_leave = int(max_row["请假"])
        F = int(max_row["排课人数"])

        # 计算课次
        lesson_count = len(grp)

        # 实到人数（所有课次已到之和）
        total_arrived = int(grp["已到"].sum())

        # 从 course_edits 获取用户编辑的值
        edit = course_edits.get(course, {})
        apply_num = edit.get("申请人数", "")
        coach = edit.get("教练", "")

        # 计算分母
        denom = _compute_denominator(apply_num, F, course, threshold_basketball, threshold_football)

        # 全月应到
        total_expected = denom * lesson_count

        # 到课率
        if total_expected > 0:
            rate = total_arrived / total_expected
        else:
            rate = None

        rows.append({
            "课程名称": course,
            "最多人那次课": max_class_info,
            "已到": max_arrived,
            "旷课": max_absent,
            "请假": max_leave,
            "最大排课人数(F)": F,
            "申请人数(G)": str(apply_num) if apply_num else "",
            "计算分母": denom,
            "计算课次": lesson_count,
            "教练": str(coach) if coach else "",
            "全月应到": total_expected,
            "实到人数": total_arrived,
            "到课率": round(rate * 100, 2) if rate is not None else None,
        })

    # 按最大排课人数降序
    rows.sort(key=lambda x: x["最大排课人数(F)"], reverse=True)
    return rows


# ──────────────────── Level 2: 教练汇总 ────────────────────

def _calc_level2(level1_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Level 2: 按教练分组，汇总全月应到和实到人数"""
    coach_data = {}
    for row in level1_rows:
        coach = row.get("教练", "")
        if not coach:
            continue
        if coach not in coach_data:
            coach_data[coach] = {"教练": coach, "全月应到": 0, "实到人数": 0}
        coach_data[coach]["全月应到"] += row.get("全月应到", 0)
        coach_data[coach]["实到人数"] += row.get("实到人数", 0)

    results = []
    for coach, data in coach_data.items():
        expected = data["全月应到"]
        actual = data["实到人数"]
        if expected > 0:
            rate = round(actual / expected * 100, 2)
        else:
            rate = None
        results.append({
            "教练": coach,
            "全月应到": expected,
            "实到人数": actual,
            "教练折扣率(%)": rate,
        })

    results.sort(key=lambda x: x["全月应到"], reverse=True)
    return results


# ──────────────────── Excel 生成 ────────────────────

def _generate_excel(level1_rows: List[Dict], level2_rows: List[Dict]) -> bytes:
    """生成双 Sheet Excel（班级汇总 + 教练汇总）"""
    df1 = pd.DataFrame(level1_rows)
    df2 = pd.DataFrame(level2_rows)

    # 到课率格式化为百分比字符串
    if "到课率" in df1.columns:
        df1["到课率"] = df1["到课率"].apply(
            lambda x: f"{x:.2f}%" if x is not None else ""
        )
    if "教练折扣率(%)" in df2.columns:
        df2["教练折扣率(%)"] = df2["教练折扣率(%)"].apply(
            lambda x: f"{x:.2f}%" if x is not None else ""
        )

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for sheet_name, data in [("班级汇总", df1), ("教练汇总", df2)]:
            if data.empty:
                pd.DataFrame().to_excel(writer, sheet_name=sheet_name, index=False)
                continue
            data.to_excel(writer, sheet_name=sheet_name, index=False)
            ws = writer.sheets[sheet_name]
            center = Alignment(horizontal="center", vertical="center")
            for row in ws.iter_rows():
                for cell in row:
                    cell.alignment = center

            def _char_width(text):
                if text is None:
                    return 0
                return sum(2 if "一" <= c <= "鿿" else 1 for c in str(text))

            for col in ws.columns:
                max_w = max((_char_width(cell.value) for cell in col), default=2)
                ws.column_dimensions[col[0].column_letter].width = min(max_w + 3, 60)

    buf.seek(0)
    return buf.read()


# ──────────────────── 公开 API ────────────────────

def preview_discount_rate(
    data: bytes,
    exclude_keywords: List[str],
    exclude_dates: List[str],
    threshold_basketball: int,
    threshold_football: int,
    course_edits: Dict[str, Dict[str, Any]],
    use_stored_config: bool = True,
) -> Dict[str, Any]:
    """完整管线：读取 → 筛选 → 课次统计 → Level1 → Level2"""
    df = _read_excel(data)
    raw_count = len(df)

    # 可用日期（筛选前）
    all_dates = sorted(set(df["上课信息"].apply(_parse_class_info_date).dropna().unique().tolist()))

    # 筛选
    filtered = _filter_records(df, exclude_keywords, exclude_dates)
    filtered_count = len(filtered)

    if filtered.empty:
        return {
            "raw_count": raw_count,
            "filtered_count": 0,
            "available_dates": all_dates,
            "level1": [],
            "level2": [],
        }

    # 合并存储的课程配置（前端传入的 edits 优先）
    if use_stored_config:
        stored = load_course_configs()
        for course, cfg in stored.items():
            if course not in course_edits:
                course_edits[course] = cfg
            else:
                # 前端未覆盖的字段从存储补
                if not course_edits[course].get("申请人数"):
                    course_edits[course]["申请人数"] = cfg.get("申请人数", "")
                if not course_edits[course].get("教练"):
                    course_edits[course]["教练"] = cfg.get("教练", "")

    # 课次统计
    session_stats = _calc_session_stats(filtered)

    # Level 1
    level1 = _calc_level1(session_stats, course_edits, threshold_basketball, threshold_football)

    # Level 2
    level2 = _calc_level2(level1)

    return {
        "raw_count": raw_count,
        "filtered_count": filtered_count,
        "available_dates": all_dates,
        "level1": level1,
        "level2": level2,
    }


def generate_discount_rate_excel(
    data: bytes,
    exclude_keywords: List[str],
    exclude_dates: List[str],
    threshold_basketball: int,
    threshold_football: int,
    course_edits: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """同 preview，额外生成 Excel"""
    result = preview_discount_rate(
        data, exclude_keywords, exclude_dates,
        threshold_basketball, threshold_football, course_edits,
    )

    excel_bytes = _generate_excel(result["level1"], result["level2"])

    coaches = set()
    for row in result["level1"]:
        if row.get("教练"):
            coaches.add(row["教练"])

    return {
        "excel_bytes": excel_bytes,
        "level1": result["level1"],
        "level2": result["level2"],
        "summary": {
            "raw_count": result["raw_count"],
            "filtered_count": result["filtered_count"],
            "course_count": len(result["level1"]),
            "coach_count": len(coaches),
        },
    }
