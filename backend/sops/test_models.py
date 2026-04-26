import pytest
from datetime import datetime
from models import DataSource, Step, SOP

def test_data_source_model():
    ds = DataSource(
        id="ds_1",
        name="教练签到表",
        type="primary",
        variableName="coach",
        operation="read",
        codeSnippet="coach = pd.read_excel('test.xlsx')",
        lineNumber=10
    )
    assert ds.name == "教练签到表"
    assert ds.type == "primary"

def test_sop_with_data_sources():
    step = Step(step=1, action="read_excel", params={"file": "test.xlsx"})
    ds = DataSource(
        id="ds_1",
        name="教练签到表",
        type="primary",
        variableName="coach",
        operation="read",
        codeSnippet="coach = pd.read_excel('test.xlsx')",
        lineNumber=10
    )
    sop = SOP(
        id="sop_1",
        name="测试SOP",
        description="测试",
        steps=[step],
        dataSources=[ds],
        tags=[],
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    assert len(sop.dataSources) == 1
    assert sop.dataSources[0].name == "教练签到表"