import json
import os
from typing import List, Optional
from .models import KnowledgeDocument, Folder

try:
    import fcntl
except ImportError:
    fcntl = None

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data")
META_FILE = os.path.join(DATA_DIR, "knowledge_metadata.json")
FOLDERS_FILE = os.path.join(DATA_DIR, "knowledge_folders.json")
CHUNKS_FILE = os.path.join(DATA_DIR, "knowledge_chunks.json")
KB_FILES_DIR = os.path.join(DATA_DIR, "knowledge_files")


def _read_json(path: str):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        if fcntl:
            fcntl.flock(f, fcntl.LOCK_SH)
        return json.load(f)


def _write_json(path: str, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        if fcntl:
            fcntl.flock(f, fcntl.LOCK_EX)
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def get_all_docs() -> List[KnowledgeDocument]:
    records = _read_json(META_FILE)
    return [KnowledgeDocument(**r) for r in records]


def get_doc(doc_id: str) -> Optional[KnowledgeDocument]:
    docs = get_all_docs()
    for d in docs:
        if d.id == doc_id:
            return d
    return None


def save_doc(doc: KnowledgeDocument) -> KnowledgeDocument:
    doc.updated_at = doc.__class__.model_fields["updated_at"].annotation(default_factory=lambda: None) or __import__("datetime").datetime.now()
    docs = get_all_docs()
    for i, existing in enumerate(docs):
        if existing.id == doc.id:
            docs[i] = doc
            _write_json(META_FILE, [d.model_dump(mode="json") for d in docs])
            return doc
    docs.append(doc)
    _write_json(META_FILE, [d.model_dump(mode="json") for d in docs])
    return doc


def delete_doc(doc_id: str) -> bool:
    docs = get_all_docs()
    new_docs = [d for d in docs if d.id != doc_id]
    if len(new_docs) == len(docs):
        return False
    _write_json(META_FILE, [d.model_dump(mode="json") for d in new_docs])
    return True


def get_all_folders() -> List[Folder]:
    records = _read_json(FOLDERS_FILE)
    return [Folder(**r) for r in records]


def get_folder(folder_id: str) -> Optional[Folder]:
    folders = get_all_folders()
    for f in folders:
        if f.id == folder_id:
            return f
    return None


def save_folder(folder: Folder) -> Folder:
    folders = get_all_folders()
    for i, existing in enumerate(folders):
        if existing.id == folder.id:
            folders[i] = folder
            _write_json(FOLDERS_FILE, [f.model_dump(mode="json") for f in folders])
            return folder
    folders.append(folder)
    _write_json(FOLDERS_FILE, [f.model_dump(mode="json") for f in folders])
    return folder


def delete_folder(folder_id: str) -> bool:
    folders = get_all_folders()
    new_folders = [f for f in folders if f.id != folder_id]
    if len(new_folders) == len(folders):
        return False
    _write_json(FOLDERS_FILE, [f.model_dump(mode="json") for f in new_folders])
    return True


def get_all_tags() -> List[str]:
    docs = get_all_docs()
    tags = set()
    for d in docs:
        for t in d.tags:
            tags.add(t)
    return sorted(tags)


def ensure_dirs():
    os.makedirs(KB_FILES_DIR, exist_ok=True)


def save_chunks(doc_id: str, chunks: List[dict]):
    """Append chunks for a doc to knowledge_chunks.json."""
    all_chunks = load_all_chunks()
    all_chunks = [c for c in all_chunks if c.get("doc_id") != doc_id]
    all_chunks.extend(chunks)
    _write_json(CHUNKS_FILE, all_chunks)


def load_all_chunks() -> List[dict]:
    """Load all chunks from knowledge_chunks.json."""
    return _read_json(CHUNKS_FILE)


def delete_doc_chunks(doc_id: str):
    """Remove all chunks for a doc from knowledge_chunks.json."""
    all_chunks = load_all_chunks()
    filtered = [c for c in all_chunks if c.get("doc_id") != doc_id]
    _write_json(CHUNKS_FILE, filtered)
