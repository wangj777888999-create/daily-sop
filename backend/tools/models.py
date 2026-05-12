from pydantic import BaseModel
from typing import List, Optional


class CheckinPreview(BaseModel):
    columns: List[str]
    rows: List[dict]
    total_rows: int
    coach_file: str
    finance_file: str


class CheckinProcessResult(BaseModel):
    batch_id: int
    record_count: int
    skipped_count: int
    check_date: str
    summary: dict


class CheckinHistory(BaseModel):
    id: int
    batch_date: str
    coach_file: str
    finance_file: str
    record_count: int
    status: str
    created_at: str
