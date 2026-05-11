import os
import uuid
import logging
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from typing import List, Optional
from datetime import datetime

from knowledge.models import (KnowledgeDocument, ParsedDocument, SearchResult,
                               RAGRequest, RAGResponse, Folder, DocType)
from knowledge.storage import (get_all_docs, get_doc, save_doc, delete_doc,
                                 get_all_folders, save_folder, delete_folder,
                                 get_all_tags, ensure_dirs)
from knowledge.parser import parse_document, compute_content_hash
from knowledge.chunker import chunk_document
from knowledge.embedder import get_embedding_service
from knowledge.vector_store import VectorStore
from knowledge.rag import RAGPipeline

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data")
KB_FILES_DIR = os.path.join(DATA_DIR, "knowledge_files")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma_db")
os.makedirs(KB_FILES_DIR, exist_ok=True)
os.makedirs(CHROMA_DIR, exist_ok=True)
ensure_dirs()

_vector_store: VectorStore = None
_rag_pipeline: RAGPipeline = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore(CHROMA_DIR)
    return _vector_store


def get_rag_pipeline() -> RAGPipeline:
    global _rag_pipeline
    if _rag_pipeline is None:
        embedder = get_embedding_service()
        vs = get_vector_store()
        _rag_pipeline = RAGPipeline(embedder, vs)
    return _rag_pipeline


ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls", ".txt", ".md"}
EXT_TO_TYPE = {
    ".pdf": "PDF", ".docx": "DOCX", ".xlsx": "XLSX", ".xls": "XLSX",
    ".txt": "TXT", ".md": "MD",
}


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
    ext = os.path.splitext(file.filename or "")[1].lower()
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
        doc.chunk_count = len(chunks)
        doc.parsed_at = datetime.now()

        embedder = get_embedding_service()
        chunk_texts = [c["text"] for c in chunks]
        embeddings = embedder.embed_texts(chunk_texts)

        vs = get_vector_store()
        vs.add_chunks(doc_id, doc.name, chunks, embeddings)
    except Exception as e:
        logger.error(f"Failed to parse/embed document {doc_id}: {e}")
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
    vs = get_vector_store()
    vs.delete_doc(doc_id)
    delete_doc(doc_id)
    import shutil
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
def search_knowledge(query: str, top_k: int = 10, doc_ids: str = None):
    """Semantic vector search across the knowledge base."""
    doc_id_list = [d.strip() for d in doc_ids.split(",") if d.strip()] if doc_ids else None
    pipeline = get_rag_pipeline()
    results = pipeline.retrieve(query, top_k=top_k, doc_ids=doc_id_list)
    return [r.model_dump(mode="json") for r in results]


# ──────────────────── RAG Generate ────────────────────

@router.post("/knowledge/generate")
def generate_content(request: RAGRequest):
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    pipeline = get_rag_pipeline()
    response = pipeline.generate(request, api_key=api_key)
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

    vs = get_vector_store()
    vs.delete_doc(doc_id)

    parsed = parse_document(file_path, doc.type.value)
    parsed.doc_id = doc_id
    chunks = chunk_document(parsed)
    doc.chunk_count = len(chunks)
    doc.parsed_at = datetime.now()

    embedder = get_embedding_service()
    chunk_texts = [c["text"] for c in chunks]
    embeddings = embedder.embed_texts(chunk_texts)
    vs.add_chunks(doc_id, doc.name, chunks, embeddings)

    save_doc(doc)
    return {"message": f"Reparsed {len(chunks)} chunks", "chunk_count": len(chunks)}
