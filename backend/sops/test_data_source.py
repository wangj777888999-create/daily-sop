import pytest
from sops.data_source import (
    infer_name_from_path,
    DataSourceDetector,
    SemanticInferencer
)


class TestInferNameFromPath:
    """测试 infer_name_from_path 函数"""

    def test_simple_xlsx(self):
        """测试简单 xlsx 文件名"""
        assert infer_name_from_path('data.xlsx') == 'data表'

    def test_simple_csv(self):
        """测试 csv 文件名"""
        assert infer_name_from_path('report.csv') == 'report表'

    def test_with_path(self):
        """测试带路径的文件名"""
        result = infer_name_from_path('C:\\Users\\coach.xlsx')
        assert 'coach' in result
        assert '教练' in result or '表' in result

    def test_with_numbers_in_parentheses(self):
        """测试带括号数字后缀"""
        assert infer_name_from_path('销售数据(53).xlsx') == '销售数据(53)表'

    def test_output_keyword(self):
        """测试 output 关键词添加结果后缀"""
        assert infer_name_from_path('output.xlsx') == 'output结果'

    def test_result_keyword(self):
        """测试 result 关键词"""
        assert infer_name_from_path('result.csv') == 'result结果'

    def test_coach_keyword(self):
        """测试 coach 关键词"""
        result = infer_name_from_path('coach.xlsx')
        assert 'coach' in result


class TestDetectReadExcel:
    """测试 detect 方法检测 read_excel"""

    def test_detect_single_read_excel(self):
        """测试检测单个 read_excel"""
        code = "coach = pd.read_excel('C:\\\\Users\\\\coach.xlsx', sheet_name='教练签到')"

        detector = DataSourceDetector()
        sources = detector.detect(code)

        assert len(sources) == 1
        assert sources[0].operation == 'read'
        assert sources[0].type == 'primary'
        assert sources[0].variableName == 'coach'

    def test_detect_multiple_sources(self):
        """测试检测多个数据源（包含 read 和 write）"""
        code = '''
coach = pd.read_excel('C:\\\\Users\\\\coach.xlsx', sheet_name='教练签到')
finance = pd.read_excel('C:\\\\Users\\\\finance.xlsx', sheet_name='财务')
result.to_excel('C:\\\\Users\\\\output.xlsx')
'''

        detector = DataSourceDetector()
        sources = detector.detect(code)

        assert len(sources) == 3

        # coach: read, primary
        coach_ds = next(ds for ds in sources if ds.variableName == 'coach')
        assert coach_ds.operation == 'read'
        assert coach_ds.type == 'primary'

        # finance: read, reference
        finance_ds = next(ds for ds in sources if ds.variableName == 'finance')
        assert finance_ds.operation == 'read'
        assert finance_ds.type == 'reference'

        # result: write, output
        result_ds = next(ds for ds in sources if ds.variableName == 'result')
        assert result_ds.operation == 'write'
        assert result_ds.type == 'output'


class TestGenerateDescription:
    """测试 generate_description 方法"""

    def test_read_excel_description(self):
        """测试 read_excel 描述生成"""
        inferencer = SemanticInferencer()
        desc = inferencer.generate_description('read_excel', {'file': 'data.xlsx'})
        assert '读取' in desc
        assert 'data' in desc

    def test_read_csv_description(self):
        """测试 read_csv 描述生成"""
        inferencer = SemanticInferencer()
        desc = inferencer.generate_description('read_csv', {'file': 'report.csv'})
        assert '读取' in desc
        assert 'report' in desc

    def test_filter_description(self):
        """测试 filter 描述生成"""
        inferencer = SemanticInferencer()
        desc = inferencer.generate_description('filter', {'condition': "age > 25"})
        assert '筛选' in desc
        assert 'age > 25' in desc

    def test_drop_columns_description(self):
        """测试 drop_columns 描述生成"""
        inferencer = SemanticInferencer()
        desc = inferencer.generate_description('drop_columns', {'columns': 'unused_col'})
        assert '删除' in desc
        assert 'unused_col' in desc

    def test_groupby_description(self):
        """测试 groupby 描述生成"""
        inferencer = SemanticInferencer()
        desc = inferencer.generate_description('groupby', {'by': 'region'})
        assert '按' in desc
        assert 'region' in desc
        assert '分组统计' in desc

    def test_sort_description(self):
        """测试 sort 描述生成"""
        inferencer = SemanticInferencer()
        desc = inferencer.generate_description('sort', {'by': 'sales'})
        assert '按' in desc
        assert 'sales' in desc
        assert '排序' in desc

    def test_to_excel_description(self):
        """测试 to_excel 描述生成"""
        inferencer = SemanticInferencer()
        desc = inferencer.generate_description('to_excel', {'file': 'output.xlsx'})
        assert '导出' in desc
        assert 'output' in desc

    def test_to_csv_description(self):
        """测试 to_csv 描述生成"""
        inferencer = SemanticInferencer()
        desc = inferencer.generate_description('to_csv', {'file': 'result.csv'})
        assert '导出' in desc
        assert 'result' in desc

    def test_merge_description(self):
        """测试 merge 描述生成"""
        inferencer = SemanticInferencer()
        desc = inferencer.generate_description('merge', {})
        assert '合并数据' in desc