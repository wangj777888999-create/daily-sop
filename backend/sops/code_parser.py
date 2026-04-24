import ast
import re
from typing import Dict, List, Any, Optional


class CodeParser:
    """Python 代码解析器 - 将 Python 代码转换为 SOP 步骤"""

    def __init__(self):
        self.df_variables: Dict[str, str] = {}  # 追踪 DataFrame 变量名
        self.steps: List[Dict[str, Any]] = []
        self.step_counter = 0

    def parse(self, code: str) -> Dict[str, Any]:
        """解析 Python 代码为 SOP 结构"""
        self.df_variables.clear()
        self.steps = []
        self.step_counter = 0

        try:
            tree = ast.parse(code)
        except SyntaxError:
            # 如果 AST 解析失败，尝试用正则表达式提取
            return self._parse_with_regex(code)

        # 分析 AST 节点
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                self._analyze_assignment(node)
            elif isinstance(node, ast.Expr):
                self._analyze_expression(node)
            elif isinstance(node, ast.FunctionDef):
                self._analyze_function_def(node)
            elif isinstance(node, ast.Delete):
                self._analyze_delete(node)

        # 生成 SOP
        sop_name = self._extract_sop_name(code)
        return {
            "name": sop_name,
            "description": f"从 Python 代码自动解析生成的 SOP，包含 {len(self.steps)} 个步骤",
            "steps": self.steps
        }

    def _parse_with_regex(self, code: str) -> Dict[str, Any]:
        """使用正则表达式解析代码（备用方法）"""
        self.steps = []
        self.step_counter = 0

        # 提取 read_excel
        read_excel_pattern = r"pd\.read_excel\(['\"](.+?)['\"]\s*(?:,\s*([^)]*))?\)"
        for match in re.finditer(read_excel_pattern, code):
            file_path = match.group(1)
            extra = match.group(2) or ""
            params = {"file": file_path}
            # 解析额外参数
            sheet_match = re.search(r"sheet_name\s*=\s*['\"](.+?)['\"]", extra)
            if sheet_match:
                params["sheet_name"] = sheet_match.group(1)
            skiprows_match = re.search(r"skiprows\s*=\s*(\d+)", extra)
            if skiprows_match:
                params["skiprows"] = int(skiprows_match.group(1))
            self._add_step("read_excel", params)

        # 提取 read_csv
        read_csv_pattern = r"pd\.read_csv\(['\"](.+?)['\"]\s*(?:,\s*([^)]*))?\)"
        for match in re.finditer(read_csv_pattern, code):
            file_path = match.group(1)
            extra = match.group(2) or ""
            params = {"file": file_path}
            self._add_step("read_csv", params)

        # 提取 query
        query_pattern = r"(\w+)\.query\(['\"](.+?)['\"]\)"
        for match in re.finditer(query_pattern, code):
            df_name = match.group(1)
            condition = match.group(2)
            self.df_variables[df_name] = "dataframe"
            self._add_step("filter", {"df": df_name, "condition": condition})

        # 提取 drop
        drop_pattern = r"(\w+)\.drop\(columns?\s*=\s*['\"](.+?)['\"]\)"
        for match in re.finditer(drop_pattern, code):
            df_name = match.group(1)
            columns = match.group(2)
            self.df_variables[df_name] = "dataframe"
            self._add_step("drop_columns", {"df": df_name, "columns": columns})

        # 提取 del df['col'] 删除列
        del_pattern = r"del\s+(\w+)\[(['\"])(.+?)\2\]"
        for match in re.finditer(del_pattern, code):
            df_name = match.group(1)
            columns = match.group(3)
            self.df_variables[df_name] = "dataframe"
            self._add_step("drop_columns", {"df": df_name, "columns": columns})

        # 提取 df[df['col'] == value] 括号过滤
        filter_pattern = r"(\w+)\[(\w+)\[(['\"])([^\]]+?)\3\s*(==|!=|<|>|<=|>=)\s*([^\]]+?)\]\]"
        for match in re.finditer(filter_pattern, code):
            df_name = match.group(1)
            column = match.group(4)
            op = match.group(5)
            value = match.group(6)
            self.df_variables[df_name] = "dataframe"
            self._add_step("filter", {"df": df_name, "condition": f"{column} {op} {value}"})

        # 提取 merge
        merge_pattern = r"pd\.merge\(\s*(\w+)\s*,\s*(\w+)\s*,\s*on\s*=\s*['\"](.+?)['\"]\s*(?:,\s*how\s*=\s*['\"](.+?)['\"])?\s*\)"
        for match in re.finditer(merge_pattern, code):
            df1, df2, on_col, how = match.groups()
            how = how or "inner"
            self._add_step("merge", {"left_df": df1, "right_df": df2, "on": on_col, "how": how})

        # 提取 groupby
        groupby_pattern = r"(\w+)\.groupby\(['\"](.+?)['\"]\)"
        for match in re.finditer(groupby_pattern, code):
            df_name = match.group(1)
            col = match.group(2)
            self.df_variables[df_name] = "dataframe"
            self._add_step("groupby", {"df": df_name, "by": col})

        # 提取 sort_values
        sort_pattern = r"(\w+)\.sort_values\(by\s*=\s*['\"](.+?)['\"]\s*(?:,\s*ascending\s*=\s*(True|False))?\)"
        for match in re.finditer(sort_pattern, code):
            df_name = match.group(1)
            by_col = match.group(2)
            ascending = match.group(3) == "True" if match.group(3) else True
            self.df_variables[df_name] = "dataframe"
            self._add_step("sort", {"df": df_name, "by": by_col, "ascending": ascending})

        # 提取 to_excel
        to_excel_pattern = r"(\w+)\.to_excel\(['\"](.+?)['\"]\s*(?:,\s*([^)]*))?\)"
        for match in re.finditer(to_excel_pattern, code):
            df_name = match.group(1)
            file_path = match.group(2)
            self.df_variables[df_name] = "dataframe"
            self._add_step("to_excel", {"df": df_name, "file": file_path})

        # 提取 to_csv
        to_csv_pattern = r"(\w+)\.to_csv\(['\"](.+?)['\"]\s*(?:,\s*([^)]*))?\)"
        for match in re.finditer(to_csv_pattern, code):
            df_name = match.group(1)
            file_path = match.group(2)
            self.df_variables[df_name] = "dataframe"
            self._add_step("to_csv", {"df": df_name, "file": file_path})

        sop_name = self._extract_sop_name(code)
        return {
            "name": sop_name,
            "description": f"从 Python 代码自动解析生成的 SOP，包含 {len(self.steps)} 个步骤",
            "steps": self.steps
        }

    def _analyze_assignment(self, node: ast.Assign):
        """分析赋值语句"""
        # 检查是否是 DataFrame 赋值
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                if isinstance(node.value, ast.Call):
                    self._analyze_call(node.value, var_name)
                elif isinstance(node.value, ast.Subscript):
                    # 检查是否是 df[df['col'] == value] 语法
                    filter_params = self._extract_filter(node.value)
                    if filter_params:
                        self._add_step("filter", filter_params)
                        self.df_variables[var_name] = "dataframe"

    def _analyze_expression(self, node: ast.Expr):
        """分析表达式语句（无赋值的函数调用）"""
        if isinstance(node.value, ast.Call):
            self._analyze_call(node.value, None)

    def _analyze_function_def(self, node: ast.FunctionDef):
        """分析函数定义"""
        for child in ast.walk(node):
            if isinstance(child, ast.Assign):
                self._analyze_assignment(child)
            elif isinstance(child, ast.Expr):
                self._analyze_expression(child)
            elif isinstance(child, ast.Delete):
                self._analyze_delete(child)

    def _analyze_delete(self, node: ast.Delete):
        """分析 del 语句"""
        # del df[col] -> 删除列
        # node.targets 是被删除的目标列表
        for target in node.targets:
            params = self._extract_del_column(target)
            if params:
                self._add_step("drop_columns", params)

    def _extract_del_column(self, target: ast.AST) -> Optional[Dict[str, Any]]:
        """提取 del df[col] 语法中的列名"""
        # del df[col] 中，target 是 ast.Subscript，df 是 value，col 是 slice
        if isinstance(target, ast.Subscript):
            # 获取 df 名称
            if isinstance(target.value, ast.Name):
                df_name = target.value.id
            else:
                return None

            # 获取列名
            col_name = self._extract_subscript_key(target.slice)
            if col_name:
                return {"df": df_name, "columns": col_name}
        return None

    def _extract_subscript_key(self, slice_node: ast.AST) -> Optional[str]:
        """从 subscript 中提取键值"""
        # df['col'] -> slice 是 Constant
        if isinstance(slice_node, ast.Constant):
            return slice_node.value
        # df[col_name] -> slice 是 Name
        elif isinstance(slice_node, ast.Name):
            return slice_node.id
        # df['col1', 'col2'] -> slice 是 Tuple (多索引访问)
        elif isinstance(slice_node, ast.Tuple):
            keys = []
            for elt in slice_node.elts:
                if isinstance(elt, ast.Constant):
                    keys.append(elt.value)
                elif isinstance(elt, ast.Name):
                    keys.append(elt.id)
            return tuple(keys) if keys else None
        return None

    def _extract_filter(self, node: ast.Subscript) -> Optional[Dict[str, Any]]:
        """提取 df[df['col'] == value] 括号过滤语法"""
        # df[...] 中，value 是 df，slice 是布尔条件
        if isinstance(node.value, ast.Name):
            df_name = node.value.id
        else:
            return None

        # 检查是否是布尔索引 df[df['col'] > value]
        slice_node = node.slice
        if isinstance(slice_node, ast.Compare):
            # 提取比较信息
            params = {"df": df_name}

            # 左操作数通常是 df['col'] 或 df["col"]
            if isinstance(slice_node.left, ast.Subscript):
                col_name = self._extract_subscript_key(slice_node.left.slice)
                if col_name:
                    params["column"] = col_name

            # 获取比较运算符
            op_map = {
                ast.Eq: "==",
                ast.NotEq: "!=",
                ast.Lt: "<",
                ast.LtE: "<=",
                ast.Gt: ">",
                ast.GtE: ">=",
            }
            if isinstance(slice_node.ops[0], tuple(op_map.keys())):
                params["op"] = op_map[type(slice_node.ops[0])]

            # 右操作数
            if slice_node.comparators:
                right_val = self._get_value(slice_node.comparators[0])
                if right_val is not None:
                    params["value"] = right_val

            # 构建条件字符串
            if "column" in params and "op" in params and "value" in params:
                col = params.pop("column")
                op = params.pop("op")
                val = params.pop("value")
                params["condition"] = f"{col} {op} {val}"
                params["df"] = df_name
                return params

        return None

    def _analyze_call(self, node: ast.Call, var_name: Optional[str]):
        """分析函数调用"""
        func_name = self._get_func_name(node.func)

        # pd.read_excel / pd.read_csv
        if func_name == "read_excel":
            params = self._extract_read_excel(node)
            self._add_step("read_excel", params)
            if var_name:
                self.df_variables[var_name] = "dataframe"
        elif func_name == "read_csv":
            params = self._extract_read_csv(node)
            self._add_step("read_csv", params)
            if var_name:
                self.df_variables[var_name] = "dataframe"

        # df.query
        elif func_name == "query":
            params = self._extract_query(node)
            if params:
                self._add_step("filter", params)
                if var_name:
                    self.df_variables[var_name] = "dataframe"

        # df.drop / del df[col]
        elif func_name == "drop":
            params = self._extract_drop(node)
            if params:
                self._add_step("drop_columns", params)
                if var_name:
                    self.df_variables[var_name] = "dataframe"

        # pd.merge
        elif func_name == "merge":
            params = self._extract_merge(node)
            if params:
                self._add_step("merge", params)

        # df.groupby
        elif func_name == "groupby":
            params = self._extract_groupby(node)
            if params:
                self._add_step("groupby", params)
                if var_name:
                    self.df_variables[var_name] = "dataframe"

        # 检测链式调用 df.groupby('col').agg(...)
        # df.agg() 是 groupby 之后的链式调用
        elif func_name == "agg":
            # 检查是否是 groupby 链式调用
            chain_result = self._detect_groupby_chain(node, var_name)
            if chain_result:
                self._add_step("groupby", chain_result)
                if var_name:
                    self.df_variables[var_name] = "dataframe"

        # df.sort_values
        elif func_name == "sort_values":
            params = self._extract_sort_values(node)
            if params:
                self._add_step("sort", params)
                if var_name:
                    self.df_variables[var_name] = "dataframe"

        # df.to_excel
        elif func_name == "to_excel":
            params = self._extract_to_excel(node)
            if params:
                self._add_step("to_excel", params)

        # df.to_csv
        elif func_name == "to_csv":
            params = self._extract_to_csv(node)
            if params:
                self._add_step("to_csv", params)

    def _get_func_name(self, node: ast.AST) -> str:
        """获取函数名称"""
        if isinstance(node, ast.Attribute):
            return node.attr
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Call):
            return self._get_func_name(node.func)
        return ""

    def _get_value(self, node: ast.AST) -> Any:
        """获取 AST 节点的值"""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.BinOp):
            left = self._get_value(node.left)
            right = self._get_value(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            elif isinstance(node.op, ast.Mult):
                return left * right
        return None

    def _extract_read_excel(self, node: ast.Call) -> Dict[str, Any]:
        """提取 pd.read_excel() 调用"""
        params = {}

        # 第一个参数通常是文件路径
        if node.args:
            file_path = self._get_value(node.args[0])
            if file_path and isinstance(file_path, str):
                params["file"] = file_path

        # 解析关键字参数
        for keyword in node.keywords:
            key = keyword.arg
            value = self._get_value(keyword.value)
            if key == "sheet_name" and value and isinstance(value, str):
                params["sheet_name"] = value
            elif key == "skiprows":
                params["skiprows"] = value
            elif key == "usecols":
                params["usecols"] = value
            elif key == "header":
                params["header"] = value

        return params if params.get("file") else {}

    def _extract_read_csv(self, node: ast.Call) -> Dict[str, Any]:
        """提取 pd.read_csv() 调用"""
        params = {}

        if node.args:
            params["file"] = self._get_value(node.args[0])

        for keyword in node.keywords:
            key = keyword.arg
            value = self._get_value(keyword.value)
            if key == "encoding":
                params["encoding"] = value
            elif key == "sep":
                params["sep"] = value
            elif key == "skiprows":
                params["skiprows"] = value

        return params

    def _extract_query(self, node: ast.Call) -> Optional[Dict[str, Any]]:
        """提取 df.query() 调用"""
        params = {}

        # 获取被调用的 DataFrame 变量名
        if isinstance(node.func, ast.Attribute):
            df_name = self._get_value(node.func.value) if hasattr(node.func.value, 'id') else None
            if df_name:
                params["df"] = df_name

        if node.args:
            params["condition"] = self._get_value(node.args[0])

        return params if params.get("condition") else None

    def _extract_drop(self, node: ast.Call) -> Optional[Dict[str, Any]]:
        """提取 df.drop() 调用"""
        params = {}

        if isinstance(node.func, ast.Attribute):
            df_name = self._get_value(node.func.value) if hasattr(node.func.value, 'id') else None
            if df_name:
                params["df"] = df_name

        for keyword in node.keywords:
            key = keyword.arg
            value = self._get_value(keyword.value)
            if key == "columns":
                params["columns"] = value
            elif key == "axis":
                params["axis"] = value

        return params if params.get("columns") else None

    def _extract_merge(self, node: ast.Call) -> Optional[Dict[str, Any]]:
        """提取 pd.merge() 调用"""
        params = {}

        if len(node.args) >= 2:
            params["left_df"] = self._get_value(node.args[0])
            params["right_df"] = self._get_value(node.args[1])

        for keyword in node.keywords:
            key = keyword.arg
            value = self._get_value(keyword.value)
            if key == "on":
                params["on"] = value
            elif key == "how":
                params["how"] = value
            elif key == "left_on":
                params["left_on"] = value
            elif key == "right_on":
                params["right_on"] = value

        return params if params.get("on") else None

    def _extract_groupby(self, node: ast.Call) -> Optional[Dict[str, Any]]:
        """提取 df.groupby() 调用"""
        params = {}

        if isinstance(node.func, ast.Attribute):
            df_name = self._get_value(node.func.value) if hasattr(node.func.value, 'id') else None
            if df_name:
                params["df"] = df_name

        if node.args:
            params["by"] = self._get_value(node.args[0])

        for keyword in node.keywords:
            key = keyword.arg
            value = self._get_value(keyword.value)
            if key == "as_index":
                params["as_index"] = value

        return params if params.get("by") else None

    def _detect_groupby_chain(self, node: ast.Call, var_name: Optional[str]) -> Optional[Dict[str, Any]]:
        """检测并处理 groupby().agg() 链式调用

        例如: grouped = df.groupby('category').agg({'sales': 'sum'})
        """
        if not isinstance(node.func, ast.Attribute):
            return None

        # node 是 agg() 调用，它的 value 应该是 groupby() 调用
        groupby_call = node.func.value
        if not isinstance(groupby_call, ast.Call):
            return None

        if not isinstance(groupby_call.func, ast.Attribute):
            return None

        if groupby_call.func.attr != "groupby":
            return None

        # 提取 groupby 的参数
        params = {}

        # 提取 df 名称（groupby 调用的对象）
        if isinstance(groupby_call.func.value, ast.Name):
            params["df"] = groupby_call.func.value.id

        # 提取 by 参数
        if groupby_call.args:
            params["by"] = self._get_value(groupby_call.args[0])

        return params if params.get("by") else None

    def _extract_sort_values(self, node: ast.Call) -> Optional[Dict[str, Any]]:
        """提取 df.sort_values() 调用"""
        params = {}

        if isinstance(node.func, ast.Attribute):
            df_name = self._get_value(node.func.value) if hasattr(node.func.value, 'id') else None
            if df_name:
                params["df"] = df_name

        for keyword in node.keywords:
            key = keyword.arg
            value = self._get_value(keyword.value)
            if key == "by":
                params["by"] = value
            elif key == "ascending":
                params["ascending"] = value
            elif key == "na_position":
                params["na_position"] = value

        return params if params.get("by") else None

    def _extract_to_excel(self, node: ast.Call) -> Optional[Dict[str, Any]]:
        """提取 df.to_excel() 调用"""
        params = {}

        if isinstance(node.func, ast.Attribute):
            df_name = self._get_value(node.func.value) if hasattr(node.func.value, 'id') else None
            if df_name:
                params["df"] = df_name

        if node.args:
            params["file"] = self._get_value(node.args[0])

        for keyword in node.keywords:
            key = keyword.arg
            value = self._get_value(keyword.value)
            if key == "index":
                params["index"] = value

        return params if params.get("file") else None

    def _extract_to_csv(self, node: ast.Call) -> Optional[Dict[str, Any]]:
        """提取 df.to_csv() 调用"""
        params = {}

        if isinstance(node.func, ast.Attribute):
            df_name = self._get_value(node.func.value) if hasattr(node.func.value, 'id') else None
            if df_name:
                params["df"] = df_name

        if node.args:
            params["file"] = self._get_value(node.args[0])

        for keyword in node.keywords:
            key = keyword.arg
            value = self._get_value(keyword.value)
            if key == "index":
                params["index"] = value
            elif key == "encoding":
                params["encoding"] = value

        return params if params.get("file") else None

    def _add_step(self, action: str, params: Dict[str, Any]):
        """添加步骤"""
        self.step_counter += 1
        self.steps.append({
            "step": self.step_counter,
            "action": action,
            "params": params
        })

    def _extract_sop_name(self, code: str) -> str:
        """从代码中提取 SOP 名称"""
        # 尝试从注释中提取
        comment_pattern = r"#\s*SOP[:：]?\s*(.+)"
        match = re.search(comment_pattern, code)
        if match:
            return match.group(1).strip()

        # 尝试从函数名提取
        func_pattern = r"def\s+(\w+)\s*\("
        match = re.search(func_pattern, code)
        if match:
            func_name = match.group(1)
            # 将下划线分隔的名称转换为标题
            return " ".join(word.capitalize() for word in func_name.split("_"))

        return "未命名 SOP"


def ParserCodeToSOP(code: str) -> Dict[str, Any]:
    """将 Python 代码解析为 SOP 字典

    Args:
        code: Python 代码字符串

    Returns:
        SOP 字典（包含 name, description, steps 数组）
    """
    parser = CodeParser()
    return parser.parse(code)


# 测试代码
if __name__ == "__main__":
    # 测试用例
    test_code = '''
    # SOP: 销售数据分析流程
    import pandas as pd

    # 读取数据
    coach = pd.read_excel('coach.xlsx', sheet_name='Sheet1', skiprows=2)
    finance = pd.read_csv('finance.csv')

    # 筛选数据
    coach_filtered = coach.query("region == '华东'")

    # 合并数据
    result = pd.merge(coach_filtered, finance, on='id', how='left')

    # 分组聚合
    grouped = result.groupby('region').agg({'sales': 'sum'})

    # 排序
    sorted_data = grouped.sort_values(by='sales', ascending=False)

    # 导出结果
    sorted_data.to_excel('output.xlsx')
    '''

    print("=" * 60)
    print("测试 1: 完整函数解析")
    print("=" * 60)
    sop = ParserCodeToSOP(test_code)
    print(f"名称: {sop['name']}")
    print(f"描述: {sop['description']}")
    print(f"步骤数量: {len(sop['steps'])}")
    for step in sop['steps']:
        print(f"  步骤 {step['step']}: {step['action']}")
        print(f"    参数: {step['params']}")

    print("\n" + "=" * 60)
    print("测试 2: pd.read_excel 解析")
    print("=" * 60)
    code2 = "df = pd.read_excel('data.xlsx', sheet_name='Sheet1', skiprows=2)"
    sop2 = ParserCodeToSOP(code2)
    print(f"名称: {sop2['name']}")
    for step in sop2['steps']:
        print(f"  步骤 {step['step']}: {step['action']} - {step['params']}")

    print("\n" + "=" * 60)
    print("测试 3: filter 解析")
    print("=" * 60)
    code3 = '''
    df = pd.read_excel('data.xlsx')
    filtered = df.query("age > 25")
    '''
    sop3 = ParserCodeToSOP(code3)
    for step in sop3['steps']:
        print(f"  步骤 {step['step']}: {step['action']} - {step['params']}")

    print("\n" + "=" * 60)
    print("测试 4: merge 解析")
    print("=" * 60)
    code4 = "result = pd.merge(df1, df2, on='id', how='left')"
    sop4 = ParserCodeToSOP(code4)
    for step in sop4['steps']:
        print(f"  步骤 {step['step']}: {step['action']} - {step['params']}")

    print("\n" + "=" * 60)
    print("测试 5: groupby 解析")
    print("=" * 60)
    code5 = "grouped = df.groupby('category').agg({'sales': 'sum'})"
    sop5 = ParserCodeToSOP(code5)
    for step in sop5['steps']:
        print(f"  步骤 {step['step']}: {step['action']} - {step['params']}")

    print("\n所有测试完成!")

    # 测试新功能
    print("\n" + "=" * 60)
    print("测试 6: df[df['col'] == value] 括号过滤解析")
    print("=" * 60)
    code6 = '''
    df = pd.read_excel('data.xlsx')
    filtered = df[df['age'] > 25]
    '''
    sop6 = ParserCodeToSOP(code6)
    print(f"步骤数量: {len(sop6['steps'])}")
    for step in sop6['steps']:
        print(f"  步骤 {step['step']}: {step['action']} - {step['params']}")

    print("\n" + "=" * 60)
    print("测试 7: del df['column'] 删除列解析")
    print("=" * 60)
    code7 = '''
    df = pd.read_excel('data.xlsx')
    del df['unused_column']
    '''
    sop7 = ParserCodeToSOP(code7)
    print(f"步骤数量: {len(sop7['steps'])}")
    for step in sop7['steps']:
        print(f"  步骤 {step['step']}: {step['action']} - {step['params']}")
