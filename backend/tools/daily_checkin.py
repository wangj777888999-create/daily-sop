import io
import json
import os
import logging
from typing import Dict, List, Tuple
from datetime import date

import pandas as pd
from openpyxl.styles import PatternFill, Alignment
from openpyxl import Workbook
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "config.json")


def _load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        raise RuntimeError(f"配置文件缺失，请确保 data/config.json 存在: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def preview_files(coach_bytes: bytes, finance_bytes: bytes) -> dict:
    """Parse uploaded Excel bytes and return preview (first 50 rows + column validation)."""
    coach_df = pd.read_excel(io.BytesIO(coach_bytes), sheet_name="教练签到")
    finance_df = pd.read_excel(io.BytesIO(finance_bytes), sheet_name="财务")

    # Skip header rows like the original script
    coach_data = coach_df.iloc[2:].copy()
    coach_data.columns = coach_df.iloc[1].values

    finance_data = finance_df.iloc[3:].copy()
    finance_data.columns = [
        '学员类型', '学员姓名', '订单类型', '课包名称', '订单金额', '优惠金额',
        '付款金额', '课包课次', '课包赠送课次', '课包已上总课次', '已确认总收入',
        '退款金额', '退款确认收入金额', '课程名称', '课程明细_换班前课程',
        '课程明细_兑换金额', '课程明细_课程单价', '课程明细_总课次(缴费总课次)',
        '课程明细_赠送课次', '课程明细_已上总课次', '课程明细_已确认总收入',
        '课程明细_剩余总课次', '课程明细_总课次(选定时间)', '课程明细_已上课次（选定时间）',
        '课程明细_已确认收入（选定时间）', '课程明细_剩余课次（选定时间）', '课程明细_已确认收入的详情'
    ]

    return {
        "coach_columns": list(coach_data.columns),
        "coach_rows": coach_data.head(50).fillna("").to_dict(orient="records"),
        "coach_total": len(coach_data),
        "finance_columns": list(finance_data.columns),
        "finance_rows": finance_data.head(50).fillna("").to_dict(orient="records"),
        "finance_total": len(finance_data),
    }


def process_files(coach_bytes: bytes, finance_bytes: bytes, check_date: str = None) -> dict:
    """Process coach check-in + finance data. Returns {records, excel_bytes, summary}."""
    config = _load_config()
    dept_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        config["tools"]["department_mapping"]
    )

    # Parse coach data
    coach_df = pd.read_excel(io.BytesIO(coach_bytes), sheet_name="教练签到")
    coach_data = coach_df.iloc[2:].copy()
    coach_data.columns = coach_df.iloc[1].values
    coach_data = coach_data.query("课程类型 == '学校课程'").drop(columns='场馆名称', errors='ignore')

    # Parse finance data
    finance_df = pd.read_excel(io.BytesIO(finance_bytes), sheet_name="财务")
    finance_data = finance_df.iloc[3:].copy()
    finance_data.columns = [
        '学员类型', '学员姓名', '订单类型', '课包名称', '订单金额', '优惠金额',
        '付款金额', '课包课次', '课包赠送课次', '课包已上总课次', '已确认总收入',
        '退款金额', '退款确认收入金额', '课程名称', '课程明细_换班前课程',
        '课程明细_兑换金额', '课程明细_课程单价', '课程明细_总课次(缴费总课次)',
        '课程明细_赠送课次', '课程明细_已上总课次', '课程明细_已确认总收入',
        '课程明细_剩余总课次', '课程明细_总课次(选定时间)', '课程明细_已上课次（选定时间）',
        '课程明细_已确认收入（选定时间）', '课程明细_剩余课次（选定时间）', '课程明细_已确认收入的详情'
    ]

    numeric_cols = ['课程明细_已确认收入（选定时间）', '课程明细_已上课次（选定时间）', '课程明细_总课次(选定时间)']
    for col in numeric_cols:
        finance_data[col] = pd.to_numeric(finance_data[col], errors='coerce').fillna(0)

    fi = finance_data.groupby('课程名称').agg(
        实际上课人次=('课程明细_已上课次（选定时间）', 'sum'),
        课程应到人次=('课程明细_总课次(选定时间)', 'sum'),
        确认收入=('课程明细_已确认收入（选定时间）', 'sum')
    ).reset_index()

    # Load department mapping
    dept_df = pd.read_excel(dept_path, sheet_name='Sheet1')
    department = dept_df.rename(columns={'学校': '学校名称'})

    # Merge all data
    merged = pd.merge(coach_data, department[['学校名称', '部门']], on='学校名称', how='left')
    result = pd.merge(merged, fi, on='课程名称', how='left')

    # 左连接后财务列可能为 NaN（课程在财务表中无匹配），统一填 0
    for col in ['实际上课人次', '课程应到人次', '确认收入']:
        if col in result.columns:
            result[col] = result[col].fillna(0)

    # Reorder columns
    new_order = ['部门']
    for col in result.columns:
        if col not in new_order and col not in ['实际上课人次', '课程应到人次', '确认收入']:
            new_order.append(col)
    if '教练姓名' in new_order:
        coach_index = new_order.index('教练姓名')
        new_order.insert(coach_index + 1, '实际上课人次')
        new_order.insert(coach_index + 2, '课程应到人次')
        new_order.insert(coach_index + 3, '确认收入')
    else:
        new_order.extend(['实际上课人次', '课程应到人次', '确认收入'])

    result = result[new_order].sort_values(by='部门', na_position='last')

    # Determine check_date
    if not check_date:
        check_date = str(date.today())

    # Convert to records for SQLite
    records = []
    for _, row in result.iterrows():
        records.append({
            "check_date": check_date,
            "department": str(row.get("部门", "")),
            "school_name": str(row.get("学校名称", "")),
            "course_type": str(row.get("课程类型", "")),
            "course_name": str(row.get("课程名称", "")),
            "coach_name": str(row.get("教练姓名", "")),
            "course_date": str(row.get("课程日期", "")),
            "start_time": str(row.get("开课时间", "")),
            "end_time": str(row.get("下课时间", "")),
            "sign_in_time": str(row.get("签到时间", "")),
            "sign_out_time": str(row.get("签退时间", "")),
            "sign_status": str(row.get("签到状态", "")),
            "actual_count": int(pd.to_numeric(row.get("实际上课人次", 0), errors='coerce') or 0),
            "expected_count": int(pd.to_numeric(row.get("课程应到人次", 0), errors='coerce') or 0),
            "confirmed_revenue": float(pd.to_numeric(row.get("确认收入", 0), errors='coerce') or 0),
        })

    # Generate formatted Excel
    excel_bytes = _generate_excel(result)

    # Summary
    status_col = None
    for col in ['状态', '签到状态', '教练状态']:
        if col in result.columns:
            status_col = col
            break

    summary = {
        "total_records": len(records),
        "departments": result['部门'].nunique() if '部门' in result.columns else 0,
        "schools": result['学校名称'].nunique() if '学校名称' in result.columns else 0,
        "coaches": result['教练姓名'].nunique() if '教练姓名' in result.columns else 0,
        "non_岗_count": int((result[status_col] != '在岗').sum()) if status_col and status_col in result.columns else 0,
    }

    return {
        "records": records,
        "excel_bytes": excel_bytes,
        "summary": summary,
    }


def _generate_excel(df: pd.DataFrame) -> bytes:
    """Generate formatted Excel with highlighting for non-在岗 statuses."""
    wb = Workbook()
    ws = wb.active
    ws.title = "cwcl"

    headers = list(df.columns)
    ws.append(headers)

    highlight_fill = PatternFill(start_color='FFFF00', end_color='FFFF00', fill_type='solid')
    center_alignment = Alignment(horizontal='center', vertical='center')

    status_col_name = None
    for col in ['状态', '签到状态', '教练状态']:
        if col in headers:
            status_col_name = col
            break
    status_col_idx = headers.index(status_col_name) + 1 if status_col_name else None

    for row_idx, (_, row) in enumerate(df.iterrows(), start=2):
        ws.append(row.tolist())
        for col_idx in range(1, len(headers) + 1):
            ws.cell(row=row_idx, column=col_idx).alignment = center_alignment
        if status_col_idx and row[status_col_name] != '在岗':
            ws.cell(row=row_idx, column=status_col_idx).fill = highlight_fill

    for col_idx in range(1, len(headers) + 1):
        ws.cell(row=1, column=col_idx).alignment = center_alignment

    for row_num in range(1, ws.max_row + 1):
        ws.row_dimensions[row_num].height = 45

    # Auto column width
    for col in range(1, ws.max_column + 1):
        max_length = 0
        for row in range(1, ws.max_row + 1):
            cell_value = ws.cell(row, col).value
            if cell_value:
                length = sum(2 if ord(c) > 127 else 1 for c in str(cell_value))
                if length > max_length:
                    max_length = length
        ws.column_dimensions[get_column_letter(col)].width = min(max(max_length + 2, 10), 50)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()
