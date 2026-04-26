import ast
import re
from typing import List, Optional
from .models import DataSource


def infer_name_from_path(file_path: str) -> str:
    """从文件路径推断数据源名称

    规则：
    1. 去除文件扩展名
    2. 去除路径中的目录
    3. 去除括号内的数字后缀（如 (53)）
    4. 添加业务后缀（数据/表/结果）
    """
    if not file_path:
        return "未命名数据"

    # 去除扩展名
    name = file_path
    for ext in ['.xlsx', '.xls', '.csv', '.json', '.parquet', '.txt']:
        if name.lower().endswith(ext):
            name = name[:-len(ext)]
            break

    # 去除路径中的目录
    name = name.replace('\\', '/')
    if '/' in name:
        name = name.split('/')[-1]

    # 去除括号内的数字后缀，如 "(53)" -> ""
    name = re.sub(r'\s*\(\d+\)\s*$', '', name)

    # 添加业务后缀（避免重复）
    name = name.strip()
    if name:
        # 如果已经包含后缀关键词，不再添加
        if any(suffix in name for suffix in ['数据', '表', '结果']):
            return name

        # 如果名称包含"财务"，返回"财务数据"
        if '财务' in name:
            return "财务数据"
        # 如果名称包含"教练"或"签到"，返回"教练签到表"
        elif '教练' in name or '签到' in name:
            return "教练签到表"
        # 如果名称包含"部门"或"划分"，返回"部门划分表"
        elif '部门' in name or '划分' in name:
            return "部门划分表"
        # 根据常见关键词添加后缀
        elif any(kw in name.lower() for kw in ['output', 'result', 'export', 'out']):
            return f"{name}结果"
        else:
            return f"{name}表"

    return "未命名数据"


class DataSourceDetector:
    """从 AST 中检测数据读写操作"""

    def detect(self, code: str) -> List[DataSource]:
        """检测代码中的所有数据源

        自动推断类型：
        - 第一个 read 操作 → primary
        - 其余 read 操作 → reference
        - 第一个 write 操作 → output
        """
        data_sources: List[DataSource] = []
        read_count = 0
        write_count = 0

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return data_sources

        # 遍历所有节点（包括函数内部的节点）
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        var_name = target.id
                        if isinstance(node.value, ast.Call):
                            # pd.read_excel / pd.read_csv
                            func_name = self._get_func_name(node.value.func)
                            if func_name in ('read_excel', 'read_csv'):
                                # 跳过函数定义中的参数（如 def foo(df=pd.read_excel(...)）
                                if self._is_inside_function_def(node, tree):
                                    continue

                                read_count += 1
                                if read_count == 1:
                                    ds_type = 'primary'
                                else:
                                    ds_type = 'reference'

                                params = self._extract_read_params(node.value)
                                file_path = params.get('file', '')

                                data_sources.append(DataSource(
                                    id=f"ds_{len(data_sources) + 1}",
                                    name=infer_name_from_path(file_path),
                                    type=ds_type,
                                    variableName=var_name,
                                    operation='read',
                                    codeSnippet=self._get_code_snippet(node.lineno, code),
                                    lineNumber=node.lineno or 0
                                ))

                            # df.to_excel / df.to_csv
                            elif func_name in ('to_excel', 'to_csv'):
                                write_count += 1
                                if write_count == 1:
                                    ds_type = 'output'
                                else:
                                    ds_type = 'output'

                                params = self._extract_write_params(node.value)
                                file_path = params.get('file', '')

                                data_sources.append(DataSource(
                                    id=f"ds_{len(data_sources) + 1}",
                                    name=infer_name_from_path(file_path),
                                    type=ds_type,
                                    variableName=var_name,
                                    operation='write',
                                    codeSnippet=self._get_code_snippet(node.lineno, code),
                                    lineNumber=node.lineno or 0
                                ))

        return data_sources

    def _is_inside_function_def(self, node: ast.AST, tree: ast.AST) -> bool:
        """检查节点是否在函数定义中作为默认参数"""
        for parent in ast.walk(tree):
            if isinstance(parent, ast.FunctionDef):
                for arg in parent.args.defaults:
                    if node in ast.walk(arg):
                        return True
        return False

    def _get_code_snippet(self, line_number: int, code: str) -> str:
        """获取指定行的代码片段"""
        if not line_number:
            return ""
        lines = code.split('\n')
        idx = line_number - 1
        if 0 <= idx < len(lines):
            return lines[idx].strip()
        return ""

    def _get_func_name(self, node: ast.AST) -> str:
        """获取函数名称"""
        if isinstance(node, ast.Attribute):
            return node.attr
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Call):
            return self._get_func_name(node.func)
        return ""

    def _get_value(self, node: ast.AST) -> any:
        """获取 AST 节点的值"""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Name):
            return node.id
        return None

    def _extract_read_params(self, node: ast.Call) -> dict:
        """提取读取参数"""
        params = {}
        if node.args:
            params['file'] = self._get_value(node.args[0])
        for keyword in node.keywords:
            key = keyword.arg
            value = self._get_value(keyword.value)
            if key == 'sheet_name':
                params['sheet_name'] = value
            elif key == 'skiprows':
                params['skiprows'] = value
        return params

    def _extract_write_params(self, node: ast.Call) -> dict:
        """提取写入参数"""
        params = {}
        if node.args:
            params['file'] = self._get_value(node.args[0])
        for keyword in node.keywords:
            key = keyword.arg
            value = self._get_value(keyword.value)
            if key == 'index':
                params['index'] = value
        return params


class SemanticInferencer:
    """语义推断器"""

    def generate_description(self, action: str, params: dict) -> str:
        """生成步骤描述

        规则表：
        | action      | 描述模板                                    |
        |-------------|---------------------------------------------|
        | read_excel  | 读取【{数据源名称}】                        |
        | read_csv    | 读取【{数据源名称}】                        |
        | filter      | 筛选【{条件摘要}】数据                      |
        | drop_columns| 删除【{列名}】列                            |
        | merge       | 合并数据                                    |
        | groupby     | 按【{by}】分组统计                          |
        | sort        | 按【{by}】排序                              |
        | to_excel    | 导出【{数据源名称}】                        |
        | to_csv      | 导出【{数据源名称}】                        |
        """
        templates = {
            'read_excel': "读取【{name}】",
            'read_csv': "读取【{name}】",
            'filter': "筛选【{condition}】数据",
            'drop_columns': "删除【{columns}】列",
            'merge': "合并数据",
            'groupby': "按【{by}】分组统计",
            'sort': "按【{by}】排序",
            'to_excel': "导出【{name}】",
            'to_csv': "导出【{name}】",
        }

        if action not in templates:
            return f"执行【{action}】操作"

        template = templates[action]

        # 根据 action 类型填充参数
        if action in ('read_excel', 'read_csv', 'to_excel', 'to_csv'):
            name = params.get('file', '')
            name = infer_name_from_path(name)
            return template.format(name=name)
        elif action == 'filter':
            condition = params.get('condition', '')
            return template.format(condition=condition)
        elif action == 'drop_columns':
            columns = params.get('columns', '')
            return template.format(columns=columns)
        elif action == 'groupby':
            by = params.get('by', '')
            return template.format(by=by)
        elif action == 'sort':
            by = params.get('by', '')
            return template.format(by=by)
        else:
            return template.format(**params)