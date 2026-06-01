try:
    import fcntl
except ImportError:
    fcntl = None

import json
import os
import shutil
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

router = APIRouter()

# ── Paths ──────────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # repo root
DATA_DIR = os.path.join(_HERE, "data", "campus_reports")
INDEX_PATH = os.path.join(DATA_DIR, "index.json")

ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20 MB


# ── Low-level JSON helpers ─────────────────────────────────────────────────────
def _ensure_dirs(school_id: Optional[str] = None):
    os.makedirs(DATA_DIR, exist_ok=True)
    if school_id:
        os.makedirs(os.path.join(DATA_DIR, school_id), exist_ok=True)
        os.makedirs(os.path.join(DATA_DIR, school_id, "images"), exist_ok=True)


def _read_json(path: str, default):
    if not os.path.exists(path):
        return default
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


# ── School index helpers ───────────────────────────────────────────────────────
def _load_schools() -> List[dict]:
    _ensure_dirs()
    return _read_json(INDEX_PATH, [])


def _save_schools(schools: List[dict]):
    _ensure_dirs()
    _write_json(INDEX_PATH, schools)


# ── Section helpers ────────────────────────────────────────────────────────────
def _section_path(school_id: str, section_id: str) -> str:
    return os.path.join(DATA_DIR, school_id, f"{section_id}.json")


def _load_sections(school_id: str) -> List[dict]:
    school_dir = os.path.join(DATA_DIR, school_id)
    if not os.path.isdir(school_dir):
        return []
    sections = []
    for fname in os.listdir(school_dir):
        if fname.endswith(".json"):
            data = _read_json(os.path.join(school_dir, fname), None)
            if data and "id" in data:
                sections.append(data)
    sections.sort(key=lambda s: s.get("order", 0))
    return sections


# ── Pydantic models ────────────────────────────────────────────────────────────
class SchoolCreate(BaseModel):
    name: str


class SectionCreate(BaseModel):
    title: str = "新板块"


class SectionUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    order: Optional[int] = None


# ── School endpoints ───────────────────────────────────────────────────────────
@router.get("/campus-reports/schools")
def list_schools():
    return _load_schools()


@router.post("/campus-reports/schools", status_code=201)
def create_school(body: SchoolCreate):
    schools = _load_schools()
    if any(s["name"] == body.name for s in schools):
        raise HTTPException(400, detail=f"学校「{body.name}」已存在")
    school = {
        "id": str(uuid.uuid4()),
        "name": body.name,
        "created_at": datetime.now().isoformat(),
    }
    schools.append(school)
    _save_schools(schools)
    _ensure_dirs(school["id"])
    return school


@router.delete("/campus-reports/schools/{school_id}", status_code=204)
def delete_school(school_id: str):
    schools = _load_schools()
    schools = [s for s in schools if s["id"] != school_id]
    _save_schools(schools)
    school_dir = os.path.join(DATA_DIR, school_id)
    if os.path.isdir(school_dir):
        shutil.rmtree(school_dir)
    return JSONResponse(status_code=204, content=None)


# ── Section endpoints ──────────────────────────────────────────────────────────
@router.get("/campus-reports/schools/{school_id}/sections")
def list_sections(school_id: str):
    return _load_sections(school_id)


@router.post("/campus-reports/schools/{school_id}/sections", status_code=201)
def create_section(school_id: str, body: SectionCreate):
    _ensure_dirs(school_id)
    existing = _load_sections(school_id)
    section = {
        "id": str(uuid.uuid4()),
        "title": body.title,
        "content": "",
        "images": [],
        "order": len(existing),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    _write_json(_section_path(school_id, section["id"]), section)
    return section


@router.put("/campus-reports/schools/{school_id}/sections/{section_id}")
def update_section(school_id: str, section_id: str, body: SectionUpdate):
    path = _section_path(school_id, section_id)
    section = _read_json(path, None)
    if section is None:
        raise HTTPException(404, detail="板块不存在")
    if body.title is not None:
        section["title"] = body.title
    if body.content is not None:
        section["content"] = body.content
    if body.order is not None:
        section["order"] = body.order
    section["updated_at"] = datetime.now().isoformat()
    _write_json(path, section)
    return section


@router.delete("/campus-reports/schools/{school_id}/sections/{section_id}", status_code=204)
def delete_section(school_id: str, section_id: str):
    path = _section_path(school_id, section_id)
    if os.path.exists(path):
        os.remove(path)
    return JSONResponse(status_code=204, content=None)


# ── Image endpoints ────────────────────────────────────────────────────────────
@router.post("/campus-reports/schools/{school_id}/images", status_code=201)
async def upload_image(school_id: str, file: UploadFile = File(...)):
    _ensure_dirs(school_id)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_IMAGE_EXTS:
        raise HTTPException(400, detail=f"不支持的图片格式: {ext}")
    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(400, detail="图片超过 20MB 限制")
    filename = f"{uuid.uuid4()}{ext}"
    dest = os.path.join(DATA_DIR, school_id, "images", filename)
    with open(dest, "wb") as f:
        f.write(content)
    return {"filename": filename, "url": f"/api/campus-reports/schools/{school_id}/images/{filename}"}


@router.delete("/campus-reports/schools/{school_id}/images/{filename}", status_code=204)
def delete_image(school_id: str, filename: str):
    path = os.path.join(DATA_DIR, school_id, "images", filename)
    if os.path.exists(path):
        os.remove(path)
    return JSONResponse(status_code=204, content=None)


@router.get("/campus-reports/schools/{school_id}/images/{filename}")
def serve_image(school_id: str, filename: str):
    path = os.path.join(DATA_DIR, school_id, "images", filename)
    if not os.path.exists(path):
        raise HTTPException(404, detail="图片不存在")
    return FileResponse(path)
