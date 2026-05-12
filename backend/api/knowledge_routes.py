import os
import uuid
import logging
import shutil
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel as PydanticBaseModel
from fastapi.responses import FileResponse
from typing import List, Optional
from datetime import datetime

from knowledge.models import (KnowledgeDocument, ParsedDocument, SearchResult,
                               RAGRequest, RAGResponse, Folder, DocType)
from knowledge.storage import (get_all_docs, get_doc, save_doc, delete_doc,
                                 get_all_folders, save_folder, delete_folder,
                                 get_all_tags, ensure_dirs, save_chunks, delete_doc_chunks)
from knowledge.parser import parse_document, compute_content_hash
from knowledge.chunker import chunk_document
from knowledge.indexer import BM25Index
from knowledge.rag import RAGPipeline

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data")
KB_FILES_DIR = os.path.join(DATA_DIR, "knowledge_files")
os.makedirs(KB_FILES_DIR, exist_ok=True)
ensure_dirs()


def _get_bm25_index() -> BM25Index:
    from main import app
    index = getattr(app.state, "bm25_index", None)
    if index is None:
        raise HTTPException(status_code=503, detail="知识库索引未就绪，请稍后重试")
    return index


def _get_rag_pipeline() -> RAGPipeline:
    return RAGPipeline(_get_bm25_index())


ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls", ".txt", ".md"}
EXT_TO_TYPE = {
    ".pdf": "PDF", ".docx": "DOCX", ".xlsx": "XLSX", ".xls": "XLSX",
    ".txt": "TXT", ".md": "MD",
}


class SearchRequest(PydanticBaseModel):
    query: str
    top_k: int = 10
    doc_ids: Optional[List[str]] = None


class GenerateRequest(PydanticBaseModel):
    prompt: str
    style: str = "policy"
    top_k: int = 5
    doc_ids: Optional[List[str]] = None


# ──────────────────── Document CRUD ────────────────────

@router.get("/knowledge/documents")
def list_documents(folder_id: str = None, type: str = None,
                   tag: str = None, sort_by: str = "created_at",
                   order: str = "desc"):
    docs = get_all_docs()
    if folder_id:
        docs = [d for d in docs if d.folder_id == folder_id]
    if type:
        docs = [d for d in docs if d.type.value == type.upper()]
    if tag:
        docs = [d for d in docs if tag in d.tags]
    docs.sort(key=lambda d: getattr(d, sort_by, d.created_at),
              reverse=(order == "desc"))
    return [d.model_dump(mode="json") for d in docs]


@router.get("/knowledge/documents/{doc_id}")
def get_document(doc_id: str):
    doc = get_doc(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc.model_dump(mode="json")


@router.post("/knowledge/documents")
async def upload_document(file: UploadFile = File(...),
                           folder_id: str = Form(""),
                           tags: str = Form("")):
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400,
                            detail=f"不支持的文件类型: {ext}。支持: {', '.join(ALLOWED_EXTENSIONS)}")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小超过 100MB 限制")

    doc_id = uuid.uuid4().hex[:12]
    doc_dir = os.path.join(KB_FILES_DIR, doc_id)
    os.makedirs(doc_dir, exist_ok=True)
    file_path = os.path.join(doc_dir, file.filename)

    with open(file_path, "wb") as f:
        f.write(contents)

    content_hash = compute_content_hash(file_path)
    doc_type = EXT_TO_TYPE.get(ext, "TXT")
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    doc = KnowledgeDocument(
        id=doc_id,
        name=file.filename,
        type=DocType(doc_type),
        size_bytes=len(contents),
        folder_id=folder_id or None,
        tags=tag_list,
        content_hash=content_hash,
    )

    try:
        parsed = parse_document(file_path, doc_type)
        parsed.doc_id = doc_id
        chunks = chunk_document(parsed)

        # Enrich chunks with doc metadata for BM25
        for c in chunks:
            c["doc_id"] = doc_id
            c["doc_name"] = file.filename
            c["id"] = f"{doc_id}_chunk_{c.get('chunk_index', 0)}"

        doc.chunk_count = len(chunks)
        doc.parsed_at = datetime.now()

        # Save chunks to JSON and update BM25 index
        save_chunks(doc_id, chunks)
        index = _get_bm25_index()
        index.add_chunks(chunks)
    except Exception as e:
        logger.error(f"Failed to parse document {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=f"文档解析失败: {str(e)}")

    save_doc(doc)
    return doc.model_dump(mode="json")


@router.put("/knowledge/documents/{doc_id}")
def update_document(doc_id: str, name: str = None, folder_id: str = None,
                    tags: List[str] = None):
    doc = get_doc(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if name is not None:
        doc.name = name
    if folder_id is not None:
        doc.folder_id = folder_id
    if tags is not None:
        doc.tags = tags
    doc.updated_at = datetime.now()
    save_doc(doc)
    return doc.model_dump(mode="json")


@router.delete("/knowledge/documents/{doc_id}")
def delete_document(doc_id: str):
    doc = get_doc(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove from BM25 index and chunks file
    index = _get_bm25_index()
    index.remove_doc(doc_id)
    delete_doc_chunks(doc_id)

    # Remove metadata
    delete_doc(doc_id)

    # Remove files
    doc_dir = os.path.join(KB_FILES_DIR, doc_id)
    if os.path.exists(doc_dir):
        shutil.rmtree(doc_dir)

    return {"message": "Document deleted successfully"}


# ──────────────────── Content & Download ────────────────────

@router.get("/knowledge/documents/{doc_id}/content")
def get_document_content(doc_id: str):
    doc = get_doc(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc_dir = os.path.join(KB_FILES_DIR, doc_id)
    if not os.path.exists(doc_dir):
        raise HTTPException(status_code=404, detail="Document files not found")
    files = os.listdir(doc_dir)
    if not files:
        raise HTTPException(status_code=404, detail="Document file not found")
    file_path = os.path.join(doc_dir, files[0])
    doc_type = doc.type.value
    parsed = parse_document(file_path, doc_type)
    return parsed.model_dump(mode="json")


@router.get("/knowledge/documents/{doc_id}/download")
def download_document(doc_id: str):
    doc = get_doc(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc_dir = os.path.join(KB_FILES_DIR, doc_id)
    if not os.path.exists(doc_dir):
        raise HTTPException(status_code=404, detail="Document not found")
    files = os.listdir(doc_dir)
    if not files:
        raise HTTPException(status_code=404, detail="Document not found")
    file_path = os.path.join(doc_dir, files[0])
    return FileResponse(file_path, filename=doc.name)


# ──────────────────── Search ────────────────────

@router.post("/knowledge/search")
def search_knowledge(body: SearchRequest):
    """BM25 keyword search across the knowledge base."""
    pipeline = _get_rag_pipeline()
    results = pipeline.retrieve(body.query, top_k=body.top_k, doc_ids=body.doc_ids)
    return [r.model_dump(mode="json") for r in results]


# ──────────────────── RAG Generate ────────────────────

@router.post("/knowledge/generate")
def generate_content(body: GenerateRequest):
    request = RAGRequest(prompt=body.prompt, style=body.style, top_k=body.top_k, doc_ids=body.doc_ids)
    pipeline = _get_rag_pipeline()
    response = pipeline.generate(request)
    return response.model_dump(mode="json")


# ──────────────────── Folders ────────────────────

@router.get("/knowledge/folders")
def list_folders():
    folders = get_all_folders()
    return [f.model_dump(mode="json") for f in folders]


@router.post("/knowledge/folders")
def create_folder(folder: Folder):
    return save_folder(folder).model_dump(mode="json")


@router.put("/knowledge/folders/{folder_id}")
def update_folder(folder_id: str, name: str):
    from knowledge.storage import get_folder
    f = get_folder(folder_id)
    if not f:
        raise HTTPException(status_code=404, detail="Folder not found")
    f.name = name
    return save_folder(f).model_dump(mode="json")


@router.delete("/knowledge/folders/{folder_id}")
def delete_folder_endpoint(folder_id: str):
    ok = delete_folder(folder_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Folder not found")
    return {"message": "Folder deleted successfully"}


# ──────────────────── Tags ────────────────────

@router.get("/knowledge/tags")
def list_tags():
    return get_all_tags()


# ──────────────────── Reparse ────────────────────

@router.post("/knowledge/reparse/{doc_id}")
def reparse_document(doc_id: str):
    doc = get_doc(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc_dir = os.path.join(KB_FILES_DIR, doc_id)
    files = os.listdir(doc_dir) if os.path.exists(doc_dir) else []
    if not files:
        raise HTTPException(status_code=404, detail="Document file not found")
    file_path = os.path.join(doc_dir, files[0])

    # Remove old chunks from BM25 index
    index = _get_bm25_index()
    index.remove_doc(doc_id)
    delete_doc_chunks(doc_id)

    # Re-parse
    parsed = parse_document(file_path, doc.type.value)
    parsed.doc_id = doc_id
    chunks = chunk_document(parsed)

    # Enrich chunks with doc metadata
    for c in chunks:
        c["doc_id"] = doc_id
        c["doc_name"] = doc.name
        c["id"] = f"{doc_id}_chunk_{c.get('chunk_index', 0)}"

    doc.chunk_count = len(chunks)
    doc.parsed_at = datetime.now()

    # Save and update index
    save_chunks(doc_id, chunks)
    index.add_chunks(chunks)
    save_doc(doc)

    return {"message": f"Reparsed {len(chunks)} chunks", "chunk_count": len(chunks)}
