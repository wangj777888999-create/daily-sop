import pandas as pd
import os
from openpyxl.styles import Alignment
import datetime
import re

# ---------------------- 通用工具函数 ----------------------
def extract_school_main(school_name):
    """提取学校主名称（归总校区）"""
    if pd.isna(school_name):
        return '未知学校'
    match = re.match(r'^(.+?)(?:（[^）]+）|$)', str(school_name))
    return match.group(1).strip() if match else str(school_name).strip()

def auto_column_width(ws):
    """中文自适应列宽（优化：兼容空值）"""
    def char_width(text):
        if pd.isna(text) or text == '':
            return 2
        return sum(2 if '\u4e00' <= c <= '\u9fff' else 1 for c in str(text))
    for col in ws.columns:
        max_w = max(char_width(cell.value) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_w + 2, 40)

# ---------------------- 核心分析函数 ----------------------
def campus_finance_analysis(coach_att, finance_df):
    """校内财务分析：上课人次+收入统计（修复.str调用错误）"""
    finance_df = finance_df[finance_df['学员类型'] == '学校学员'].copy()
    
    # 修复1：单列处理（确保对Series调用.str）
    for col in ['教练', '课程名称']:
        # 先转为字符串类型 → 再去空格 → 空值填充（全程针对Series）
        finance_df[col] = finance_df[col].astype(str).str.strip().fillna('未知')
    
    # 修复2：多列批量处理字符串（用applymap而非apply，按元素处理）
    str_cols = ['教练姓名', '课程名称', '部门', '学校名称']
    # 先转为字符串类型，再对每个元素去空格，空值填充为'未知'
    coach_att[str_cols] = coach_att[str_cols].astype(str).applymap(lambda x: x.strip()).fillna('未知')

    # 构建合并键（无变化）
    finance_df['名加课'] = finance_df['教练'] + '_' + finance_df['课程名称']
    coach_att['名加课'] = coach_att['教练姓名'] + '_' + coach_att['课程名称']
    
    # 财务数据聚合（无变化）
    finance_agg = finance_df.groupby('名加课').agg(
        上课人次=('上课日期', 'count'),
        已确认收入=('课程单价', lambda x: pd.to_numeric(x, errors='coerce').fillna(0).sum())
    ).round(2)  

    # 考勤数据聚合（无变化）
    coach_agg = coach_att.groupby(['部门', '学校名称', '教练姓名', '名加课']).size().rename('上课次数').reset_index()
    
    # 合并数据（无变化）
    result = pd.merge(coach_agg, finance_agg.reset_index(), on='名加课', how='left').fillna(0)
    
    # 打印胡允祥数据（调试用）
    hu_data = result[result['教练姓名'] == '胡允祥'][['名加课', '上课次数', '上课人次', '已确认收入']]
    print(hu_data)
    
    # 透视表（无变化）
    pivot = result.pivot_table(
        index=['部门', '学校名称','名加课', '教练姓名'],
        values=['上课次数', '上课人次', '已确认收入'],
        aggfunc='sum', fill_value=0, margins=True, margins_name='总计'
    )
    pivot[['上课次数', '上课人次']] = pivot[['上课次数', '上课人次']].astype(int)
    return pivot

def coach_checkin_analysis(att_df):
    """教练考勤分析：签到状态+合并显示签到率（修复'教练个人签到率(%)'列缺失）"""
    # 数据预处理
    att_df = att_df.copy()
    att_df['签到状态'] = att_df['签到状态'].astype(str).str.strip().fillna('未签到')
    att_df['学校主名称'] = att_df['学校名称'].apply(extract_school_main)

    # 签到状态统计（透视表）
    checkin_stats = (
        att_df.groupby(['部门', '学校名称', '教练姓名', '签到状态'])
        .size()
        .unstack(fill_value=0)
        .add_suffix('次数')
    )
    checkin_stats['总计次数'] = checkin_stats.sum(axis=1)
    checkin_stats['在岗次数'] = checkin_stats.get('在岗次数', 0)

    # ========== 核心修复：补充生成'教练个人签到率(%)'列 ==========
    checkin_stats['教练个人签到率(%)'] = (
        (checkin_stats['在岗次数'] / checkin_stats['总计次数'] * 100)
        .round(2)  # 保留2位小数
        .fillna(0)  # 避免除以0导致的NaN
    )

    # 计算学校签到率（低版本pandas兼容：删除include_groups=False）
    school_rate = att_df.groupby(['部门', '学校主名称']).apply(
        lambda x: (x['签到状态'] == '在岗').sum() / len(x) * 100 if len(x) > 0 else 0
    ).round(2).rename('学校签到率(%)')
    
    # 计算部门签到率（低版本pandas兼容：删除include_groups=False）
    dept_rate = att_df.groupby('部门').apply(
        lambda x: (x['签到状态'] == '在岗').sum() / len(x) * 100 if len(x) > 0 else 0
    ).round(2).rename('部门签到率(%)')

    # 合并数据+重置索引
    result = checkin_stats.reset_index()
    result['学校主名称'] = result['学校名称'].apply(extract_school_main)
    result = result.merge(school_rate.reset_index(), on=['部门', '学校主名称'], how='left')
    result = result.merge(dept_rate.reset_index(), on='部门', how='left')

    # 合并签到率显示逻辑
    result['学校签到率(%)'] = result.groupby(['部门', '学校主名称'])['学校签到率(%)'].transform(
        lambda x: x.iloc[0] if len(x) > 0 else ''
    ).where(result.groupby(['部门', '学校主名称']).cumcount() == 0, '')

    result['部门签到率(%)'] = result.groupby('部门')['部门签到率(%)'].transform(
        lambda x: x.iloc[0] if len(x) > 0 else ''
    ).where(result.groupby('部门').cumcount() == 0, '')

    # 恢复多层索引+添加总计行
    result = result.set_index(['部门', '学校名称', '教练姓名']).drop('学校主名称', axis=1)
    count_cols = [col for col in result.columns if '次数' in col]
    
    # 构建总计行（兼容所有列，包括新增的教练个人签到率）
    total_row_data = {
        col: result[col].sum() if col in count_cols else '-' 
        for col in result.columns
    }
    total_row = pd.Series(total_row_data, name=('总计', '总计', '总计'))
    final_result = pd.concat([result, total_row.to_frame().T])

    # 格式化签到率（现在列存在，不会报错）
    mask = final_result.index != ('总计', '总计', '总计')
    for col in ['教练个人签到率(%)', '学校签到率(%)', '部门签到率(%)']:
        final_result.loc[mask, col] = final_result.loc[mask, col].apply(
            lambda x: f"{x:.2f}%" if x != '' and pd.notna(x) and isinstance(x, (int, float)) else ''
        )

    return final_result

# def course_type_analysis(att_df, type_file):
#     """课程类型分析：课次统计+收费类占比（修复返回值+总课次计算）"""
#     # 1. 数据合并（优化：空值处理）
#     print(att_df)
#     att_df = att_df.copy()
#     type_file = type_file.copy()
#     for col in ['课程名称']:
#         att_df[col] = att_df[col].astype(str).str.strip()
#         type_file[col] = type_file[col].astype(str).str.strip()
#     att_df = pd.merge(att_df, type_file, on='课程名称', how='left')
    
#     # 2. 按部门+类型统计课次
#     att_df_type_ana = att_df.groupby(['部门', '类型']).size().rename('课程类型次数').reset_index()
    
#     # 3. 计算各部门总课次（修复：求和而非计数）
#     att_df_type_ana_total = att_df_type_ana.groupby('部门')['课程类型次数'].sum().rename('总课次').reset_index()
    
#     # 4. 定义目标类型（收费类）
#     target_types = ['兴趣班', '校队', '梯队']
#     month = '3月'  
#     print(att_df_type_ana_total)
#     # 5. 遍历所有部门，收集结果
#     output_list = []
#     for _, dept_row in att_df_type_ana_total.iterrows():
#         dept_name = dept_row['部门']
#         total_count = dept_row['总课次']
        
#         # 筛选该部门的所有类型课次
#         dept_detail = att_df_type_ana[att_df_type_ana['部门'] == dept_name]
        
#         # 构建类型字符串+统计收费类
#         type_str_list = []
#         target_total = 0
#         for _, type_row in dept_detail.iterrows():
#             type_name = type_row['类型'] if pd.notna(type_row['类型']) else '未知类型'
#             type_count = type_row['课程类型次数']
#             type_str_list.append(f'{type_name}{type_count}次')
#             if type_name in target_types:
#                 target_total += type_count
        
#         # 计算占比（避免除以0）
#         target_ratio = (target_total / total_count) * 100 if total_count != 0 else 0
        
#         # 拼接输出文本
#         type_str = '、'.join(type_str_list)
#         output = f"{dept_name}：{month}总课次{total_count}次，其中{type_str}，（收费类兴趣班、校队/梯队）课次占总课次的{target_ratio:.2f}%"
        
#         # 收集结果
#         output_list.append({
#             '部门': dept_name,
#             '总课次': total_count,
#             '各类型课次': type_str,
#             '收费类课次': target_total,
#             '收费类占比(%)': round(target_ratio, 2),
#             '输出文本': output
#         })
    
#     # 6. 合并结果为DataFrame
#     output_df = pd.DataFrame(output_list)
#     final_df = pd.merge(att_df_type_ana, output_df[['部门', '总课次', '收费类课次', '收费类占比(%)', '输出文本']], on='部门', how='left')
    
#     # 7. 打印输出文本（便于控制台查看）
#     print("\n📋 课程类型分析结果：")
#     for text in output_df['输出文本'].tolist():
#         print(text)

#     return final_df

def course_type_analysis(att_df, type_file):
    """课程类型分析：包含缺失类型检查+课次统计+收费类占比"""
    
    # 1. 数据合并与清洗
    att_df = att_df.copy()
    type_file = type_file.copy()
    
    # 统一列名格式（去除首尾空格）
    att_df.columns = att_df.columns.str.strip()
    type_file.columns = type_file.columns.str.strip()

    # 核心检查：确保关键列存在
    if '课程名称' not in att_df.columns or '课程名称' not in type_file.columns:
        print("❌ 错误：数据中缺少 '课程名称' 列，请检查原始文件表头。")
        return None

    # 统一转为字符串并去空格，防止匹配失败
    att_df['课程名称'] = att_df['课程名称'].astype(str).str.strip()
    type_file['课程名称'] = type_file['课程名称'].astype(str).str.strip()
    
    # 执行左连接：保留 att_df 所有课程，匹配 type_file 中的类型
    merged_df = pd.merge(att_df, type_file, on='课程名称', how='left')
    
    # 2. 🛑 核心新增：检查是否有课程缺失类型
    # pd.isna() 可以准确识别 merge 后未匹配上的空值
    missing_type_mask = pd.isna(merged_df['类型'])
    
    if missing_type_mask.any():
        # 获取缺失类型的课程名单（去重）
        missing_courses = merged_df.loc[missing_type_mask, '课程名称'].unique()
        
        print("\n" + "="*50)
        print("⚠️ 警告：发现以下课程未在 type_file 中配置类型！")
        print("="*50)
        for course in missing_courses:
            print(f" - {course}")
        print("="*50)
        print("🛑 已暂停分析，请补充类型配置后重新运行。")
        missing_df = pd.DataFrame(missing_courses, columns=['缺失课程名称'])
        missing_df.to_excel('missing_courses.xlsx', index=False)
        return None

    # 3. 如果所有类型都存在，继续执行原逻辑
    print("✅ 检查通过：所有课程均已匹配到类型，开始执行分析...")

    # 检查分组所需的列是否存在
    if '部门' not in merged_df.columns:
         print("❌ 错误：数据中缺少 '部门' 列。")
         return None

    # 4. 按部门+类型统计课次
    # dropna=False 防止因为其他列的空值导致分组异常（虽然类型列现在保证不为空了）
    att_df_type_ana = merged_df.groupby(['部门', '类型']).size().rename('课程类型次数').reset_index()
    
    # 5. 计算各部门总课次
    att_df_type_ana_total = att_df_type_ana.groupby('部门')['课程类型次数'].sum().rename('总课次').reset_index()
    
    # 6. 定义目标类型（收费类）
    target_types = ['兴趣班', '校队', '梯队']
    month = '3月'  # 建议改为动态参数
    
    output_list = []
    
    if not att_df_type_ana_total.empty:
        for _, dept_row in att_df_type_ana_total.iterrows():
            dept_name = dept_row['部门']
            total_count = dept_row['总课次']
            
            # 筛选该部门的所有类型课次
            dept_detail = att_df_type_ana[att_df_type_ana['部门'] == dept_name]
            
            type_str_list = []
            target_total = 0
            
            for _, type_row in dept_detail.iterrows():
                type_name = str(type_row['类型']) if pd.notna(type_row['类型']) else '未知类型'
                type_count = type_row['课程类型次数']
                type_str_list.append(f'{type_name}{type_count}次')
                if type_name in target_types:
                    target_total += type_count
            
            target_ratio = (target_total / total_count) * 100 if total_count != 0 else 0
            type_str = '、'.join(type_str_list)
            
            output = f"{dept_name}：{month}总课次{total_count}次，其中{type_str}，（收费类兴趣班、校队/梯队）课次占总课次的{target_ratio:.2f}%"
            
            output_list.append({
                '部门': dept_name,
                '总课次': total_count,
                '各类型课次': type_str,
                '收费类课次': target_total,
                '收费类占比(%)': round(target_ratio, 2),
                '输出文本': output
            })
    
    output_df = pd.DataFrame(output_list)
    final_df = pd.merge(att_df_type_ana, output_df[['部门', '总课次', '收费类课次', '收费类占比(%)', '输出文本']], on='部门', how='left')
    
    print("\n📋 课程类型分析结果：")
    for text in output_df['输出文本'].tolist():
        print(text)

    return final_df

def refund_analysis(refund_df,department):
    refund_df = pd.merge(refund_df, department, on='学校', how='left')
    refund_df = pd.pivot_table(
        refund_df,
        index=['部门', '学校'],
        values=['学员姓名','退款金额'],
        aggfunc={'学员姓名': 'count', '退款金额': 'sum'}, 
        margins=True,
        margins_name='总计')
    return refund_df

# ---------------------- 统一导出函数（删除冗余逻辑） ----------------------
def export_multi_sheet_excel(data_dict, output_dir, filename):
    """导出多sheet Excel，支持多层索引+格式美化"""
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, filename)

    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        for sheet_name, df in data_dict.items():
            # 关键：多层索引保留index=True，单层索引index=False
            index_flag = isinstance(df.index, pd.MultiIndex) or (df.index.nlevels > 1)
            df.to_excel(writer, sheet_name=sheet_name, index=index_flag)
            
            # 格式美化：居中+自适应列宽
            ws = writer.sheets[sheet_name]
            center = Alignment(horizontal='center', vertical='center')
            for row in ws.iter_rows():
                for cell in row:
                    cell.alignment = center
            auto_column_width(ws)

    print(f"\n✅ 导出成功：{output_path}")
    print(f"📊 包含Sheet：{list(data_dict.keys())}")

# ---------------------- 主函数 ----------------------
if __name__ == "__main__":
    # 配置项
    CONFIG = {
        'finance_path': r'C:\Users\Administrator\Desktop\python\代码分析\华越分析\华越分析\2026年分析\4月\校内\财务统计明细 (16).xls',
        'attendance_path': r'C:\Users\Administrator\Desktop\python\代码分析\华越分析\华越分析\2026年分析\4月\校内\4月教练签到.xlsx',
        'output_dir': r'C:\Users\Administrator\Desktop\python\代码分析\华越分析\华越分析\2026年分析\4月\校内',
        'type_file': r'C:\Users\Administrator\Desktop\python\代码分析\华越分析\华越分析\2026年分析\3月\校内\26年春课程类型.xlsx',
        'department':r'C:\Users\Administrator\Desktop\python\代码分析\华越分析\华越分析\python分析\分析通用文件\部门划分.xlsx',
        'refund_df':r'C:\Users\Administrator\Desktop\python\代码分析\华越分析\华越分析\2026年分析\4月\校内\退款导出 (29).xls',
        'sheet_names': {
            '校内分析': campus_finance_analysis,
            '教练考勤': coach_checkin_analysis,
            '类型分析': course_type_analysis,
            '退款分析': refund_analysis,
            '教练签到': lambda att_df: att_df  # 直接返回原始考勤数据
        }
    }

    # 计算上月（用于文件名）
    today = datetime.datetime.now()
    last_month = today.month - 1 if today.month > 1 else 12
    output_filename = f'{last_month}月校内分析.xlsx'

    try:
        # 1. 读取数据（兼容不同Excel引擎）
        print("📥 正在读取数据...")
        finance_df = pd.read_excel(CONFIG['finance_path'], sheet_name='财务', engine='xlrd')
        att_df = pd.read_excel(CONFIG['attendance_path'], sheet_name='Sheet1', engine='openpyxl')
        type_file = pd.read_excel(CONFIG['type_file'], sheet_name='Sheet1', engine='openpyxl')
        refund_df = pd.read_excel(CONFIG['refund_df'], sheet_name='导出', engine='xlrd')
        # 2. 执行各模块分析
        print("\n📈 正在执行分析...")
        data_to_export = {}
        for sheet_name, analysis_func in CONFIG['sheet_names'].items():
            print(f"  - 执行【{sheet_name}】分析...")
            if sheet_name == '校内分析':
                data_to_export[sheet_name] = analysis_func(att_df, finance_df)
            elif sheet_name == '类型分析':
                data_to_export[sheet_name] = analysis_func(att_df, type_file)
            elif sheet_name == '退款分析':
                department_df = pd.read_excel(CONFIG['department'], sheet_name='Sheet1', engine='openpyxl')
                data_to_export[sheet_name] = analysis_func(refund_df, department_df)
            elif sheet_name == '教练考勤':
                data_to_export[sheet_name] = analysis_func(att_df)
            else:
                data_to_export['教练签到'] = att_df

        # 3. 统一导出Excel（删除冗余的写入逻辑）
        export_multi_sheet_excel(data_to_export, CONFIG['output_dir'], output_filename)

    # 异常处理（细分类型）
    except FileNotFoundError as e:
        print(f"\n❌ 错误：找不到文件 - {str(e)}")
        print("  请检查配置中的文件路径是否正确（注意文件名/后缀）")
    except ImportError as e:
        print(f"\n❌ 错误：缺少Excel引擎 - {str(e)}")
        print("  解决方案：pip install xlrd openpyxl pandas")
    except PermissionError as e:
        print(f"\n❌ 错误：权限不足 - {str(e)}")
        print("  请关闭已打开的Excel文件，或检查目录读写权限")
    except KeyError as e:
        print(f"\n❌ 错误：列名不存在 - {str(e)}")
        print("  请检查数据中的列名是否与代码匹配（如'课程名称'/'签到状态'）")
    except Exception as e:
        print(f"\n❌ 未知错误：{str(e)}")
        # 可选：打印详细报错栈（调试用）
        # import traceback
        # traceback.print_exc()