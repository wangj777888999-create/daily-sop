from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum
import uuid


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class DocType(str, Enum):
    PDF = "PDF"
    DOCX = "DOCX"
    XLSX = "XLSX"
    TXT = "TXT"
    MD = "MD"


class Folder(BaseModel):
    id: str = Field(default_factory=_new_id)
    name: str
    parent_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)


class ChunkMetadata(BaseModel):
    doc_id: str
    doc_name: str
    chunk_index: int
    chunk_type: str = "paragraph"
    heading_path: str = ""
    page: int = 0


class KnowledgeDocument(BaseModel):
    id: str = Field(default_factory=_new_id)
    name: str
    type: DocType
    size_bytes: int
    folder_id: Optional[str] = None
    tags: List[str] = []
    content_hash: str = ""
    chunk_count: int = 0
    parsed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ParsedDocument(BaseModel):
    doc_id: str
    full_text: str
    chunks: List[dict] = []


class SearchResult(BaseModel):
    doc_id: str
    doc_name: str
    doc_type: DocType
    chunk_text: str
    chunk_type: str
    heading_path: str
    score: float
    page: int = 0


class RAGRequest(BaseModel):
    prompt: str
    doc_ids: Optional[List[str]] = None
    style: str = "policy"
    top_k: int = 5


class RAGResponse(BaseModel):
    generated_text: str
    sources: List[dict] = []
