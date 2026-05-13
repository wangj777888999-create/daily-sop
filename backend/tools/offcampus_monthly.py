"""校外月度分析 — 独立数据源，4 个必传 + 1 个可选 Excel"""
import io
import os
import json
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment
from openpyxl.utils.dataframe import dataframe_to_rows

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "offcampus_output")


# ──────────────────── 工具函数 ────────────────────

def _load_config() -> dict:
    config_path = os.path.join(DATA_DIR, "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _read_excel(data: bytes, sheet_name: str = "Sheet1") -> pd.DataFrame:
    try:
        return pd.read_excel(io.BytesIO(data), sheet_name=sheet_name, engine="openpyxl")
    except Exception:
        return pd.read_excel(io.BytesIO(data), sheet_name=sheet_name, engine="xlrd")


# ──────────────────── 子函数 ────────────────────

def skjl_separate(skjl: pd.DataFrame, cw: pd.DataFrame, outside_keywords: List[str]) -> tuple:
    """按课程名关键词拆分校外/校内上课记录，校外记录附加校区和教练"""
    kw_pattern = "|".join(outside_keywords)
    xwskjl = skjl[skjl["课程名称"].str.contains(kw_pattern, case=False, na=False)].copy()
    xwskjl["时加课"] = xwskjl["上课信息"].astype(str) + xwskjl["课程名称"].astype(str)

    xwcw, course_coach = process_finance_data(cw)

    cw_copy = cw.copy()
    cw_copy["时加课"] = (
        cw_copy["上课日期"].astype(str) + " "
        + cw_copy["上课时间"].astype(str)
        + cw_copy["课程名称"].astype(str)
    )
    cw_copy = cw_copy.drop_duplicates(subset=["时加课"])[["时加课", "校区"]].copy()

    xwskjl = pd.merge(xwskjl, cw_copy[["时加课", "校区"]], on="时加课", how="left")
    xwskjl = pd.merge(xwskjl, course_coach[["时加课", "教练"]], on="时加课", how="left")
    xwskjl.rename(columns={"订单类型": "校区"}, inplace=True)
    xwskjl_copy = xwskjl.drop(columns=["时加课"]).copy()

    xnskjl = skjl[~skjl["课程名称"].str.contains(kw_pattern, case=False, na=False)].copy()
    return xwskjl_copy, xnskjl


def process_finance_data(cw: pd.DataFrame) -> tuple:
    """处理财务数据：校外财务表（球馆学员）+ 课程-教练映射"""
    xwcw = cw[cw["学员类型"] == "球馆学员"].copy()
    xwcw.rename(columns={"订单类型": "校区"}, inplace=True)

    cw_copy = cw.copy()
    cw_copy["时加课"] = (
        cw_copy["上课日期"].astype(str) + " "
        + cw_copy["上课时间"].astype(str)
        + cw_copy["课程名称"].astype(str)
    )
    course_coach = cw_copy.drop_duplicates(subset=["时加课"])[["时加课", "教练"]].copy()
    return xwcw, course_coach


def calculate_basic_stats(xwskjl: pd.DataFrame) -> tuple:
    """计算上课节次、人次、平均课堂人次"""
    xwskjl_copy = xwskjl.copy()
    xwskjl_copy["时加课"] = xwskjl_copy["上课信息"].astype(str) + xwskjl_copy["课程名称"].astype(str)
    xwskjl_copy["校区教练"] = xwskjl_copy["校区"].astype(str) + "-" + xwskjl_copy["教练"].astype(str)

    xwskjl_in = xwskjl_copy[xwskjl_copy["状态"] == "已到"].copy()
    xwskjl_in["校区教练"] = xwskjl_in["校区"].astype(str) + "-" + xwskjl_in["教练"].astype(str)

    campus_course = (
        xwskjl_in.drop_duplicates(subset=["时加课"])
        .groupby("校区教练", as_index=False)["时加课"]
        .nunique()
        .rename(columns={"时加课": "上课节次"})
    )
    campus_people = (
        xwskjl_in.groupby("校区教练", as_index=False)
        .size()
        .rename(columns={"size": "上课人次"})
    )

    combined = pd.merge(campus_course, campus_people, on="校区教练", how="outer")
    combined["上课节次"] = combined["上课节次"].fillna(0).astype(int)
    combined["上课人次"] = combined["上课人次"].fillna(0).astype(int)
    combined[["校区", "教练"]] = combined["校区教练"].str.split("-", expand=True)
    combined["平均课堂人次"] = combined.apply(
        lambda x: round(x["上课人次"] / x["上课节次"], 2) if x["上课节次"] != 0 else 0, axis=1
    )
    return combined, xwskjl_copy


def calculate_attendance_rate(combined: pd.DataFrame, xwskjl_copy: pd.DataFrame) -> pd.DataFrame:
    """计算到课率（排除私教课程）"""
    xwskjl_filtered = xwskjl_copy[
        ~xwskjl_copy["课程名称"].str.contains("私教", case=False, na=False)
    ].copy()
    xwskjl_in = xwskjl_filtered[xwskjl_filtered["状态"] == "已到"].copy()

    total_persons = (
        xwskjl_filtered.groupby("校区教练", as_index=False)
        .size()
        .rename(columns={"size": "总应到人数"})
    )
    attended_persons = (
        xwskjl_in.groupby("校区教练", as_index=False)
        .size()
        .rename(columns={"size": "已到人数"})
    )

    attendance = pd.merge(total_persons, attended_persons, on="校区教练", how="left")
    attendance["已到人数"] = attendance["已到人数"].fillna(0)
    attendance["到课率"] = attendance.apply(
        lambda x: f"{x['已到人数'] / x['总应到人数'] * 100:.2f}%"
        if x["总应到人数"] != 0
        else "0.00%",
        axis=1,
    )

    combined = pd.merge(combined, attendance[["校区教练", "到课率"]], on="校区教练", how="left")
    return combined


def calculate_revenue(combined: pd.DataFrame, xwcw: pd.DataFrame) -> pd.DataFrame:
    """统计确认收入与平均课程单价"""
    xwcw_copy = xwcw.copy()
    xwcw_copy["校区教练"] = xwcw_copy["校区"].astype(str) + "-" + xwcw_copy["教练"].astype(str)

    campus_revenue = (
        xwcw_copy.groupby("校区教练", as_index=False)["课程单价"]
        .sum()
        .rename(columns={"课程单价": "确认收入"})
    )
    campus_revenue["确认收入"] = campus_revenue["确认收入"].fillna(0).round(2)

    combined = pd.merge(combined, campus_revenue[["校区教练", "确认收入"]], on="校区教练", how="left")
    combined["确认收入"] = combined["确认收入"].fillna(0).round(2)
    combined["平均课程单价"] = combined.apply(
        lambda x: round(x["确认收入"] / x["上课人次"], 2) if x["上课人次"] != 0 else 0, axis=1
    )
    combined.rename(columns={"上课节次": "课次"}, inplace=True)
    return combined


def analyze_class_size(combined: pd.DataFrame, xwskjl_copy: pd.DataFrame) -> pd.DataFrame:
    """统计5人及以下、10人及以上课程数及比例"""
    xwskjl_filtered = xwskjl_copy[
        ~xwskjl_copy["课程名称"].str.contains("私教", case=False, na=False)
    ].copy()

    ca_grouped = xwskjl_filtered.groupby(["上课信息", "校区教练"])["状态"].apply(list).reset_index()
    ca_container = defaultdict(lambda: {"total": 0, "low": 0, "high": 0})

    for _, row in ca_grouped.iterrows():
        present = sum(1 for s in row["状态"] if s == "已到")
        ca_container[row["校区教练"]]["total"] += 1
        if present <= 5:
            ca_container[row["校区教练"]]["low"] += 1
        if present >= 10:
            ca_container[row["校区教练"]]["high"] += 1

    ca_df = pd.DataFrame([
        {
            "校区教练": k,
            "5人及以下课程数": v["low"],
            "5人及以下比例": f"{v['low'] / v['total'] * 100:.2f}%" if v["total"] != 0 else "0.00%",
            "10人及以上课程数": v["high"],
            "10人及以上比例": f"{v['high'] / v['total'] * 100:.2f}%" if v["total"] != 0 else "0.00%",
        }
        for k, v in ca_container.items()
    ])

    target_cols = ["5人及以下课程数", "5人及以下比例", "10人及以上课程数", "10人及以上比例"]
    combined = combined.drop(columns=[c for c in target_cols if c in combined.columns], errors="ignore")
    return pd.merge(combined, ca_df, on="校区教练", how="left").fillna({
        "5人及以下课程数": 0,
        "10人及以上课程数": 0,
        "5人及以下比例": "0.00%",
        "10人及以上比例": "0.00%",
    })


def calculate_campus_contribution(combined: pd.DataFrame) -> pd.DataFrame:
    """计算教练对本校区的营收贡献比"""
    campus_total = (
        combined.groupby("校区", as_index=False)["确认收入"]
        .sum()
        .rename(columns={"确认收入": "校区总营收"})
    )
    combined = pd.merge(combined, campus_total, on="校区", how="left")
    combined["本校区确收贡献比"] = combined.apply(
        lambda x: f"{x['确认收入'] / x['校区总营收'] * 100:.2f}%"
        if x["校区总营收"] != 0
        else "0.00%",
        axis=1,
    )
    return combined.drop(columns="校区总营收")


def calculate_offcampus_in_campus(
    xnskjl: pd.DataFrame, course_coach: pd.DataFrame, off_campus_coaches: List[str]
) -> pd.DataFrame:
    """统计校外教练在校内的上课节次"""
    xnskjl_copy = xnskjl.copy()
    xnskjl_copy["时加课"] = xnskjl_copy["上课信息"].astype(str) + xnskjl_copy["课程名称"].astype(str)
    xnskjl_unique = xnskjl_copy.drop_duplicates(subset=["时加课"]).copy()
    xnskjl_unique = pd.merge(xnskjl_unique, course_coach, on="时加课", how="left")
    return (
        xnskjl_unique[xnskjl_unique["教练"].isin(off_campus_coaches)]
        .groupby("教练", as_index=False)
        .size()
        .rename(columns={"size": "校内上课节次"})
    )


def merge_teaching_fee(combined: pd.DataFrame, xwksf: pd.DataFrame) -> pd.DataFrame:
    """合并校外课时费数据"""
    xwksf_copy = xwksf.copy()
    xwksf_copy["校区教练"] = xwksf_copy["校区"].astype(str) + "-" + xwksf_copy["教练"].astype(str)
    if "应发课时费" in combined.columns:
        combined = combined.drop(columns=["应发课时费"], errors="ignore")
    combined = pd.merge(combined, xwksf_copy[["校区教练", "应发课时费"]], on="校区教练", how="left")
    combined["应发课时费"] = combined["应发课时费"].fillna(0).round(2)
    return combined


def site_cost(combined: pd.DataFrame, cdf_bytes: bytes, xwskjl: pd.DataFrame,
              last_month_ana: pd.DataFrame) -> pd.DataFrame:
    """场地费及相关费用计算"""
    excel_file = pd.ExcelFile(io.BytesIO(cdf_bytes))

    sheet_data = []
    campus_name_map = {
        "农都校区": "农都城校区（篮球）",
        "滨江校区": "滨江天街校区",
        "西溪校区": "西溪天街校区",
    }
    for sheet_name in excel_file.sheet_names:
        df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
        df = df.drop(index=0).reset_index(drop=True)
        df.columns = df.iloc[0]
        df = df.drop(index=0).reset_index(drop=True)
        if sheet_name in campus_name_map:
            df["校区"] = campus_name_map[sheet_name]
        sheet_data.append(df)

    _, xwskjl_copy = calculate_basic_stats(xwskjl)
    date_sheet = pd.concat(sheet_data, ignore_index=True)
    date_sheet["上课日期"] = pd.to_datetime(date_sheet["上课日期"], errors="coerce").dt.strftime("%Y-%m-%d")
    date_sheet["上课时间"] = date_sheet["上课时间"].str.replace("--", "-", regex=False)
    date_sheet["时加课"] = (
        date_sheet["上课日期"].astype(str) + " "
        + date_sheet["上课时间"].astype(str)
        + date_sheet["课程名称"].astype(str)
    )

    capums_ana = (
        date_sheet.groupby("校区", as_index=False)["场地费用"]
        .sum()
        .rename(columns={"场地费用": "校区场地费合计"})
    )
    date_sheet = date_sheet.drop(["场地费用合计", "场地编号", "周明细", "合计"], axis=1, errors="ignore")

    xwskjl_in = xwskjl_copy[xwskjl_copy["状态"] == "已到"].copy()
    course_site_count = (
        xwskjl_in.groupby("时加课", as_index=False)
        .size()
        .rename(columns={"size": "上课人数"})
    )
    campus_attendance = (
        xwskjl_in.groupby("校区", as_index=False)
        .size()
        .rename(columns={"size": "校区总到课人次"})
    )

    capums_ana = pd.merge(capums_ana, campus_attendance, on="校区", how="left")
    date_sheet = pd.merge(date_sheet, course_site_count, on="时加课", how="left")
    capums_ana["校区生均场地费"] = capums_ana.apply(
        lambda x: round(x["校区场地费合计"] / x["校区总到课人次"], 2)
        if x["校区总到课人次"] != 0
        else 0,
        axis=1,
    )

    date_sheet["教练员"] = date_sheet["教练员"].str.replace(" ", "", regex=False)
    date_sheet["校区教练"] = date_sheet["校区"].astype(str) + "-" + date_sheet["教练员"].astype(str)
    df = (
        date_sheet.groupby("校区教练", as_index=False)["场地费用"]
        .sum()
        .rename(columns={"场地费用": "场地费"})
    )
    df["场地费"] = pd.to_numeric(df["场地费"], errors="coerce").fillna(0).round(2)
    combined = pd.merge(combined, df, on="校区教练", how="left")
    combined["S3:场地费生均成本"] = combined.apply(
        lambda x: round(x["场地费"] / x["上课人次"], 2) if x["上课人次"] != 0 else "0", axis=1
    )
    combined["(场地费+课时费)/确收"] = combined.apply(
        lambda x: f"{(x['场地费'] + x['应发课时费']) / x['确认收入'] * 100:.2f}%"
        if x["确认收入"] != 0
        else "0",
        axis=1,
    )

    date_sheet["课程生均场地费"] = date_sheet.apply(
        lambda x: round(x["场地费用"] / x["上课人数"], 2) if x["上课人数"] != 0 else 0, axis=1
    )
    date_sheet = pd.merge(date_sheet, capums_ana[["校区", "校区生均场地费"]], on="校区", how="left")

    date_sheet_lower = (
        date_sheet[date_sheet["课程生均场地费"] <= date_sheet["校区生均场地费"]]
        .groupby("校区教练", as_index=False)["课程生均场地费"]
        .count()
        .rename(columns={"课程生均场地费": "低于校区生均场地费占比"})
    )
    date_sheet_higher = (
        date_sheet[date_sheet["课程生均场地费"] > date_sheet["校区生均场地费"] * 2]
        .groupby("校区教练", as_index=False)["课程生均场地费"]
        .count()
        .rename(columns={"课程生均场地费": "高于校区生均场地费1倍占比"})
    )
    date_sheet_highest = (
        date_sheet.groupby("校区教练", as_index=False)["课程生均场地费"]
        .max()
        .rename(columns={"课程生均场地费": "最高课程生均场地费"})
    )

    combined = pd.merge(combined, date_sheet_lower, on="校区教练", how="left").fillna(
        {"低于校区生均场地费占比": 0}
    )
    combined = pd.merge(combined, date_sheet_higher, on="校区教练", how="left").fillna(
        {"高于校区生均场地费1倍占比": 0}
    )
    combined = pd.merge(combined, date_sheet_highest, on="校区教练", how="left").fillna(
        {"最高课程生均场地费": 0}
    )

    combined["低于校区生均场地费占比"] = combined.apply(
        lambda x: f"{x['低于校区生均场地费占比'] / x['课次'] * 100:.2f}%"
        if x["课次"] != 0
        else "0",
        axis=1,
    )
    combined["高于校区生均场地费1倍占比"] = combined.apply(
        lambda x: f"{x['高于校区生均场地费1倍占比'] / x['课次'] * 100:.2f}%"
        if x["课次"] != 0
        else "0",
        axis=1,
    )
    combined["最高课程生均场地费/s3"] = combined.apply(
        lambda x: f"{x['最高课程生均场地费'] / x['S3:场地费生均成本']:.2f}倍", axis=1
    )

    last_month_ana["校区"] = last_month_ana["校区"].ffill()
    last_month_ana["校区"] = last_month_ana["校区"].replace("农都城校区", "农都城校区（篮球）")
    last_month_ana["校区教练"] = last_month_ana["校区"].astype(str) + "-" + last_month_ana["教练"].astype(str)
    combined = pd.merge(
        combined,
        last_month_ana[["校区教练", "S3:场地费生均成本"]],
        on="校区教练",
        how="left",
    ).rename(columns={
        "S3:场地费生均成本_y": "上月场地费生均成本",
        "S3:场地费生均成本_x": "S3:场地费生均成本",
    })
    combined["上月场地费生均成本"] = combined["上月场地费生均成本"].round(2)
    combined["s3较上月变化"] = combined.apply(
        lambda x: f"{(x['S3:场地费生均成本'] - x['上月场地费生均成本']) / x['上月场地费生均成本'] * 100:.2f}%"
        if x["上月场地费生均成本"] != 0
        else "0",
        axis=1,
    )
    return combined


def summarize_campus(group: pd.DataFrame, xwskjl: pd.DataFrame,
                     last_month_ana: pd.DataFrame) -> pd.Series:
    """添加校区汇总行"""
    total_classes = int(group["课次"].sum())
    total_students = int(group["上课人次"].sum())
    avg_class_size = round(total_students / total_classes, 2) if total_classes > 0 else 0.00

    current_campus = group["校区"].iloc[0]
    campus_attendance_total = xwskjl[xwskjl["校区"] == current_campus].shape[0]
    if campus_attendance_total > 0:
        avg_attendance = f"{total_students / campus_attendance_total * 100:.2f}%"
    else:
        avg_attendance = "0.00%"

    total_revenue = round(group["确认收入"].sum(), 2)
    avg_price = round(total_revenue / total_students, 2) if total_students > 0 else 0.00
    total_small_classes = int(group["5人及以下课程数"].sum())
    small_class_ratio = (
        f"{total_small_classes / total_classes * 100:.2f}%" if total_classes > 0 else "0.00%"
    )
    total_large_classes = int(group["10人及以上课程数"].sum())
    large_class_ratio = (
        f"{total_large_classes / total_classes * 100:.2f}%" if total_classes > 0 else "0.00%"
    )
    total_internal_classes = int(group["校内上课节次"].sum())
    total_teacher_fee = round(group["应发课时费"].sum(), 2)
    total_venue_fee = round(group["场地费"].sum(), 1)
    avg_venue_cost_per_student = (
        round(total_venue_fee / total_students, 2) if total_students > 0 else 0.00
    )
    cost_revenue_ratio = (
        f"{(total_venue_fee + total_teacher_fee) / total_revenue * 100:.2f}%"
        if total_revenue > 0
        else "0.00%"
    )

    last_month_campus_data = last_month_ana[last_month_ana["校区"] == current_campus]
    if not last_month_campus_data.empty:
        total_venue_last = last_month_campus_data["场地费"].sum()
        total_students_last = last_month_campus_data["上课人次"].sum()
        last_month_avg = round(total_venue_last / total_students_last, 2) if total_students_last > 0 else 0.0
    else:
        last_month_avg = 0.0

    if abs(last_month_avg) < 1e-6:
        s3_change = "0.00%"
    else:
        s3_change = f"{(avg_venue_cost_per_student - last_month_avg) / last_month_avg * 100:.2f}%"

    return pd.Series({
        "校区": f"{current_campus}-汇总",
        "课次": total_classes,
        "上课人次": total_students,
        "平均课堂人次": avg_class_size,
        "到课率": avg_attendance,
        "确认收入": total_revenue,
        "平均课程单价": avg_price,
        "5人及以下课程数": total_small_classes,
        "5人及以下比例": small_class_ratio,
        "10人及以上课程数": total_large_classes,
        "10人及以上比例": large_class_ratio,
        "校内上课节次": total_internal_classes,
        "应发课时费": total_teacher_fee,
        "场地费": total_venue_fee,
        "S3:场地费生均成本": avg_venue_cost_per_student,
        "上月场地费生均成本": last_month_avg,
        "(场地费+课时费)/确收": cost_revenue_ratio,
        "s3较上月变化": s3_change,
    }, dtype=object)


def summarize_total(combined: pd.DataFrame, xwskjl: pd.DataFrame,
                    last_month_ana: pd.DataFrame) -> pd.Series:
    """添加全部汇总行"""
    combined = combined[~combined["校区"].str.contains("乒乓球")].copy()
    non_summary = combined[~combined["校区"].str.endswith("-汇总", na=False)].copy()

    total_classes = int(non_summary["课次"].sum())
    total_students = int(non_summary["上课人次"].sum())
    avg_class_size = round(total_students / total_classes, 2) if total_classes > 0 else 0.00

    xwskjl_np = xwskjl[~xwskjl["校区"].str.contains("乒乓球")].copy()
    total_possible = xwskjl_np.shape[0]
    total_attendance_rate = (
        f"{total_students / total_possible * 100:.2f}%" if total_possible > 0 else "0.00%"
    )

    total_revenue = round(non_summary["确认收入"].sum(), 2)
    avg_price = round(total_revenue / total_students, 2) if total_students > 0 else 0.00
    total_small_classes = int(non_summary["5人及以下课程数"].sum())
    small_class_ratio = (
        f"{total_small_classes / total_classes * 100:.2f}%" if total_classes > 0 else "0.00%"
    )
    total_large_classes = int(non_summary["10人及以上课程数"].sum())
    large_class_ratio = (
        f"{total_large_classes / total_classes * 100:.2f}%" if total_classes > 0 else "0.00%"
    )
    total_internal_classes = int(non_summary["校内上课节次"].sum())
    total_teacher_fee = round(non_summary["应发课时费"].sum(), 2)
    total_venue_fee = round(non_summary["场地费"].sum(), 1)
    avg_venue_cost = round(total_venue_fee / total_students, 2) if total_students > 0 else 0.00
    cost_revenue_ratio = (
        f"{(total_venue_fee + total_teacher_fee) / total_revenue * 100:.2f}%"
        if total_revenue > 0
        else "0.00%"
    )

    last_month_data = last_month_ana[last_month_ana["校区"] == "Z总计"]
    if not last_month_data.empty:
        last_avg = round(float(last_month_data["S3:场地费生均成本"].values[0]), 2)
        s3_change = (
            f"{(avg_venue_cost - last_avg) / last_avg * 100:.2f}%" if last_avg != 0 else "0.00%"
        )
    else:
        s3_change = "0.00%"

    return pd.Series({
        "校区": "Z总计",
        "课次": total_classes,
        "上课人次": total_students,
        "平均课堂人次": avg_class_size,
        "到课率": total_attendance_rate,
        "确认收入": total_revenue,
        "平均课程单价": avg_price,
        "5人及以下课程数": total_small_classes,
        "5人及以下比例": small_class_ratio,
        "10人及以上课程数": total_large_classes,
        "10人及以上比例": large_class_ratio,
        "校内上课节次": total_internal_classes,
        "应发课时费": total_teacher_fee,
        "场地费": total_venue_fee,
        "S3:场地费生均成本": avg_venue_cost,
        "上月场地费生均成本": float(last_month_data["S3:场地费生均成本"].values[0]) if not last_month_data.empty else 0.0,
        "本校区营收贡献比": "-",
        "(场地费+课时费)/确收": cost_revenue_ratio,
        "s3较上月变化": s3_change,
        "低于校区生均场地费占比": "-",
        "高于校区生均场地费1倍占比": "-",
        "最高课程生均场地费/s3": "-",
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

def _run_analysis(
    xwskjl: pd.DataFrame,
    xnskjl: pd.DataFrame,
    xwksf: pd.DataFrame,
    cw: pd.DataFrame,
    cdf_bytes: bytes,
    off_campus_coaches: List[str],
    last_month_ana: pd.DataFrame,
) -> tuple:
    """串联所有子函数，返回 (combined筛选列, df完整数据)"""
    xwcw, course_coach = process_finance_data(cw)

    combined, xwskjl_copy = calculate_basic_stats(xwskjl)
    combined = calculate_attendance_rate(combined, xwskjl_copy)
    combined = calculate_revenue(combined, xwcw)
    combined = analyze_class_size(combined, xwskjl_copy)
    combined = calculate_campus_contribution(combined)

    xn_skjl = calculate_offcampus_in_campus(xnskjl, course_coach, off_campus_coaches)
    combined = pd.merge(combined, xn_skjl, on="教练", how="left")
    combined["校内上课节次"] = combined["校内上课节次"].fillna(0).astype(int)

    combined = merge_teaching_fee(combined, xwksf)

    combined = site_cost(combined, cdf_bytes, xwskjl, last_month_ana)
    combined = combined[~combined["校区"].str.contains("乒乓球")].copy()

    summary_rows = combined.groupby("校区", group_keys=False).apply(
        lambda g: summarize_campus(g, xwskjl_copy, last_month_ana)
    ).reset_index(drop=True).fillna(" ")
    combined = pd.concat([combined, summary_rows], ignore_index=True)

    total_summary = summarize_total(combined, xwskjl, last_month_ana).to_frame().T
    combined = pd.concat([combined, total_summary], ignore_index=True)

    final_cols = [
        "校区", "教练", "课次", "上课人次", "平均课堂人次", "到课率",
        "确认收入", "平均课程单价", "场地费", "应发课时费", "S3:场地费生均成本",
        "(场地费+课时费)/确收", "本校区营收贡献比", "校内上课节次",
        "5人及以下课程数", "5人及以下比例", "10人及以上课程数", "10人及以上比例",
        "上月场地费生均成本", "s3较上月变化", "低于校区生均场地费占比",
        "高于校区生均场地费1倍占比", "最高课程生均场地费/s3",
    ]
    df = combined.copy()
    combined = combined[final_cols].sort_values(
        ["校区", "确认收入"], ascending=[True, True]
    ).reset_index(drop=True)

    return combined, df


# ──────────────────── 公开 API ────────────────────

def preview_offcampus(skjl_bytes: bytes, cw_bytes: bytes) -> dict:
    """预览：拆分校内外记录，返回统计"""
    config = _load_config()
    outside_keywords = config["tools"]["outside_keywords"]

    skjl = _read_excel(skjl_bytes)
    cw = _read_excel(cw_bytes, sheet_name="财务")

    xwskjl, xnskjl = skjl_separate(skjl, cw, outside_keywords)

    return {
        "offcampus_count": len(xwskjl),
        "oncampus_count": len(xnskjl),
        "total_count": len(skjl),
        "campuses": sorted(xwskjl["校区"].dropna().unique().tolist()) if "校区" in xwskjl.columns else [],
        "coaches": sorted(xwskjl["教练"].dropna().unique().tolist()) if "教练" in xwskjl.columns else [],
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

    skjl = _read_excel(skjl_bytes)
    xwksf = _read_excel(xwksf_bytes)
    cw = _read_excel(cw_bytes, sheet_name="财务")

    xwskjl, xnskjl = skjl_separate(skjl, cw, outside_keywords)

    if last_month_bytes:
        last_month_ana = _read_excel(last_month_bytes, sheet_name="综合统计")
    else:
        last_month_ana = pd.DataFrame(columns=[
            "校区", "教练", "场地费", "上课人次", "S3:场地费生均成本"
        ])

    combined, df = _run_analysis(xwskjl, xnskjl, xwksf, cw, cdf_bytes, off_campus_coaches, last_month_ana)

    excel_bytes = _generate_excel(combined, df)

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    non_summary = combined[
        ~combined["校区"].astype(str).str.endswith("-汇总") & (combined["校区"] != "Z总计")
    ]

    return {
        "excel_bytes": excel_bytes,
        "sheets": ["综合统计", "综合统计_完整数据"],
        "summary": {
            "total_records": len(xwskjl) + len(xnskjl),
            "offcampus_count": len(xwskjl),
            "campus_count": len(non_summary["校区"].unique()) if len(non_summary) > 0 else 0,
            "coach_count": len(non_summary["教练"].unique()) if len(non_summary) > 0 else 0,
            "total_revenue": float(non_summary["确认收入"].sum()) if len(non_summary) > 0 else 0,
        },
    }
