"""校外月度累积分析 — 从 SQLite 聚合多月数据，生成累积报表"""
import io
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from openpyxl.styles import Alignment

# ── 列名 ──
COL_CAMPUS = "校区"
COL_COACH = "教练"
COL_CLASS_COUNT = "课次"
COL_STUDENT_COUNT = "上课人次"
COL_AVG_CLASS_SIZE = "平均课堂人次"
COL_ATTENDANCE_RATE = "学员到课率"
COL_CONFIRMED_REVENUE = "确认收入"
COL_AVG_COURSE_PRICE = "平均课程单价"
COL_VENUE_FEE = "场地费"
COL_TEACHING_FEE = "课时费"
COL_VENUE_COST_PER_STUDENT = "学单人次场地费"
COL_COST_REVENUE_RATIO = "（场地费+课时费）/确收"
COL_CAMPUS_REVENUE_CONTRIB = "本校区营收贡献比"

FINAL_COLS = [
    COL_CAMPUS, COL_COACH, COL_CLASS_COUNT, COL_STUDENT_COUNT, COL_AVG_CLASS_SIZE,
    COL_ATTENDANCE_RATE, COL_CONFIRMED_REVENUE, COL_AVG_COURSE_PRICE,
    COL_VENUE_FEE, COL_TEACHING_FEE, COL_VENUE_COST_PER_STUDENT,
    COL_COST_REVENUE_RATIO, COL_CAMPUS_REVENUE_CONTRIB,
]

SUMMARY_SUFFIX = "-汇总"
Z_TOTAL = "Z总计"


def _safe_div(numer: float, denom: float) -> float:
    if abs(denom) < 1e-9 or not np.isfinite(denom) or not np.isfinite(numer):
        return 0.0
    return numer / denom


def _pct_str(numer: float, denom: float) -> str:
    if abs(denom) < 1e-9:
        return "-"
    val = numer / denom
    return f"{val:.2%}"


def _ratio_str(numer: float, denom: float) -> str:
    if abs(denom) < 1e-9:
        return "-"
    return f"{_safe_div(numer, denom):.4f}"


def _build_dataframe(raw: List[Dict[str, Any]]) -> pd.DataFrame:
    """将聚合后的原始数据构造成分析 DataFrame"""
    df = pd.DataFrame(raw)
    if df.empty:
        return df

    # 派生列
    df[COL_AVG_CLASS_SIZE] = df.apply(
        lambda r: round(_safe_div(r["actual_attendance"], r["lessons"]), 6) if r["lessons"] else 0.0, axis=1
    )
    df[COL_ATTENDANCE_RATE] = df.apply(
        lambda r: _pct_str(r["actual_attendance"], r["expected_attendance"]), axis=1
    )
    df[COL_AVG_COURSE_PRICE] = df.apply(
        lambda r: round(_safe_div(r["revenue"], r["actual_attendance"]), 6) if r["actual_attendance"] else 0.0, axis=1
    )
    df[COL_VENUE_COST_PER_STUDENT] = df.apply(
        lambda r: round(_safe_div(r["site_cost"], r["actual_attendance"]), 6) if r["actual_attendance"] else 0.0, axis=1
    )
    df[COL_COST_REVENUE_RATIO] = df.apply(
        lambda r: _ratio_str(r["site_cost"] + r["teaching_fee"], r["revenue"]), axis=1
    )

    # 本校区营收贡献比：教练收入 / 校区总收入
    campus_revenue = df.groupby("campus")["revenue"].transform("sum")
    df[COL_CAMPUS_REVENUE_CONTRIB] = df.apply(
        lambda r: _ratio_str(r["revenue"], campus_revenue.loc[r.name]), axis=1
    )

    # 重命名原始列
    df = df.rename(columns={
        "campus": COL_CAMPUS,
        "coach": COL_COACH,
        "lessons": COL_CLASS_COUNT,
        "actual_attendance": COL_STUDENT_COUNT,
        "revenue": COL_CONFIRMED_REVENUE,
        "site_cost": COL_VENUE_FEE,
        "teaching_fee": COL_TEACHING_FEE,
    })

    return df[FINAL_COLS].copy()


def _campus_summary_row(group: pd.DataFrame) -> pd.Series:
    """生成校区汇总行"""
    campus = group[COL_CAMPUS].iloc[0]
    total_lessons = group[COL_CLASS_COUNT].sum()
    total_attendance = group[COL_STUDENT_COUNT].sum()
    total_revenue = group[COL_CONFIRMED_REVENUE].sum()
    total_venue = group[COL_VENUE_FEE].sum()
    total_fee = group[COL_TEACHING_FEE].sum()

    # 到课率需重算（汇总行无单独的 expected_attendance，近似用出勤人次/总人次）
    # 实际在这一步已经聚合过了，只能展示 "-"
    return pd.Series({
        COL_CAMPUS: f"{campus}{SUMMARY_SUFFIX}",
        COL_COACH: None,
        COL_CLASS_COUNT: total_lessons,
        COL_STUDENT_COUNT: total_attendance,
        COL_AVG_CLASS_SIZE: round(_safe_div(total_attendance, total_lessons), 2) if total_lessons else 0.0,
        COL_ATTENDANCE_RATE: "-",
        COL_CONFIRMED_REVENUE: round(total_revenue, 2),
        COL_AVG_COURSE_PRICE: round(_safe_div(total_revenue, total_attendance), 2) if total_attendance else 0.0,
        COL_VENUE_FEE: round(total_venue, 2),
        COL_TEACHING_FEE: round(total_fee, 2),
        COL_VENUE_COST_PER_STUDENT: round(_safe_div(total_venue, total_attendance), 2) if total_attendance else 0.0,
        COL_COST_REVENUE_RATIO: _ratio_str(total_venue + total_fee, total_revenue),
        COL_CAMPUS_REVENUE_CONTRIB: 1.0,
    }, dtype=object)


def _total_row(df: pd.DataFrame) -> pd.Series:
    """生成全部总计行（排除汇总行）"""
    data = df[~df[COL_CAMPUS].astype(str).str.endswith(SUMMARY_SUFFIX)].copy()
    total_lessons = data[COL_CLASS_COUNT].sum()
    total_attendance = data[COL_STUDENT_COUNT].sum()
    total_revenue = data[COL_CONFIRMED_REVENUE].sum()
    total_venue = data[COL_VENUE_FEE].sum()
    total_fee = data[COL_TEACHING_FEE].sum()

    return pd.Series({
        COL_CAMPUS: Z_TOTAL,
        COL_COACH: None,
        COL_CLASS_COUNT: total_lessons,
        COL_STUDENT_COUNT: total_attendance,
        COL_AVG_CLASS_SIZE: round(_safe_div(total_attendance, total_lessons), 2) if total_lessons else 0.0,
        COL_ATTENDANCE_RATE: "-",
        COL_CONFIRMED_REVENUE: round(total_revenue, 2),
        COL_AVG_COURSE_PRICE: round(_safe_div(total_revenue, total_attendance), 2) if total_attendance else 0.0,
        COL_VENUE_FEE: round(total_venue, 2),
        COL_TEACHING_FEE: round(total_fee, 2),
        COL_VENUE_COST_PER_STUDENT: round(_safe_div(total_venue, total_attendance), 2) if total_attendance else 0.0,
        COL_COST_REVENUE_RATIO: _ratio_str(total_venue + total_fee, total_revenue),
        COL_CAMPUS_REVENUE_CONTRIB: 1.0,
    }, dtype=object)


def _generate_excel(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="累积统计", index=False)
        ws = writer.sheets["累积统计"]
        center = Alignment(horizontal="center", vertical="center")
        for row in ws.iter_rows():
            for cell in row:
                cell.alignment = center

        def _char_width(text):
            if text is None:
                return 0
            return sum(2 if "一" <= c <= "鿿" else 1 for c in str(text))

        for col in ws.columns:
            max_w = max(_char_width(cell.value) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_w + 2, 40)

    buf.seek(0)
    return buf.read()


def process_offcampus_cumulative(raw: List[Dict[str, Any]]) -> Tuple[bytes, Dict[str, Any]]:
    """
    接受 query_offcampus_cumulative() 返回的聚合数据，生成累积分析 Excel。
    返回 (excel_bytes, summary_dict)
    """
    df = _build_dataframe(raw)
    if df.empty:
        raise ValueError("没有可用数据")

    # 排序：按校区升序、按确认收入升序（与月度分析保持一致）
    df = df.sort_values([COL_CAMPUS, COL_CONFIRMED_REVENUE], ascending=[True, True]).reset_index(drop=True)

    # 添加校区汇总行
    summary_rows = (
        df.groupby(COL_CAMPUS, group_keys=False)
        .apply(_campus_summary_row)
        .reset_index(drop=True)
    )
    df = pd.concat([df, summary_rows], ignore_index=True)

    # 添加总计行
    total = _total_row(df).to_frame().T
    df = pd.concat([df, total], ignore_index=True)

    non_summary = df[
        ~df[COL_CAMPUS].astype(str).str.endswith(SUMMARY_SUFFIX) & (df[COL_CAMPUS] != Z_TOTAL)
    ]

    summary = {
        "campus_count": int(non_summary[COL_CAMPUS].nunique()),
        "coach_count": int(non_summary[COL_COACH].nunique()) if non_summary[COL_COACH].notna().any() else 0,
        "total_revenue": round(float(non_summary[COL_CONFIRMED_REVENUE].sum()), 2),
        "total_lessons": int(non_summary[COL_CLASS_COUNT].sum()),
    }

    excel_bytes = _generate_excel(df)
    return excel_bytes, summary
