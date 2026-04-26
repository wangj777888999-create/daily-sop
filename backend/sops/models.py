from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class Step(BaseModel):
    step: int
    action: str
    params: dict
    description: Optional[str] = ""

class DataSource(BaseModel):
    id: str
    name: str
    type: str
    variableName: str
    operation: str
    codeSnippet: str
    lineNumber: int

class SOP(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    steps: List[Step]
    dataSources: List[DataSource] = []
    tags: List[str] = []
    created_at: datetime
    updated_at: datetime

class ExecutionLog(BaseModel):
    id: str
    sop_id: str
    status: str
    input_files: List[str]
    output_file: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
