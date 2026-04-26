# backend/sops/code_generator.py
import re
import warnings
from typing import Dict, List, Any, Optional


class CodeGenerator:
    """SOP 代码生成器 - 将 SOP 步骤转换为可执行 Python 代码"""

    def __init__(self):
        self.df_counter = 0
        self.df_vars: Dict[str, str] = {}  # 追踪 DataFrame 变量名: action -> df_var
        self.lines: List[str] = []

    def generate(self, sop: Dict[str, Any]) -> str:
        """生成可执行代码

        Args:
            sop: SOP 字典（包含 steps 数组）

        Returns:
            可执行的 Python 代码字符串
        """
        self.df_counter = 0
        self.df_vars.clear()
        self.lines = []

        # 添加文件头注释
        sop_name = sop.get("name", "未命名 SOP")
        self.lines.append(f"# SOP: {sop_name}")
        self.lines.append("import pandas as pd")
        self.lines.append("")

        # 处理每个步骤
        steps = sop.get("steps", [])
        for step in steps:
            action = step.get("action", "")
            params = step.get("params", {})
            result_var = step.get("result_var")

            code = self._generate_step(action, params, result_var)
            if code:
                self.lines.append(code)

        return "\n".join(self.lines)

    def _generate_step(self, action: str, params: Dict[str, Any], result_var: Optional[str] = None) -> Optional[str]:
        """根据 action 类型生成对应代码"""
        generator_map = {
            "read_excel": self._generate_read_excel,
            "read_csv": self._generate_read_csv,
            "filter": self._generate_filter,
            "drop_columns": self._generate_drop_columns,
            "merge": self._generate_merge,
            "groupby": self._generate_groupby,
            "sort": self._generate_sort,
            "to_excel": self._generate_to_excel,
            "to_csv": self._generate_to_csv,
        }

        generator = generator_map.get(action)
        if generator:
            return generator(params, result_var)
        return None

    def _get_df_var(self, action: str, result_var: Optional[str] = None) -> str:
        """获取或创建 DataFrame 变量名"""
        if result_var:
            self.df_vars[action] = result_var
            return result_var

        if action not in self.df_vars:
            self.df_counter += 1
            self.df_vars[action] = f"df{self.df_counter}"
        return self.df_vars[action]

    def _generate_read_excel(self, params: Dict[str, Any], result_var: Optional[str] = None) -> str:
        """生成 read_excel 代码"""
        file = params.get("file", "")
        if not file:
            warnings.warn("read_excel 操作缺少 file 参数")
            return ""

        var_name = self._get_df_var("read_excel", result_var)

        parts = [f"'{file}'"]

        # sheet_name
        sheet_name = params.get("sheet_name")
        if sheet_name:
            parts.append(f"sheet_name='{sheet_name}'")

        # skiprows
        skiprows = params.get("skiprows")
        if skiprows is not None:
            parts.append(f"skiprows={skiprows}")

        # usecols
        usecols = params.get("usecols")
        if usecols is not None:
            if isinstance(usecols, str):
                parts.append(f"usecols='{usecols}'")
            else:
                parts.append(f"usecols={usecols}")

        # header
        header = params.get("header")
        if header is not None:
            parts.append(f"header={header}")

        args_str = ", ".join(parts)
        return f"{var_name} = pd.read_excel({args_str})"

    def _generate_read_csv(self, params: Dict[str, Any], result_var: Optional[str] = None) -> str:
        """生成 read_csv 代码"""
        file = params.get("file", "")
        if not file:
            warnings.warn("read_csv 操作缺少 file 参数")
            return ""

        var_name = self._get_df_var("read_csv", result_var)

        parts = [f"'{file}'"]

        # encoding
        encoding = params.get("encoding")
        if encoding:
            parts.append(f"encoding='{encoding}'")

        # sep
        sep = params.get("sep")
        if sep and sep != ",":
            parts.append(f"sep='{sep}'")

        # skiprows
        skiprows = params.get("skiprows")
        if skiprows is not None:
            parts.append(f"skiprows={skiprows}")

        args_str = ", ".join(parts)
        return f"{var_name} = pd.read_csv({args_str})"

    def _generate_filter(self, params: Dict[str, Any], result_var: Optional[str] = None) -> str:
        """生成 filter 代码"""
        df = params.get("df", "")
        condition = params.get("condition", "")

        if not df and not condition:
            warnings.warn("filter 操作缺少必要的 df 或 condition 参数")
            return ""

        # 确定源 DataFrame 变量名
        if not df:
            df = "df"

        var_name = self._get_df_var("filter", result_var)

        # 优先使用 query 方式，带安全验证
        if condition:
            if not _validate_condition(condition):
                warnings.warn(f"filter 操作检测到不安全的条件表达式: {condition}")
                return ""
            return f'{var_name} = {df}.query("{condition}")'
        else:
            return f"{var_name} = {df}"

    def _generate_drop_columns(self, params: Dict[str, Any], result_var: Optional[str] = None) -> str:
        """生成 drop_columns 代码"""
        df = params.get("df", "")
        columns = params.get("columns", "")

        if not df and not columns:
            warnings.warn("drop_columns 操作缺少必要的 df 或 columns 参数")
            return ""

        if not df:
            df = "df"

        var_name = self._get_df_var("drop_columns", result_var)

        # 处理 columns 可能是元组或列表的情况
        if isinstance(columns, (list, tuple)):
            cols_str = ", ".join(f"'{col}'" for col in columns)
            return f"{var_name} = {df}.drop(columns=[{cols_str}])"
        else:
            return f"{var_name} = {df}.drop(columns=['{columns}'])"

    def _generate_merge(self, params: Dict[str, Any], result_var: Optional[str] = None) -> str:
        """生成 merge 代码"""
        left_df = params.get("left_df", "")
        right_df = params.get("right_df", "")
        on = params.get("on", "")
        how = params.get("how", "inner")

        if not left_df and not right_df and not on:
            warnings.warn("merge 操作缺少必要的 left_df、right_df 或 on 参数")
            return ""

        var_name = self._get_df_var("merge", result_var)

        # 处理 on 参数可能是列表的情况
        if isinstance(on, list):
            on_str = ", ".join(f"'{col}'" for col in on)
            on_part = f"on=[{on_str}]"
        elif isinstance(on, str):
            on_part = f"on='{on}'"
        else:
            on_part = f"on='{on}'"

        how_part = f"how='{how}'" if how and how != "inner" else ""

        parts = [left_df, right_df, on_part]
        if how_part:
            parts.append(how_part)

        args_str = ", ".join(parts)
        return f"{var_name} = pd.merge({args_str})"

    def _generate_groupby(self, params: Dict[str, Any], result_var: Optional[str] = None) -> str:
        """生成 groupby 代码"""
        df = params.get("df", "")
        by = params.get("by", "")
        agg_dict = params.get("agg", None)

        if not df and not by:
            warnings.warn("groupby 操作缺少必要的 df 或 by 参数")
            return ""

        if not df:
            df = "df"

        var_name = self._get_df_var("groupby", result_var)

        # 处理 by 参数可能是列表的情况
        if isinstance(by, list):
            by_str = ", ".join(f"'{col}'" for col in by)
            by_part = f"[{by_str}]"
        else:
            by_part = f"'{by}'"

        if agg_dict:
            # agg 是字典格式 {'col': 'sum', 'col2': 'count'}
            agg_parts = []
            for col, func in agg_dict.items():
                agg_parts.append(f"'{col}': '{func}'")
            agg_str = "{" + ", ".join(agg_parts) + "}"
            return f"{var_name} = {df}.groupby(by={by_part}).agg({agg_str})"
        else:
            return f"{var_name} = {df}.groupby(by={by_part})"

    def _generate_sort(self, params: Dict[str, Any], result_var: Optional[str] = None) -> str:
        """生成 sort 代码"""
        df = params.get("df", "")
        by = params.get("by", "")
        ascending = params.get("ascending", True)

        if not df and not by:
            warnings.warn("sort 操作缺少必要的 df 或 by 参数")
            return ""

        if not df:
            df = "df"

        var_name = self._get_df_var("sort", result_var)

        # 处理 by 参数可能是列表的情况
        if isinstance(by, list):
            by_str = ", ".join(f"'{col}'" for col in by)
            by_part = f"[{by_str}]"
        else:
            by_part = f"'{by}'"

        asc_str = "True" if ascending else "False"
        return f"{var_name} = {df}.sort_values(by={by_part}, ascending={asc_str})"

    def _generate_to_excel(self, params: Dict[str, Any], result_var: Optional[str] = None) -> str:
        """生成 to_excel 代码"""
        df = params.get("df", "")
        file = params.get("file", "")

        if not df and not file:
            warnings.warn("to_excel 操作缺少必要的 df 或 file 参数")
            return ""

        # 确定源 DataFrame 变量名
        if not df:
            df = "df"

        parts = [f"'{file}'"]

        # sheet_name
        sheet_name = params.get("sheet_name")
        if sheet_name:
            parts.append(f"sheet_name='{sheet_name}'")

        # index
        index = params.get("index", False)
        if index is False:
            parts.append("index=False")

        args_str = ", ".join(parts)
        return f"{df}.to_excel({args_str})"

    def _generate_to_csv(self, params: Dict[str, Any], result_var: Optional[str] = None) -> str:
        """生成 to_csv 代码"""
        df = params.get("df", "")
        file = params.get("file", "")

        if not df and not file:
            warnings.warn("to_csv 操作缺少必要的 df 或 file 参数")
            return ""

        # 确定源 DataFrame 变量名
        if not df:
            df = "df"

        parts = [f"'{file}'"]

        # index
        index = params.get("index", False)
        if index is False:
            parts.append("index=False")

        # encoding
        encoding = params.get("encoding")
        if encoding:
            parts.append(f"encoding='{encoding}'")

        args_str = ", ".join(parts)
        return f"{df}.to_csv({args_str})"


def _validate_condition(condition: str) -> bool:
    """验证条件表达式是否安全，防止代码注入

    只允许字母、数字、下划线、比较运算符、逻辑运算符、括号和空格
    """
    if not condition:
        return True
    # 允许：字母、数字、下划线、比较运算符、逻辑运算符、括号、引号、点号（列名可能有）
    pattern = r'^[\w\s\+\-\*/\.\'\"=<>!&|(),]+$'
    return bool(re.match(pattern, condition))


def SOPToExecutableCode(sop: Dict[str, Any], mappings: Dict[str, str] = None) -> str:
    """将 SOP 转换为可执行代码

    Args:
        sop: SOP 字典（包含 name, description, steps 数组）
        mappings: 数据源ID到实际文件的映射，如 {"ds_coach": "/path/to/file.xlsx"}
                 如果为 None，则使用 SOP 中存储的原始路径

    Returns:
        可执行的 Python 代码字符串
    """
    generator = CodeGenerator()
    code = generator.generate(sop)

    # 如果提供了 mappings，进行替换
    if mappings:
        for ds_id, file_path in mappings.items():
            # 替换 {{ds_id}} 占位符（保留周围的引号）
            placeholder = f'{{{{{ds_id}}}}}'
            code = code.replace(placeholder, file_path)

    return code


# 测试代码
if __name__ == "__main__":
    # 测试用例
    test_sop = {
        "name": "教练签到数据分析",
        "description": "处理教练签到Excel数据",
        "steps": [
            {
                "step": 1,
                "action": "read_excel",
                "params": {"file": "input.xlsx", "sheet_name": "教练签到", "skiprows": 2}
            },
            {
                "step": 2,
                "action": "filter",
                "params": {"df": "df1", "condition": "region == '华东'"}
            },
            {
                "step": 3,
                "action": "drop_columns",
                "params": {"df": "df2", "columns": ["unused_col1", "unused_col2"]}
            },
            {
                "step": 4,
                "action": "read_csv",
                "params": {"file": "finance.csv", "encoding": "utf-8"}
            },
            {
                "step": 5,
                "action": "merge",
                "params": {"left_df": "df3", "right_df": "df4", "on": "id", "how": "left"}
            },
            {
                "step": 6,
                "action": "groupby",
                "params": {"df": "df5", "by": "region", "agg": {"sales": "sum", "count": "count"}}
            },
            {
                "step": 7,
                "action": "sort",
                "params": {"df": "df6", "by": "sales", "ascending": False}
            },
            {
                "step": 8,
                "action": "to_excel",
                "params": {"df": "df7", "file": "output.xlsx", "sheet_name": "结果"}
            }
        ]
    }

    print("=" * 60)
    print("测试 1: 完整 SOP 代码生成")
    print("=" * 60)
    code = SOPToExecutableCode(test_sop)
    print(code)

    print("\n" + "=" * 60)
    print("测试 2: read_excel 代码生成")
    print("=" * 60)
    sop2 = {
        "name": "测试read_excel",
        "steps": [
            {
                "step": 1,
                "action": "read_excel",
                "params": {"file": "data.xlsx", "sheet_name": "Sheet1", "skiprows": 2}
            }
        ]
    }
    code2 = SOPToExecutableCode(sop2)
    print(code2)

    print("\n" + "=" * 60)
    print("测试 3: filter 代码生成")
    print("=" * 60)
    sop3 = {
        "name": "测试filter",
        "steps": [
            {
                "step": 1,
                "action": "filter",
                "params": {"df": "df1", "condition": "age > 25"}
            }
        ]
    }
    code3 = SOPToExecutableCode(sop3)
    print(code3)

    print("\n" + "=" * 60)
    print("测试 4: merge 代码生成")
    print("=" * 60)
    sop4 = {
        "name": "测试merge",
        "steps": [
            {
                "step": 1,
                "action": "merge",
                "params": {"left_df": "df1", "right_df": "df2", "on": "id", "how": "left"}
            }
        ]
    }
    code4 = SOPToExecutableCode(sop4)
    print(code4)

    print("\n" + "=" * 60)
    print("测试 5: groupby + agg 代码生成")
    print("=" * 60)
    sop5 = {
        "name": "测试groupby",
        "steps": [
            {
                "step": 1,
                "action": "groupby",
                "params": {"df": "df1", "by": "category", "agg": {"sales": "sum", "quantity": "count"}}
            }
        ]
    }
    code5 = SOPToExecutableCode(sop5)
    print(code5)

    print("\n" + "=" * 60)
    print("测试 6: sort 代码生成")
    print("=" * 60)
    sop6 = {
        "name": "测试sort",
        "steps": [
            {
                "step": 1,
                "action": "sort",
                "params": {"df": "df1", "by": "sales", "ascending": False}
            }
        ]
    }
    code6 = SOPToExecutableCode(sop6)
    print(code6)

    print("\n" + "=" * 60)
    print("测试 7: to_excel 代码生成")
    print("=" * 60)
    sop7 = {
        "name": "测试to_excel",
        "steps": [
            {
                "step": 1,
                "action": "to_excel",
                "params": {"df": "df1", "file": "output.xlsx", "sheet_name": "结果"}
            }
        ]
    }
    code7 = SOPToExecutableCode(sop7)
    print(code7)

    print("\n" + "=" * 60)
    print("测试 8: to_csv 代码生成")
    print("=" * 60)
    sop8 = {
        "name": "测试to_csv",
        "steps": [
            {
                "step": 1,
                "action": "to_csv",
                "params": {"df": "df1", "file": "output.csv", "encoding": "utf-8"}
            }
        ]
    }
    code8 = SOPToExecutableCode(sop8)
    print(code8)

    print("\n所有测试完成!")
