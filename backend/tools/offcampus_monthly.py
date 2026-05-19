"""校外月度分析 — 独立数据源，4 个必传 + 1 个可选 Excel"""
import io
import os
import json
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment
from openpyxl.utils.dataframe import dataframe_to_rows

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "offcampus_output")

# ── 列名常量 ──
COL_CAMPUS = "校区"
COL_COACH = "教练"
COL_COURSE_NAME = "课程名称"
COL_ORDER_TYPE = "订单类型"
COL_COURSE_INFO = "上课信息"
COL_STATUS = "状态"
COL_ATTENDED = "已到"
COL_STUDENT_TYPE = "学员类型"
COL_VENUE_STUDENT = "球馆学员"
COL_COURSE_PRICE = "课程单价"
COL_CAMPUS_COACH = "校区教练"
COL_TIME_COURSE = "时加课"
COL_CLASS_COUNT = "课次"
COL_STUDENT_COUNT = "上课人次"
COL_AVG_CLASS_SIZE = "平均课堂人次"
COL_ATTENDANCE_RATE = "到课率"
COL_CONFIRMED_REVENUE = "确认收入"
COL_AVG_COURSE_PRICE = "平均课程单价"
COL_LOW_CLASS_COUNT = "5人及以下课程数"
COL_LOW_CLASS_RATIO = "5人及以下比例"
COL_HIGH_CLASS_COUNT = "10人及以上课程数"
COL_HIGH_CLASS_RATIO = "10人及以上比例"
COL_INTERNAL_CLASSES = "校内上课节次"
COL_TEACHING_FEE = "应发课时费"
COL_VENUE_FEE = "场地费"
COL_S3_VENUE_COST = "S3:场地费生均成本"
COL_COST_REVENUE_RATIO = "(场地费+课时费)/确收"
COL_CAMPUS_REVENUE_CONTRIB = "本校区营收贡献比"
COL_LAST_MONTH_VENUE_COST = "上月场地费生均成本"
COL_S3_CHANGE = "s3较上月变化"
COL_BELOW_AVG_RATIO = "低于校区生均场地费占比"
COL_ABOVE_2X_RATIO = "高于校区生均场地费1倍占比"
COL_MAX_COURSE_VENUE_RATIO = "最高课程生均场地费/s3"
COL_VENUE_TOTAL = "校区场地费合计"
COL_CAMPUS_ATTENDANCE_TOTAL = "校区总到课人次"
COL_AVG_VENUE_COST = "校区生均场地费"
COL_COURSE_VENUE_COST = "课程生均场地费"
COL_COURSE_ATTENDANCE_COUNT = "上课人数"
COL_TOTAL_EXPECTED = "总应到人数"
COL_ATTENDED_COUNT = "已到人数"
COL_PRIVATE_TUTOR = "私教"
COL_COACH_NAME_ALT = "教练员"

FINAL_COLS = [
    COL_CAMPUS, COL_COACH, COL_CLASS_COUNT, COL_STUDENT_COUNT, COL_AVG_CLASS_SIZE,
    COL_ATTENDANCE_RATE, COL_CONFIRMED_REVENUE, COL_AVG_COURSE_PRICE, COL_VENUE_FEE,
    COL_TEACHING_FEE, COL_S3_VENUE_COST, COL_COST_REVENUE_RATIO, COL_CAMPUS_REVENUE_CONTRIB,
    COL_INTERNAL_CLASSES, COL_LOW_CLASS_COUNT, COL_LOW_CLASS_RATIO, COL_HIGH_CLASS_COUNT,
    COL_HIGH_CLASS_RATIO, COL_LAST_MONTH_VENUE_COST, COL_S3_CHANGE,
    COL_BELOW_AVG_RATIO, COL_ABOVE_2X_RATIO, COL_MAX_COURSE_VENUE_RATIO,
]

PINGPONG = "乒乓球"
SUMMARY_SUFFIX = "-汇总"
Z_TOTAL = "Z总计"


def _safe_div_str(numer: float, denom: float, fmt: str = ".2f", suffix: str = "%") -> str:
    """安全除法，denom 为 0 或非有限时返回占位符"""
    if abs(denom) < 1e-9 or not np.isfinite(denom) or not np.isfinite(numer):
        return f"{0:{fmt}}{suffix}" if suffix else f"{0:{fmt}}"
    result = numer / denom
    if not np.isfinite(result):
        return f"{0:{fmt}}{suffix}" if suffix else f"{0:{fmt}}"
    return f"{result * 100:{fmt}}{suffix}" if suffix else f"{result:{fmt}}"


def _safe_div_float(numer: float, denom: float, default: float = 0.0) -> float:
    """安全浮点除法，denom 为 0 或非有限时返回 default"""
    if abs(denom) < 1e-9 or not np.isfinite(denom) or not np.isfinite(numer):
        return default
    result = numer / denom
    return result if np.isfinite(result) else default


# ──────────────────── 工具函数 ────────────────────

def _load_config() -> dict:
    config_path = os.path.join(DATA_DIR, "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


# 期望列名 — 用于自动检测表头行
_CW_EXPECTED_COLS = {"学员类型", "学员姓名", "课程名称", "课程单价", "上课日期", "上课时间", "教练"}
_SKJL_EXPECTED_COLS = {"课程名称", "上课信息", "状态"}


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


def _read_excel(data: bytes, sheet_name: str = "Sheet1", expected_cols: set = None) -> pd.DataFrame:
    engines = ["openpyxl", "xlrd"]
    for engine in engines:
        try:
            if expected_cols:
                preview = pd.read_excel(io.BytesIO(data), sheet_name=sheet_name, header=None, nrows=5, engine=engine)
                header_idx = _detect_header_row(expected_cols, preview)
                return pd.read_excel(io.BytesIO(data), sheet_name=sheet_name, header=header_idx, engine=engine)
            else:
                return pd.read_excel(io.BytesIO(data), sheet_name=sheet_name, engine=engine)
        except Exception:
            continue
    raise ValueError(f"无法读取 Excel 文件（sheet: {sheet_name}）")


# ──────────────────── 子函数 ────────────────────


def process_finance_data(cw: pd.DataFrame) -> tuple:
    """处理财务数据：校外财务表（球馆学员）+ 课程-教练-校区映射"""
    xwcw = cw[cw[COL_STUDENT_TYPE] == COL_VENUE_STUDENT].copy()
    xwcw.rename(columns={COL_ORDER_TYPE: COL_CAMPUS}, inplace=True)

    # 从 xwcw（已 rename 校区）构建 session 映射，含校区列
    xwcw[COL_TIME_COURSE] = (
        xwcw["上课日期"].astype(str) + " "
        + xwcw["上课时间"].astype(str)
        + xwcw[COL_COURSE_NAME].astype(str)
    )
    course_coach = xwcw.drop_duplicates(subset=[COL_TIME_COURSE])[
        [COL_TIME_COURSE, COL_COACH, COL_CAMPUS]
    ].copy()
    return xwcw, course_coach


def calculate_basic_stats(xwcw: pd.DataFrame) -> pd.DataFrame:
    """计算上课节次、人次、平均课堂人次（以财务明细为基底，财务行即已到）"""
    xwcw_copy = xwcw.copy()
    # 时加课已由 process_finance_data 写入，此处确保存在
    if COL_TIME_COURSE not in xwcw_copy.columns:
        xwcw_copy[COL_TIME_COURSE] = (
            xwcw_copy["上课日期"].astype(str) + " "
            + xwcw_copy["上课时间"].astype(str)
            + xwcw_copy[COL_COURSE_NAME].astype(str)
        )
    xwcw_copy[COL_CAMPUS_COACH] = xwcw_copy[COL_CAMPUS].astype(str) + "-" + xwcw_copy[COL_COACH].astype(str)

    # 财务记录即已到，无需 status 过滤
    campus_course = (
        xwcw_copy.drop_duplicates(subset=[COL_TIME_COURSE])
        .groupby(COL_CAMPUS_COACH, as_index=False)[COL_TIME_COURSE]
        .nunique()
        .rename(columns={COL_TIME_COURSE: "上课节次"})
    )
    campus_people = (
        xwcw_copy.groupby(COL_CAMPUS_COACH, as_index=False)
        .size()
        .rename(columns={"size": COL_STUDENT_COUNT})
    )

    combined = pd.merge(campus_course, campus_people, on=COL_CAMPUS_COACH, how="outer")
    combined["上课节次"] = combined["上课节次"].fillna(0).astype(int)
    combined[COL_STUDENT_COUNT] = combined[COL_STUDENT_COUNT].fillna(0).astype(int)
    combined[[COL_CAMPUS, COL_COACH]] = combined[COL_CAMPUS_COACH].str.split("-", n=1, expand=True)
    combined[COL_AVG_CLASS_SIZE] = combined.apply(
        lambda x: _safe_div_float(x[COL_STUDENT_COUNT], x["上课节次"]), axis=1
    )
    return combined


def calculate_attendance_rate(combined: pd.DataFrame, xwskjl_copy: pd.DataFrame) -> pd.DataFrame:
    """计算到课率（排除私教课程）"""
    xwskjl_filtered = xwskjl_copy[
        ~xwskjl_copy[COL_COURSE_NAME].str.contains(COL_PRIVATE_TUTOR, case=False, na=False)
    ].copy()
    xwskjl_in = xwskjl_filtered[xwskjl_filtered[COL_STATUS] == COL_ATTENDED].copy()

    total_persons = (
        xwskjl_filtered.groupby(COL_CAMPUS_COACH, as_index=False)
        .size()
        .rename(columns={"size": COL_TOTAL_EXPECTED})
    )
    attended_persons = (
        xwskjl_in.groupby(COL_CAMPUS_COACH, as_index=False)
        .size()
        .rename(columns={"size": COL_ATTENDED_COUNT})
    )

    attendance = pd.merge(total_persons, attended_persons, on=COL_CAMPUS_COACH, how="left")
    attendance[COL_ATTENDED_COUNT] = attendance[COL_ATTENDED_COUNT].fillna(0)
    attendance[COL_ATTENDANCE_RATE] = attendance.apply(
        lambda x: _safe_div_str(x[COL_ATTENDED_COUNT], x[COL_TOTAL_EXPECTED]), axis=1
    )

    combined = pd.merge(
        combined,
        attendance[[COL_CAMPUS_COACH, COL_ATTENDANCE_RATE, COL_ATTENDED_COUNT, COL_TOTAL_EXPECTED]],
        on=COL_CAMPUS_COACH,
        how="left",
    )
    combined[COL_ATTENDED_COUNT] = combined[COL_ATTENDED_COUNT].fillna(0)
    combined[COL_TOTAL_EXPECTED] = combined[COL_TOTAL_EXPECTED].fillna(0)
    return combined


def calculate_revenue(combined: pd.DataFrame, xwcw: pd.DataFrame) -> pd.DataFrame:
    """统计确认收入与平均课程单价"""
    xwcw_copy = xwcw.copy()
    xwcw_copy[COL_CAMPUS_COACH] = xwcw_copy[COL_CAMPUS].astype(str) + "-" + xwcw_copy[COL_COACH].astype(str)

    campus_revenue = (
        xwcw_copy.groupby(COL_CAMPUS_COACH, as_index=False)[COL_COURSE_PRICE]
        .sum()
        .rename(columns={COL_COURSE_PRICE: COL_CONFIRMED_REVENUE})
    )
    campus_revenue[COL_CONFIRMED_REVENUE] = campus_revenue[COL_CONFIRMED_REVENUE].fillna(0).round(2)

    combined = pd.merge(combined, campus_revenue[[COL_CAMPUS_COACH, COL_CONFIRMED_REVENUE]], on=COL_CAMPUS_COACH, how="left")
    combined[COL_CONFIRMED_REVENUE] = combined[COL_CONFIRMED_REVENUE].fillna(0).round(2)
    combined[COL_AVG_COURSE_PRICE] = combined.apply(
        lambda x: _safe_div_float(x[COL_CONFIRMED_REVENUE], x[COL_STUDENT_COUNT]), axis=1
    )
    combined.rename(columns={"上课节次": COL_CLASS_COUNT}, inplace=True)
    return combined


def analyze_class_size(combined: pd.DataFrame, xwskjl_copy: pd.DataFrame) -> pd.DataFrame:
    """统计5人及以下、10人及以上课程数及比例"""
    xwskjl_filtered = xwskjl_copy[
        ~xwskjl_copy[COL_COURSE_NAME].str.contains(COL_PRIVATE_TUTOR, case=False, na=False)
    ].copy()

    ca_grouped = xwskjl_filtered.groupby([COL_COURSE_INFO, COL_CAMPUS_COACH])[COL_STATUS].apply(list).reset_index()
    ca_container = defaultdict(lambda: {"total": 0, "low": 0, "high": 0})

    for _, row in ca_grouped.iterrows():
        present = sum(1 for s in row[COL_STATUS] if s == COL_ATTENDED)
        ca_container[row[COL_CAMPUS_COACH]]["total"] += 1
        if present <= 5:
            ca_container[row[COL_CAMPUS_COACH]]["low"] += 1
        if present >= 10:
            ca_container[row[COL_CAMPUS_COACH]]["high"] += 1

    ca_df = pd.DataFrame([
        {
            COL_CAMPUS_COACH: k,
            COL_LOW_CLASS_COUNT: v["low"],
            COL_LOW_CLASS_RATIO: _safe_div_str(v["low"], v["total"]),
            COL_HIGH_CLASS_COUNT: v["high"],
            COL_HIGH_CLASS_RATIO: _safe_div_str(v["high"], v["total"]),
        }
        for k, v in ca_container.items()
    ])

    target_cols = [COL_LOW_CLASS_COUNT, COL_LOW_CLASS_RATIO, COL_HIGH_CLASS_COUNT, COL_HIGH_CLASS_RATIO]
    combined = combined.drop(columns=[c for c in target_cols if c in combined.columns], errors="ignore")
    return pd.merge(combined, ca_df, on=COL_CAMPUS_COACH, how="left").fillna({
        COL_LOW_CLASS_COUNT: 0,
        COL_HIGH_CLASS_COUNT: 0,
        COL_LOW_CLASS_RATIO: "0.00%",
        COL_HIGH_CLASS_RATIO: "0.00%",
    })


def calculate_campus_contribution(combined: pd.DataFrame) -> pd.DataFrame:
    """计算教练对本校区的营收贡献比"""
    campus_total = (
        combined.groupby(COL_CAMPUS, as_index=False)[COL_CONFIRMED_REVENUE]
        .sum()
        .rename(columns={COL_CONFIRMED_REVENUE: "校区总营收"})
    )
    combined = pd.merge(combined, campus_total, on=COL_CAMPUS, how="left")
    combined[COL_CAMPUS_REVENUE_CONTRIB] = combined.apply(
        lambda x: _safe_div_str(x[COL_CONFIRMED_REVENUE], x["校区总营收"]), axis=1
    )
    return combined.drop(columns="校区总营收")


def calculate_offcampus_in_campus(
    xnskjl: pd.DataFrame, course_coach: pd.DataFrame, off_campus_coaches: List[str]
) -> pd.DataFrame:
    """统计校外教练在校内的上课节次"""
    xnskjl_copy = xnskjl.copy()
    xnskjl_copy[COL_TIME_COURSE] = xnskjl_copy[COL_COURSE_INFO].astype(str) + xnskjl_copy[COL_COURSE_NAME].astype(str)
    xnskjl_unique = xnskjl_copy.drop_duplicates(subset=[COL_TIME_COURSE]).copy()
    xnskjl_unique = pd.merge(xnskjl_unique, course_coach, on=COL_TIME_COURSE, how="left")
    return (
        xnskjl_unique[xnskjl_unique[COL_COACH].isin(off_campus_coaches)]
        .groupby(COL_COACH, as_index=False)
        .size()
        .rename(columns={"size": COL_INTERNAL_CLASSES})
    )


def merge_teaching_fee(combined: pd.DataFrame, xwksf: pd.DataFrame) -> pd.DataFrame:
    """合并校外课时费数据"""
    xwksf_copy = xwksf.copy()
    xwksf_copy[COL_CAMPUS_COACH] = xwksf_copy[COL_CAMPUS].astype(str) + "-" + xwksf_copy[COL_COACH].astype(str)
    if COL_TEACHING_FEE in combined.columns:
        combined = combined.drop(columns=[COL_TEACHING_FEE], errors="ignore")
    combined = pd.merge(combined, xwksf_copy[[COL_CAMPUS_COACH, COL_TEACHING_FEE]], on=COL_CAMPUS_COACH, how="left")
    combined[COL_TEACHING_FEE] = combined[COL_TEACHING_FEE].fillna(0).round(2)
    return combined


def site_cost(combined: pd.DataFrame, cdf_bytes: bytes, xwskjl_copy: pd.DataFrame,
              last_month_ana: pd.DataFrame) -> pd.DataFrame:
    """场地费及相关费用计算（xwskjl_copy 由调用方传入，已含校区教练和时加课）"""
    try:
        excel_file = pd.ExcelFile(io.BytesIO(cdf_bytes))
    except Exception as e:
        raise ValueError(f"无法读取场地费文件：{e}")

    sheet_data = []
    campus_name_map = {
        "农都校区": "农都城校区（篮球）",
        "滨江校区": "滨江天街校区",
        "西溪校区": "西溪天街校区",
    }
    for sheet_name in excel_file.sheet_names:
        try:
            df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
            df = df.drop(index=0).reset_index(drop=True)
            df.columns = df.iloc[0]
            df = df.drop(index=0).reset_index(drop=True)
        except Exception as e:
            raise ValueError(f"读取 Sheet「{sheet_name}」失败，请检查文件格式：{e}")
        if sheet_name in campus_name_map:
            df[COL_CAMPUS] = campus_name_map[sheet_name]
        sheet_data.append(df)

    if not sheet_data:
        raise ValueError("场地费文件中没有可读取的 Sheet")

    date_sheet = pd.concat(sheet_data, ignore_index=True)
    date_sheet["上课日期"] = pd.to_datetime(date_sheet["上课日期"], errors="coerce").dt.strftime("%Y-%m-%d")
    date_sheet["上课时间"] = date_sheet["上课时间"].str.replace("--", "-", regex=False)
    date_sheet[COL_TIME_COURSE] = (
        date_sheet["上课日期"].astype(str) + " "
        + date_sheet["上课时间"].astype(str)
        + date_sheet[COL_COURSE_NAME].astype(str)
    )

    capums_ana = (
        date_sheet.groupby(COL_CAMPUS, as_index=False)["场地费用"]
        .sum()
        .rename(columns={"场地费用": COL_VENUE_TOTAL})
    )
    date_sheet = date_sheet.drop(["场地费用合计", "场地编号", "周明细", "合计"], axis=1, errors="ignore")

    xwskjl_in = xwskjl_copy[xwskjl_copy[COL_STATUS] == COL_ATTENDED].copy()
    course_site_count = (
        xwskjl_in.groupby(COL_TIME_COURSE, as_index=False)
        .size()
        .rename(columns={"size": COL_COURSE_ATTENDANCE_COUNT})
    )
    campus_attendance = (
        xwskjl_in.groupby(COL_CAMPUS, as_index=False)
        .size()
        .rename(columns={"size": COL_CAMPUS_ATTENDANCE_TOTAL})
    )

    capums_ana = pd.merge(capums_ana, campus_attendance, on=COL_CAMPUS, how="left")
    date_sheet = pd.merge(date_sheet, course_site_count, on=COL_TIME_COURSE, how="left")
    capums_ana[COL_AVG_VENUE_COST] = capums_ana.apply(
        lambda x: _safe_div_float(x[COL_VENUE_TOTAL], x[COL_CAMPUS_ATTENDANCE_TOTAL]), axis=1
    )

    date_sheet[COL_COACH_NAME_ALT] = date_sheet[COL_COACH_NAME_ALT].str.replace(" ", "", regex=False)
    date_sheet[COL_CAMPUS_COACH] = date_sheet[COL_CAMPUS].astype(str) + "-" + date_sheet[COL_COACH_NAME_ALT].astype(str)
    df = (
        date_sheet.groupby(COL_CAMPUS_COACH, as_index=False)["场地费用"]
        .sum()
        .rename(columns={"场地费用": COL_VENUE_FEE})
    )
    df[COL_VENUE_FEE] = pd.to_numeric(df[COL_VENUE_FEE], errors="coerce").fillna(0).round(2)
    combined = pd.merge(combined, df, on=COL_CAMPUS_COACH, how="left")
    combined[COL_S3_VENUE_COST] = combined.apply(
        lambda x: _safe_div_float(x[COL_VENUE_FEE], x[COL_STUDENT_COUNT]), axis=1
    )
    combined[COL_COST_REVENUE_RATIO] = combined.apply(
        lambda x: _safe_div_str(x[COL_VENUE_FEE] + x[COL_TEACHING_FEE], x[COL_CONFIRMED_REVENUE]), axis=1
    )

    date_sheet[COL_COURSE_VENUE_COST] = date_sheet.apply(
        lambda x: _safe_div_float(x["场地费用"], x[COL_COURSE_ATTENDANCE_COUNT]), axis=1
    )
    date_sheet = pd.merge(date_sheet, capums_ana[[COL_CAMPUS, COL_AVG_VENUE_COST]], on=COL_CAMPUS, how="left")

    date_sheet_lower = (
        date_sheet[date_sheet[COL_COURSE_VENUE_COST] <= date_sheet[COL_AVG_VENUE_COST]]
        .groupby(COL_CAMPUS_COACH, as_index=False)[COL_COURSE_VENUE_COST]
        .count()
        .rename(columns={COL_COURSE_VENUE_COST: COL_BELOW_AVG_RATIO})
    )
    date_sheet_higher = (
        date_sheet[date_sheet[COL_COURSE_VENUE_COST] > date_sheet[COL_AVG_VENUE_COST] * 2]
        .groupby(COL_CAMPUS_COACH, as_index=False)[COL_COURSE_VENUE_COST]
        .count()
        .rename(columns={COL_COURSE_VENUE_COST: COL_ABOVE_2X_RATIO})
    )
    date_sheet_highest = (
        date_sheet.groupby(COL_CAMPUS_COACH, as_index=False)[COL_COURSE_VENUE_COST]
        .max()
        .rename(columns={COL_COURSE_VENUE_COST: "最高课程生均场地费"})
    )

    combined = pd.merge(combined, date_sheet_lower, on=COL_CAMPUS_COACH, how="left").fillna(
        {COL_BELOW_AVG_RATIO: 0}
    )
    combined = pd.merge(combined, date_sheet_higher, on=COL_CAMPUS_COACH, how="left").fillna(
        {COL_ABOVE_2X_RATIO: 0}
    )
    combined = pd.merge(combined, date_sheet_highest, on=COL_CAMPUS_COACH, how="left").fillna(
        {"最高课程生均场地费": 0}
    )

    combined[COL_BELOW_AVG_RATIO] = combined.apply(
        lambda x: _safe_div_str(x[COL_BELOW_AVG_RATIO], x[COL_CLASS_COUNT]), axis=1
    )
    combined[COL_ABOVE_2X_RATIO] = combined.apply(
        lambda x: _safe_div_str(x[COL_ABOVE_2X_RATIO], x[COL_CLASS_COUNT]), axis=1
    )
    combined[COL_MAX_COURSE_VENUE_RATIO] = combined.apply(
        lambda x: f"{_safe_div_float(x['最高课程生均场地费'], x[COL_S3_VENUE_COST]):.2f}倍", axis=1
    )

    last_month_ana[COL_CAMPUS] = last_month_ana[COL_CAMPUS].ffill()
    last_month_ana[COL_CAMPUS] = last_month_ana[COL_CAMPUS].replace("农都城校区", "农都城校区（篮球）")
    last_month_ana[COL_CAMPUS_COACH] = last_month_ana[COL_CAMPUS].astype(str) + "-" + last_month_ana[COL_COACH].astype(str)
    combined = pd.merge(
        combined,
        last_month_ana[[COL_CAMPUS_COACH, COL_S3_VENUE_COST]],
        on=COL_CAMPUS_COACH,
        how="left",
    ).rename(columns={
        f"{COL_S3_VENUE_COST}_y": COL_LAST_MONTH_VENUE_COST,
        f"{COL_S3_VENUE_COST}_x": COL_S3_VENUE_COST,
    })
    combined[COL_LAST_MONTH_VENUE_COST] = combined[COL_LAST_MONTH_VENUE_COST].fillna(0).round(2)
    combined[COL_S3_CHANGE] = combined.apply(
        lambda x: _safe_div_str(
            x[COL_S3_VENUE_COST] - x[COL_LAST_MONTH_VENUE_COST], x[COL_LAST_MONTH_VENUE_COST]
        ), axis=1
    )

    combined = combined.replace([np.inf, -np.inf], 0).fillna(0)
    return combined


def summarize_campus(group: pd.DataFrame, xwskjl: pd.DataFrame,
                     last_month_ana: pd.DataFrame) -> pd.Series:
    """添加校区汇总行"""
    total_classes = int(group[COL_CLASS_COUNT].sum())
    total_students = int(group[COL_STUDENT_COUNT].sum())
    avg_class_size = _safe_div_float(total_students, total_classes)

    current_campus = group[COL_CAMPUS].iloc[0]
    campus_attendance_total = xwskjl[xwskjl[COL_CAMPUS] == current_campus].shape[0]
    avg_attendance = _safe_div_str(total_students, campus_attendance_total)

    total_revenue = round(group[COL_CONFIRMED_REVENUE].sum(), 2)
    avg_price = _safe_div_float(total_revenue, total_students)
    total_small_classes = int(group[COL_LOW_CLASS_COUNT].sum())
    small_class_ratio = _safe_div_str(total_small_classes, total_classes)
    total_large_classes = int(group[COL_HIGH_CLASS_COUNT].sum())
    large_class_ratio = _safe_div_str(total_large_classes, total_classes)
    total_internal_classes = int(group[COL_INTERNAL_CLASSES].sum())
    total_teacher_fee = round(group[COL_TEACHING_FEE].sum(), 2)
    total_venue_fee = round(group[COL_VENUE_FEE].sum(), 1)
    avg_venue_cost_per_student = _safe_div_float(total_venue_fee, total_students)
    cost_revenue_ratio = _safe_div_str(total_venue_fee + total_teacher_fee, total_revenue)

    last_month_campus_data = last_month_ana[last_month_ana[COL_CAMPUS] == current_campus]
    if not last_month_campus_data.empty:
        total_venue_last = last_month_campus_data[COL_VENUE_FEE].sum()
        total_students_last = last_month_campus_data[COL_STUDENT_COUNT].sum()
        last_month_avg = _safe_div_float(total_venue_last, total_students_last)
    else:
        last_month_avg = 0.0

    s3_change = _safe_div_str(avg_venue_cost_per_student - last_month_avg, last_month_avg)

    return pd.Series({
        COL_CAMPUS: f"{current_campus}{SUMMARY_SUFFIX}",
        COL_CLASS_COUNT: total_classes,
        COL_STUDENT_COUNT: total_students,
        COL_AVG_CLASS_SIZE: avg_class_size,
        COL_ATTENDANCE_RATE: avg_attendance,
        COL_CONFIRMED_REVENUE: total_revenue,
        COL_AVG_COURSE_PRICE: avg_price,
        COL_LOW_CLASS_COUNT: total_small_classes,
        COL_LOW_CLASS_RATIO: small_class_ratio,
        COL_HIGH_CLASS_COUNT: total_large_classes,
        COL_HIGH_CLASS_RATIO: large_class_ratio,
        COL_INTERNAL_CLASSES: total_internal_classes,
        COL_TEACHING_FEE: total_teacher_fee,
        COL_VENUE_FEE: total_venue_fee,
        COL_S3_VENUE_COST: avg_venue_cost_per_student,
        COL_LAST_MONTH_VENUE_COST: last_month_avg,
        COL_COST_REVENUE_RATIO: cost_revenue_ratio,
        COL_S3_CHANGE: s3_change,
    }, dtype=object)


def summarize_total(combined: pd.DataFrame, xwskjl: pd.DataFrame,
                    last_month_ana: pd.DataFrame) -> pd.Series:
    """添加全部汇总行"""
    combined = combined[~combined[COL_CAMPUS].str.contains(PINGPONG)].copy()
    non_summary = combined[~combined[COL_CAMPUS].str.endswith(SUMMARY_SUFFIX, na=False)].copy()

    total_classes = int(non_summary[COL_CLASS_COUNT].sum())
    total_students = int(non_summary[COL_STUDENT_COUNT].sum())
    avg_class_size = _safe_div_float(total_students, total_classes)

    xwskjl_np = xwskjl[~xwskjl[COL_CAMPUS].str.contains(PINGPONG)].copy()
    total_possible = xwskjl_np.shape[0]
    total_attendance_rate = _safe_div_str(total_students, total_possible)

    total_revenue = round(non_summary[COL_CONFIRMED_REVENUE].sum(), 2)
    avg_price = _safe_div_float(total_revenue, total_students)
    total_small_classes = int(non_summary[COL_LOW_CLASS_COUNT].sum())
    small_class_ratio = _safe_div_str(total_small_classes, total_classes)
    total_large_classes = int(non_summary[COL_HIGH_CLASS_COUNT].sum())
    large_class_ratio = _safe_div_str(total_large_classes, total_classes)
    total_internal_classes = int(non_summary[COL_INTERNAL_CLASSES].sum())
    total_teacher_fee = round(non_summary[COL_TEACHING_FEE].sum(), 2)
    total_venue_fee = round(non_summary[COL_VENUE_FEE].sum(), 1)
    avg_venue_cost = _safe_div_float(total_venue_fee, total_students)
    cost_revenue_ratio = _safe_div_str(total_venue_fee + total_teacher_fee, total_revenue)

    last_month_data = last_month_ana[last_month_ana[COL_CAMPUS] == Z_TOTAL]
    if not last_month_data.empty:
        last_avg = round(float(last_month_data[COL_S3_VENUE_COST].values[0]), 2)
        s3_change = _safe_div_str(avg_venue_cost - last_avg, last_avg)
    else:
        s3_change = "0.00%"

    return pd.Series({
        COL_CAMPUS: Z_TOTAL,
        COL_CLASS_COUNT: total_classes,
        COL_STUDENT_COUNT: total_students,
        COL_AVG_CLASS_SIZE: avg_class_size,
        COL_ATTENDANCE_RATE: total_attendance_rate,
        COL_CONFIRMED_REVENUE: total_revenue,
        COL_AVG_COURSE_PRICE: avg_price,
        COL_LOW_CLASS_COUNT: total_small_classes,
        COL_LOW_CLASS_RATIO: small_class_ratio,
        COL_HIGH_CLASS_COUNT: total_large_classes,
        COL_HIGH_CLASS_RATIO: large_class_ratio,
        COL_INTERNAL_CLASSES: total_internal_classes,
        COL_TEACHING_FEE: total_teacher_fee,
        COL_VENUE_FEE: total_venue_fee,
        COL_S3_VENUE_COST: avg_venue_cost,
        COL_LAST_MONTH_VENUE_COST: float(last_month_data[COL_S3_VENUE_COST].values[0]) if not last_month_data.empty else 0.0,
        COL_CAMPUS_REVENUE_CONTRIB: "-",
        COL_COST_REVENUE_RATIO: cost_revenue_ratio,
        COL_S3_CHANGE: s3_change,
        COL_BELOW_AVG_RATIO: "-",
        COL_ABOVE_2X_RATIO: "-",
        COL_MAX_COURSE_VENUE_RATIO: "-",
    }, dtype=object)


# ──────────────────── Excel 导出 ────────────────────

def _generate_excel(combined: pd.DataFrame, df: pd.DataFrame) -> bytes:
    """生成双 Sheet Excel（主文件筛选列 + 完整数据），返回字节流"""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for sheet_name, data in [("综合统计", combined), ("综合统计_完整数据", df)]:
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
                max_w = max(_char_width(cell.value) for cell in col)
                ws.column_dimensions[col[0].column_letter].width = min(max_w + 3, 60)

    buf.seek(0)
    return buf.read()


# ──────────────────── 总函数 ────────────────────

def _extract_coach_stats(combined: pd.DataFrame) -> List[dict]:
    """从汇总前的 combined 提取每位教练的原始统计数据，供累积分析存库"""
    rows = []
    for _, row in combined.iterrows():
        rows.append({
            "campus": str(row.get(COL_CAMPUS, "") or ""),
            "coach": str(row.get(COL_COACH, "") or ""),
            "lessons": int(row.get(COL_CLASS_COUNT, 0) or 0),
            "actual_attendance": int(row.get(COL_ATTENDED_COUNT, 0) or 0),
            "expected_attendance": int(row.get(COL_TOTAL_EXPECTED, 0) or 0),
            "revenue": float(row.get(COL_CONFIRMED_REVENUE, 0) or 0),
            "site_cost": float(row.get(COL_VENUE_FEE, 0) or 0),
            "teaching_fee": float(row.get(COL_TEACHING_FEE, 0) or 0),
        })
    return rows


def _build_xwskjl_copy(
    skjl: pd.DataFrame, course_coach: pd.DataFrame, outside_keywords: List[str]
) -> pd.DataFrame:
    """从原始上课记录过滤校外课程，join 财务 session_map 获取教练和校区"""
    kw_pattern = "|".join(outside_keywords)
    raw_att = skjl[skjl[COL_COURSE_NAME].str.contains(kw_pattern, case=False, na=False)].copy()

    # 与财务侧保持一致的时加课拼接方式：日期 + 空格 + 时间 + 课程名
    raw_att["上课日期"] = raw_att[COL_COURSE_INFO].str.extract(r"(\d{4}-\d{2}-\d{2})")
    raw_att["上课时间"] = raw_att[COL_COURSE_INFO].str.extract(r"\d{4}-\d{2}-\d{2} (.+)")
    raw_att[COL_TIME_COURSE] = (
        raw_att["上课日期"].astype(str) + " "
        + raw_att["上课时间"].astype(str)
        + raw_att[COL_COURSE_NAME].astype(str)
    )

    # 通过财务 session_map join 获取教练和校区
    xwskjl_copy = pd.merge(
        raw_att,
        course_coach[[COL_TIME_COURSE, COL_COACH, COL_CAMPUS]],
        on=COL_TIME_COURSE,
        how="left",
    )
    xwskjl_copy[COL_CAMPUS_COACH] = (
        xwskjl_copy[COL_CAMPUS].astype(str) + "-" + xwskjl_copy[COL_COACH].astype(str)
    )
    return xwskjl_copy


def _run_analysis(
    skjl: pd.DataFrame,
    xwksf: pd.DataFrame,
    cw: pd.DataFrame,
    cdf_bytes: bytes,
    off_campus_coaches: List[str],
    last_month_ana: pd.DataFrame,
    outside_keywords: List[str],
) -> tuple:
    """串联所有子函数，返回 (combined筛选列, df完整数据, coach_stats)"""
    # 1. 财务处理（基底）
    xwcw, course_coach = process_finance_data(cw)

    # 2. 课次/人次/确收 全部来自财务
    combined = calculate_basic_stats(xwcw)
    combined = calculate_revenue(combined, xwcw)

    # 3. 构建 xwskjl_copy（上课记录 join 财务）仅用于到课率和班级规模
    xwskjl_copy = _build_xwskjl_copy(skjl, course_coach, outside_keywords)

    # 4. 到课率、班级规模来自 xwskjl_copy
    combined = calculate_attendance_rate(combined, xwskjl_copy)
    combined = analyze_class_size(combined, xwskjl_copy)
    combined = calculate_campus_contribution(combined)

    # 5. 校外教练校内课次 — xnskjl 内部派生
    kw_pattern = "|".join(outside_keywords)
    xnskjl = skjl[~skjl[COL_COURSE_NAME].str.contains(kw_pattern, case=False, na=False)].copy()
    xn_skjl = calculate_offcampus_in_campus(xnskjl, course_coach, off_campus_coaches)
    combined = pd.merge(combined, xn_skjl, on=COL_COACH, how="left")
    combined[COL_INTERNAL_CLASSES] = combined[COL_INTERNAL_CLASSES].fillna(0).astype(int)

    combined = merge_teaching_fee(combined, xwksf)

    # 6. 场地费 — 传入 xwskjl_copy（含时加课和校区教练）
    combined = site_cost(combined, cdf_bytes, xwskjl_copy, last_month_ana)
    combined = combined[~combined[COL_CAMPUS].str.contains(PINGPONG)].copy()

    coach_stats = _extract_coach_stats(combined)

    summary_rows = combined.groupby(COL_CAMPUS, group_keys=False).apply(
        lambda g: summarize_campus(g, xwskjl_copy, last_month_ana)
    ).reset_index(drop=True).fillna(" ")
    combined = pd.concat([combined, summary_rows], ignore_index=True)

    total_summary = summarize_total(combined, xwskjl_copy, last_month_ana).to_frame().T
    combined = pd.concat([combined, total_summary], ignore_index=True)

    df = combined.copy()
    combined = combined[FINAL_COLS].sort_values(
        [COL_CAMPUS, COL_CONFIRMED_REVENUE], ascending=[True, True]
    ).reset_index(drop=True)

    return combined, df, coach_stats


# ──────────────────── 公开 API ────────────────────

def preview_offcampus(skjl_bytes: bytes, cw_bytes: bytes) -> dict:
    """预览：从财务明细提取校外课程基本信息"""
    config = _load_config()
    outside_keywords = config["tools"]["outside_keywords"]

    skjl = _read_excel(skjl_bytes, expected_cols=_SKJL_EXPECTED_COLS)
    cw = _read_excel(cw_bytes, sheet_name="财务", expected_cols=_CW_EXPECTED_COLS)

    xwcw, course_coach = process_finance_data(cw)
    kw_pattern = "|".join(outside_keywords)
    offcampus_count = skjl[skjl[COL_COURSE_NAME].str.contains(kw_pattern, case=False, na=False)].shape[0]
    oncampus_count = skjl[~skjl[COL_COURSE_NAME].str.contains(kw_pattern, case=False, na=False)].shape[0]

    return {
        "offcampus_count": offcampus_count,
        "oncampus_count": oncampus_count,
        "total_count": len(skjl),
        "campuses": sorted(xwcw[COL_CAMPUS].dropna().unique().tolist()),
        "coaches": sorted(xwcw[COL_COACH].dropna().unique().tolist()),
    }


def process_offcampus(
    skjl_bytes: bytes,
    xwksf_bytes: bytes,
    cw_bytes: bytes,
    cdf_bytes: bytes,
    last_month_bytes: Optional[bytes] = None,
) -> dict:
    """完整分析，返回 {excel_bytes, sheets, summary}"""
    config = _load_config()
    outside_keywords = config["tools"]["outside_keywords"]
    off_campus_coaches = config["tools"]["offcampus_coaches"]

    skjl = _read_excel(skjl_bytes, expected_cols=_SKJL_EXPECTED_COLS)
    xwksf = _read_excel(xwksf_bytes)
    cw = _read_excel(cw_bytes, sheet_name="财务", expected_cols=_CW_EXPECTED_COLS)

    if last_month_bytes:
        last_month_ana = _read_excel(last_month_bytes, sheet_name="综合统计")
    else:
        last_month_ana = pd.DataFrame(columns=[
            COL_CAMPUS, COL_COACH, COL_VENUE_FEE, COL_STUDENT_COUNT, COL_S3_VENUE_COST
        ])

    combined, df, coach_stats = _run_analysis(
        skjl, xwksf, cw, cdf_bytes, off_campus_coaches, last_month_ana, outside_keywords
    )

    excel_bytes = _generate_excel(combined, df)
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    non_summary = combined[
        ~combined[COL_CAMPUS].astype(str).str.endswith(SUMMARY_SUFFIX) & (combined[COL_CAMPUS] != Z_TOTAL)
    ]

    kw_pattern = "|".join(outside_keywords)
    offcampus_count = skjl[skjl[COL_COURSE_NAME].str.contains(kw_pattern, case=False, na=False)].shape[0]

    return {
        "excel_bytes": excel_bytes,
        "sheets": ["综合统计", "综合统计_完整数据"],
        "summary": {
            "total_records": len(skjl),
            "offcampus_count": offcampus_count,
            "campus_count": len(non_summary[COL_CAMPUS].unique()) if len(non_summary) > 0 else 0,
            "coach_count": len(non_summary[COL_COACH].unique()) if len(non_summary) > 0 else 0,
            "total_revenue": float(non_summary[COL_CONFIRMED_REVENUE].sum()) if len(non_summary) > 0 else 0,
        },
        "coach_stats": coach_stats,
    }
