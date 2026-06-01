# Campus Report Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `/analytics` page with a campus service report management system — school folders with note-style sections (title + text + images) and a placeholder data-charts tab.

**Architecture:** New FastAPI router `campus_report_routes.py` handles all CRUD + file serving, backed by JSON files + a local `data/campus_reports/` directory. Vue side has a dedicated component tree under `src/ui/pages/analytics/components/`. No new npm packages required for this phase (charts deferred).

**Tech Stack:** FastAPI + Python stdlib (json, uuid, shutil, fcntl) · Vue 3 + TypeScript + Tailwind · Existing `databaseApi.query()` for the school-picker dropdown

---

## File Map

**Create (backend):**
- `backend/api/campus_report_routes.py` — all API endpoints + file serving
- `backend/api/test_campus_report_routes.py` — pytest tests for storage logic

**Modify (backend):**
- `backend/main.py` — mount new router

**Create (frontend):**
- `src/services/campusReportApi.ts` — typed fetch wrappers
- `src/ui/pages/analytics/components/SchoolSidebar.vue` — left panel: school list + create modal
- `src/ui/pages/analytics/components/ContentTab.vue` — content tab container (section list + editor side-by-side)
- `src/ui/pages/analytics/components/ChartsTab.vue` — placeholder charts tab

**Replace (frontend):**
- `src/ui/pages/analytics/AnalyticsPage.vue` — full rewrite as layout skeleton

**Modify (frontend):**
- `src/ui/components/layout/Sidebar.vue` — rename label from `高级数据分析` to `校园报告`

---

## Task 1: Backend — Storage helpers + campus_report_routes.py

**Files:**
- Create: `backend/api/campus_report_routes.py`

- [ ] **Step 1: Create the route file with storage helpers and all endpoints**

```python
# backend/api/campus_report_routes.py
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
```

- [ ] **Step 2: Verify the file was written cleanly**

```bash
cd /Users/wangjun/Desktop/ai_analyst_v2
python -c "import ast; ast.parse(open('backend/api/campus_report_routes.py').read()); print('syntax OK')"
```
Expected: `syntax OK`

- [ ] **Step 3: Commit**

```bash
git add backend/api/campus_report_routes.py
git commit -m "feat: add campus report backend routes (schools + sections + images)"
```

---

## Task 2: Mount the new router in main.py

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Add import and include_router**

In `backend/main.py`, add after the last `from api import ...` line:
```python
from api import campus_report_routes
```

Add after the last `app.include_router(...)` line:
```python
app.include_router(campus_report_routes.router, prefix="/api")
```

- [ ] **Step 2: Verify syntax**

```bash
cd /Users/wangjun/Desktop/ai_analyst_v2/backend
python -c "import ast; ast.parse(open('main.py').read()); print('syntax OK')"
```
Expected: `syntax OK`

- [ ] **Step 3: Start backend and smoke-test endpoints**

```bash
cd /Users/wangjun/Desktop/ai_analyst_v2/backend
source .venv/bin/activate
uvicorn main:app --port 8003 &
sleep 2
curl -s http://localhost:8003/api/campus-reports/schools
```
Expected: `[]`

```bash
curl -s -X POST http://localhost:8003/api/campus-reports/schools \
  -H "Content-Type: application/json" \
  -d '{"name": "测试校区"}' | python3 -m json.tool
```
Expected: JSON with `id`, `name`, `created_at` fields.

```bash
# clean up
kill %1 2>/dev/null; rm -rf data/campus_reports/
```

- [ ] **Step 4: Commit**

```bash
git add backend/main.py
git commit -m "feat: mount campus_report_routes in FastAPI app"
```

---

## Task 3: Frontend API service

**Files:**
- Create: `src/services/campusReportApi.ts`

- [ ] **Step 1: Create the typed API service**

```typescript
// src/services/campusReportApi.ts
const BASE = '/api/campus-reports'

export interface School {
  id: string
  name: string
  created_at: string
}

export interface Section {
  id: string
  title: string
  content: string
  images: string[]       // filenames, relative to the school's images/ dir
  order: number
  created_at: string
  updated_at: string
}

export interface UploadedImage {
  filename: string
  url: string
}

async function req<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || '请求失败')
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

function post<T>(url: string, body: unknown): Promise<T> {
  return req<T>(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

function put<T>(url: string, body: unknown): Promise<T> {
  return req<T>(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

function del(url: string): Promise<void> {
  return req<void>(url, { method: 'DELETE' })
}

export const campusReportApi = {
  // Schools
  listSchools: (): Promise<School[]> =>
    req(`${BASE}/schools`),

  createSchool: (name: string): Promise<School> =>
    post(`${BASE}/schools`, { name }),

  deleteSchool: (schoolId: string): Promise<void> =>
    del(`${BASE}/schools/${schoolId}`),

  // Sections
  listSections: (schoolId: string): Promise<Section[]> =>
    req(`${BASE}/schools/${schoolId}/sections`),

  createSection: (schoolId: string, title = '新板块'): Promise<Section> =>
    post(`${BASE}/schools/${schoolId}/sections`, { title }),

  updateSection: (
    schoolId: string,
    sectionId: string,
    patch: Partial<Pick<Section, 'title' | 'content' | 'order'>>
  ): Promise<Section> =>
    put(`${BASE}/schools/${schoolId}/sections/${sectionId}`, patch),

  deleteSection: (schoolId: string, sectionId: string): Promise<void> =>
    del(`${BASE}/schools/${schoolId}/sections/${sectionId}`),

  // Images
  uploadImage: (schoolId: string, file: File): Promise<UploadedImage> => {
    const fd = new FormData()
    fd.append('file', file)
    return req(`${BASE}/schools/${schoolId}/images`, { method: 'POST', body: fd })
  },

  deleteImage: (schoolId: string, filename: string): Promise<void> =>
    del(`${BASE}/schools/${schoolId}/images/${filename}`),

  imageUrl: (schoolId: string, filename: string): string =>
    `${BASE}/schools/${schoolId}/images/${filename}`,
}
```

- [ ] **Step 2: Commit**

```bash
git add src/services/campusReportApi.ts
git commit -m "feat: add campusReportApi frontend service"
```

---

## Task 4: Rewrite AnalyticsPage.vue — layout skeleton

**Files:**
- Replace: `src/ui/pages/analytics/AnalyticsPage.vue`

- [ ] **Step 1: Replace the file with the new layout skeleton**

```vue
<!-- src/ui/pages/analytics/AnalyticsPage.vue -->
<script setup lang="ts">
import { ref } from 'vue'
import SchoolSidebar from './components/SchoolSidebar.vue'
import ContentTab from './components/ContentTab.vue'
import ChartsTab from './components/ChartsTab.vue'
import type { School } from '@/services/campusReportApi'

const selectedSchool = ref<School | null>(null)
const activeTab = ref<'content' | 'charts'>('content')

function onSchoolSelect(school: School) {
  selectedSchool.value = school
  activeTab.value = 'content'
}
</script>

<template>
  <div class="flex h-full gap-0 -m-4">
    <!-- Left: school list -->
    <SchoolSidebar
      :selected-school-id="selectedSchool?.id ?? null"
      @select="onSchoolSelect"
    />

    <!-- Right: workspace -->
    <div class="flex-1 flex flex-col min-w-0 p-4">
      <!-- Empty state -->
      <template v-if="!selectedSchool">
        <div class="flex-1 flex flex-col items-center justify-center text-center">
          <div class="text-4xl mb-3">🏫</div>
          <div class="text-[14px] font-semibold text-text-heading mb-1">选择一所学校开始</div>
          <div class="text-[12px] text-text-light">从左侧选择学校，或新建本学期的学校</div>
        </div>
      </template>

      <!-- Workspace -->
      <template v-else>
        <!-- Tab bar -->
        <div class="flex gap-1 mb-4 border-b border-border pb-2">
          <button
            v-for="tab in [{ key: 'content', label: '内容素材' }, { key: 'charts', label: '数据图表' }]"
            :key="tab.key"
            @click="activeTab = tab.key as 'content' | 'charts'"
            class="px-4 py-1.5 text-[12px] font-medium rounded-md transition-colors"
            :class="activeTab === tab.key
              ? 'bg-accent text-white'
              : 'text-text-body hover:text-text-heading hover:bg-accent/10'"
          >
            {{ tab.label }}
          </button>
        </div>

        <!-- Tab content -->
        <ContentTab
          v-if="activeTab === 'content'"
          :school="selectedSchool"
          class="flex-1 min-h-0"
        />
        <ChartsTab
          v-else
          :school="selectedSchool"
          class="flex-1 min-h-0"
        />
      </template>
    </div>
  </div>
</template>
```

- [ ] **Step 2: Create the components directory**

```bash
mkdir -p /Users/wangjun/Desktop/ai_analyst_v2/src/ui/pages/analytics/components
```

- [ ] **Step 3: Create stub components so the page compiles**

`src/ui/pages/analytics/components/ContentTab.vue`:
```vue
<script setup lang="ts">
import type { School } from '@/services/campusReportApi'
defineProps<{ school: School }>()
</script>
<template><div class="text-text-light text-[12px]">内容素材（加载中…）</div></template>
```

`src/ui/pages/analytics/components/ChartsTab.vue`:
```vue
<script setup lang="ts">
import type { School } from '@/services/campusReportApi'
defineProps<{ school: School }>()
</script>
<template><div class="text-text-light text-[12px]">数据图表（待实现）</div></template>
```

`src/ui/pages/analytics/components/SchoolSidebar.vue`:
```vue
<script setup lang="ts">
import type { School } from '@/services/campusReportApi'
defineProps<{ selectedSchoolId: string | null }>()
defineEmits<{ select: [school: School] }>()
</script>
<template><aside class="w-[180px] border-r border-border p-3 text-[12px] text-text-light">学校列表（加载中…）</aside></template>
```

- [ ] **Step 4: Run type-check**

```bash
cd /Users/wangjun/Desktop/ai_analyst_v2
npm run type-check
```
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add src/ui/pages/analytics/AnalyticsPage.vue \
        src/ui/pages/analytics/components/SchoolSidebar.vue \
        src/ui/pages/analytics/components/ContentTab.vue \
        src/ui/pages/analytics/components/ChartsTab.vue
git commit -m "feat: replace AnalyticsPage with campus report layout skeleton"
```

---

## Task 5: SchoolSidebar.vue — school list + create modal

**Files:**
- Replace: `src/ui/pages/analytics/components/SchoolSidebar.vue`

- [ ] **Step 1: Write the full SchoolSidebar component**

```vue
<!-- src/ui/pages/analytics/components/SchoolSidebar.vue -->
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { campusReportApi, type School } from '@/services/campusReportApi'
import { databaseApi, type QueryResult } from '@/services/databaseApi'

const props = defineProps<{ selectedSchoolId: string | null }>()
const emit = defineEmits<{ select: [school: School] }>()

// School list state
const schools = ref<School[]>([])
const loading = ref(false)

// Create modal state
const showModal = ref(false)
const dbSchools = ref<{ id: number; school_name: string }[]>([])
const dbLoading = ref(false)
const selectedDbName = ref('')
const creating = ref(false)
const createError = ref('')

// Hover state for delete button
const hoveredId = ref<string | null>(null)

async function loadSchools() {
  loading.value = true
  try {
    schools.value = await campusReportApi.listSchools()
  } finally {
    loading.value = false
  }
}

async function openModal() {
  showModal.value = true
  selectedDbName.value = ''
  createError.value = ''
  dbLoading.value = true
  try {
    const result: QueryResult = await databaseApi.query(
      'SELECT id, school_name FROM gs_school',
      200
    )
    dbSchools.value = result.rows.map(row => ({
      id: Number(row[0]),
      school_name: String(row[1] ?? ''),
    }))
  } catch (e: any) {
    createError.value = '无法从数据库加载学校列表：' + e.message
  } finally {
    dbLoading.value = false
  }
}

async function confirmCreate() {
  if (!selectedDbName.value) {
    createError.value = '请选择一所学校'
    return
  }
  creating.value = true
  createError.value = ''
  try {
    const school = await campusReportApi.createSchool(selectedDbName.value)
    schools.value.push(school)
    showModal.value = false
    emit('select', school)
  } catch (e: any) {
    createError.value = e.message
  } finally {
    creating.value = false
  }
}

async function removeSchool(e: MouseEvent, school: School) {
  e.stopPropagation()
  if (!confirm(`确认删除「${school.name}」及其所有内容？`)) return
  await campusReportApi.deleteSchool(school.id)
  schools.value = schools.value.filter(s => s.id !== school.id)
}

onMounted(loadSchools)
</script>

<template>
  <aside
    class="w-[180px] flex-shrink-0 flex flex-col border-r border-border bg-sidebar-bg"
    style="min-height: 0"
  >
    <!-- Header -->
    <div class="px-3 pt-4 pb-2">
      <div class="text-[10px] text-text-light tracking-wider uppercase mb-2">本学期学校</div>
      <button
        @click="openModal"
        class="w-full flex items-center justify-center gap-1 py-1.5 rounded-md border border-dashed border-border text-[11px] text-text-light hover:border-accent hover:text-accent transition-colors"
      >
        <span>＋</span> 新建学校
      </button>
    </div>

    <!-- School list -->
    <div class="flex-1 overflow-y-auto px-2 pb-3">
      <div v-if="loading" class="text-[11px] text-text-light text-center py-4">加载中…</div>
      <div v-else-if="schools.length === 0" class="text-[11px] text-text-light text-center py-6 px-2 leading-relaxed">
        暂无学校<br>点击上方按钮新建
      </div>
      <div
        v-for="school in schools"
        :key="school.id"
        @click="emit('select', school)"
        @mouseenter="hoveredId = school.id"
        @mouseleave="hoveredId = null"
        class="flex items-center gap-2 px-2.5 py-2 rounded-lg mb-1 cursor-pointer transition-colors text-[12px] group"
        :class="props.selectedSchoolId === school.id
          ? 'bg-accent text-white font-medium'
          : 'text-text-body hover:bg-accent/10 hover:text-text-heading'"
      >
        <span class="flex-shrink-0 text-[10px]">🏫</span>
        <span class="flex-1 truncate">{{ school.name }}</span>
        <button
          v-if="hoveredId === school.id && props.selectedSchoolId !== school.id"
          @click="removeSchool($event, school)"
          class="flex-shrink-0 text-[11px] text-text-light hover:text-red-500 transition-colors"
          title="删除"
        >✕</button>
      </div>
    </div>
  </aside>

  <!-- Create modal overlay -->
  <Teleport to="body">
    <div
      v-if="showModal"
      class="fixed inset-0 bg-black/30 flex items-center justify-center z-50"
      @click.self="showModal = false"
    >
      <div class="bg-card-bg border border-border rounded-xl shadow-xl p-6 w-[360px]">
        <div class="text-[14px] font-semibold text-text-heading mb-4">新建学校</div>

        <div class="text-[11px] text-text-light mb-1.5">从数据库选择学校</div>
        <div v-if="dbLoading" class="text-[11px] text-text-light py-2">正在加载学校列表…</div>
        <select
          v-else
          v-model="selectedDbName"
          class="w-full border border-border rounded-lg px-3 py-2 text-[12px] text-text-body bg-page-bg focus:outline-none focus:border-accent"
        >
          <option value="" disabled>请选择学校…</option>
          <option
            v-for="s in dbSchools"
            :key="s.id"
            :value="s.school_name"
          >{{ s.school_name }}</option>
        </select>

        <div v-if="createError" class="mt-2 text-[11px] text-red-500">{{ createError }}</div>

        <div class="flex gap-2 justify-end mt-4">
          <button
            @click="showModal = false"
            class="px-4 py-1.5 text-[12px] text-text-body border border-border rounded-lg hover:bg-placeholder/40 transition-colors"
          >取消</button>
          <button
            @click="confirmCreate"
            :disabled="creating || !selectedDbName"
            class="px-4 py-1.5 text-[12px] text-white bg-accent rounded-lg hover:bg-accent-dark transition-colors disabled:opacity-50"
          >{{ creating ? '创建中…' : '确认创建' }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
```

- [ ] **Step 2: Type-check**

```bash
cd /Users/wangjun/Desktop/ai_analyst_v2 && npm run type-check
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add src/ui/pages/analytics/components/SchoolSidebar.vue
git commit -m "feat: implement SchoolSidebar with DB-backed create modal"
```

---

## Task 6: ContentTab.vue — section list + editor container

**Files:**
- Replace: `src/ui/pages/analytics/components/ContentTab.vue`

- [ ] **Step 1: Write ContentTab**

```vue
<!-- src/ui/pages/analytics/components/ContentTab.vue -->
<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { campusReportApi, type School, type Section } from '@/services/campusReportApi'

const props = defineProps<{ school: School }>()

const sections = ref<Section[]>([])
const selectedSection = ref<Section | null>(null)
const loading = ref(false)
const creating = ref(false)
const hoveredSectionId = ref<string | null>(null)

async function loadSections() {
  loading.value = true
  try {
    sections.value = await campusReportApi.listSections(props.school.id)
    if (sections.value.length > 0 && !selectedSection.value) {
      selectedSection.value = sections.value[0]
    }
  } finally {
    loading.value = false
  }
}

async function addSection() {
  creating.value = true
  try {
    const s = await campusReportApi.createSection(props.school.id, '新板块')
    sections.value.push(s)
    selectedSection.value = s
  } finally {
    creating.value = false
  }
}

async function removeSection(e: MouseEvent, section: Section) {
  e.stopPropagation()
  if (!confirm(`确认删除板块「${section.title}」？`)) return
  await campusReportApi.deleteSection(props.school.id, section.id)
  sections.value = sections.value.filter(s => s.id !== section.id)
  if (selectedSection.value?.id === section.id) {
    selectedSection.value = sections.value[0] ?? null
  }
}

function onSectionUpdated(updated: Section) {
  const idx = sections.value.findIndex(s => s.id === updated.id)
  if (idx >= 0) sections.value[idx] = updated
  if (selectedSection.value?.id === updated.id) {
    selectedSection.value = updated
  }
}

watch(() => props.school.id, () => {
  sections.value = []
  selectedSection.value = null
  loadSections()
})

onMounted(loadSections)
</script>

<template>
  <div class="flex h-full gap-0 border border-border rounded-xl overflow-hidden bg-card-bg">
    <!-- Section list panel -->
    <div class="w-[200px] flex-shrink-0 border-r border-border flex flex-col bg-sidebar-bg">
      <div class="px-3 pt-3 pb-2">
        <button
          @click="addSection"
          :disabled="creating"
          class="w-full flex items-center justify-center gap-1 py-1.5 rounded-md border border-dashed border-border text-[11px] text-text-light hover:border-accent hover:text-accent transition-colors disabled:opacity-50"
        >
          <span>＋</span> 新建板块
        </button>
      </div>

      <div class="flex-1 overflow-y-auto px-2 pb-3">
        <div v-if="loading" class="text-[11px] text-text-light text-center py-4">加载中…</div>
        <div v-else-if="sections.length === 0" class="text-[11px] text-text-light text-center py-6 px-2 leading-relaxed">
          暂无板块<br>点击上方按钮新建
        </div>
        <div
          v-for="section in sections"
          :key="section.id"
          @click="selectedSection = section"
          @mouseenter="hoveredSectionId = section.id"
          @mouseleave="hoveredSectionId = null"
          class="flex items-center gap-1.5 px-2.5 py-2 rounded-lg mb-1 cursor-pointer transition-colors text-[12px]"
          :class="selectedSection?.id === section.id
            ? 'bg-accent text-white font-medium'
            : 'text-text-body hover:bg-accent/10 hover:text-text-heading'"
        >
          <span class="flex-1 truncate">{{ section.title }}</span>
          <button
            v-if="hoveredSectionId === section.id && selectedSection?.id !== section.id"
            @click="removeSection($event, section)"
            class="flex-shrink-0 text-[10px] text-text-light hover:text-red-500 transition-colors"
            title="删除"
          >✕</button>
        </div>
      </div>
    </div>

    <!-- Editor area -->
    <div class="flex-1 min-w-0">
      <div v-if="!selectedSection" class="h-full flex items-center justify-center text-[12px] text-text-light">
        选择左侧板块开始编辑
      </div>
      <SectionEditor
        v-else
        :key="selectedSection.id"
        :school-id="props.school.id"
        :section="selectedSection"
        @updated="onSectionUpdated"
      />
    </div>
  </div>
</template>

<script lang="ts">
// Import SectionEditor so Vue can resolve it
import SectionEditor from './SectionEditor.vue'
export default { components: { SectionEditor } }
</script>
```

> **Note:** The `<script lang="ts">` block at the bottom registers `SectionEditor` as a local component for the Options API resolver. In Vue 3 with `<script setup>`, you can also just add the import at the top of the setup block — both work. Add `import SectionEditor from './SectionEditor.vue'` at the top of the `<script setup>` instead and remove the extra `<script>` block if you prefer the cleaner approach.

Actually let's use the clean approach — add the import to the setup block only:

```vue
<!-- src/ui/pages/analytics/components/ContentTab.vue -->
<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { campusReportApi, type School, type Section } from '@/services/campusReportApi'
import SectionEditor from './SectionEditor.vue'

const props = defineProps<{ school: School }>()

const sections = ref<Section[]>([])
const selectedSection = ref<Section | null>(null)
const loading = ref(false)
const creating = ref(false)
const hoveredSectionId = ref<string | null>(null)

async function loadSections() {
  loading.value = true
  try {
    sections.value = await campusReportApi.listSections(props.school.id)
    if (sections.value.length > 0 && !selectedSection.value) {
      selectedSection.value = sections.value[0]
    }
  } finally {
    loading.value = false
  }
}

async function addSection() {
  creating.value = true
  try {
    const s = await campusReportApi.createSection(props.school.id, '新板块')
    sections.value.push(s)
    selectedSection.value = s
  } finally {
    creating.value = false
  }
}

async function removeSection(e: MouseEvent, section: Section) {
  e.stopPropagation()
  if (!confirm(`确认删除板块「${section.title}」？`)) return
  await campusReportApi.deleteSection(props.school.id, section.id)
  sections.value = sections.value.filter(s => s.id !== section.id)
  if (selectedSection.value?.id === section.id) {
    selectedSection.value = sections.value[0] ?? null
  }
}

function onSectionUpdated(updated: Section) {
  const idx = sections.value.findIndex(s => s.id === updated.id)
  if (idx >= 0) sections.value[idx] = updated
  if (selectedSection.value?.id === updated.id) {
    selectedSection.value = updated
  }
}

watch(() => props.school.id, () => {
  sections.value = []
  selectedSection.value = null
  loadSections()
})

onMounted(loadSections)
</script>

<template>
  <div class="flex h-full gap-0 border border-border rounded-xl overflow-hidden bg-card-bg">
    <!-- Section list panel -->
    <div class="w-[200px] flex-shrink-0 border-r border-border flex flex-col bg-sidebar-bg">
      <div class="px-3 pt-3 pb-2">
        <button
          @click="addSection"
          :disabled="creating"
          class="w-full flex items-center justify-center gap-1 py-1.5 rounded-md border border-dashed border-border text-[11px] text-text-light hover:border-accent hover:text-accent transition-colors disabled:opacity-50"
        >
          <span>＋</span> 新建板块
        </button>
      </div>

      <div class="flex-1 overflow-y-auto px-2 pb-3">
        <div v-if="loading" class="text-[11px] text-text-light text-center py-4">加载中…</div>
        <div v-else-if="sections.length === 0" class="text-[11px] text-text-light text-center py-6 px-2 leading-relaxed">
          暂无板块<br>点击上方按钮新建
        </div>
        <div
          v-for="section in sections"
          :key="section.id"
          @click="selectedSection = section"
          @mouseenter="hoveredSectionId = section.id"
          @mouseleave="hoveredSectionId = null"
          class="flex items-center gap-1.5 px-2.5 py-2 rounded-lg mb-1 cursor-pointer transition-colors text-[12px]"
          :class="selectedSection?.id === section.id
            ? 'bg-accent text-white font-medium'
            : 'text-text-body hover:bg-accent/10 hover:text-text-heading'"
        >
          <span class="flex-1 truncate">{{ section.title }}</span>
          <button
            v-if="hoveredSectionId === section.id && selectedSection?.id !== section.id"
            @click="removeSection($event, section)"
            class="flex-shrink-0 text-[10px] text-text-light hover:text-red-500 transition-colors"
            title="删除"
          >✕</button>
        </div>
      </div>
    </div>

    <!-- Editor area -->
    <div class="flex-1 min-w-0">
      <div v-if="!selectedSection" class="h-full flex items-center justify-center text-[12px] text-text-light">
        选择左侧板块开始编辑
      </div>
      <SectionEditor
        v-else
        :key="selectedSection.id"
        :school-id="props.school.id"
        :section="selectedSection"
        @updated="onSectionUpdated"
      />
    </div>
  </div>
</template>
```

- [ ] **Step 2: Create a stub SectionEditor so ContentTab compiles**

```vue
<!-- src/ui/pages/analytics/components/SectionEditor.vue -->
<script setup lang="ts">
import type { Section } from '@/services/campusReportApi'
defineProps<{ schoolId: string; section: Section }>()
defineEmits<{ updated: [section: Section] }>()
</script>
<template><div class="p-4 text-[12px] text-text-light">编辑器（加载中…）</div></template>
```

- [ ] **Step 3: Type-check**

```bash
cd /Users/wangjun/Desktop/ai_analyst_v2 && npm run type-check
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add src/ui/pages/analytics/components/ContentTab.vue \
        src/ui/pages/analytics/components/SectionEditor.vue
git commit -m "feat: implement ContentTab with section list management"
```

---

## Task 7: SectionEditor.vue — title + text + image grid

**Files:**
- Replace: `src/ui/pages/analytics/components/SectionEditor.vue`

- [ ] **Step 1: Write the full SectionEditor**

```vue
<!-- src/ui/pages/analytics/components/SectionEditor.vue -->
<script setup lang="ts">
import { ref, watch } from 'vue'
import { campusReportApi, type Section } from '@/services/campusReportApi'

const props = defineProps<{ schoolId: string; section: Section }>()
const emit = defineEmits<{ updated: [section: Section] }>()

const title = ref(props.section.title)
const content = ref(props.section.content)
const images = ref<string[]>([...props.section.images])

let saveTimer: ReturnType<typeof setTimeout> | null = null
const saving = ref(false)
const saveStatus = ref<'idle' | 'saving' | 'saved'>('idle')

// Preview / lightbox
const previewUrl = ref<string | null>(null)

// Upload state
const uploading = ref(false)
const uploadError = ref('')

function scheduleSave() {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(save, 1000)
}

async function save() {
  saving.value = true
  saveStatus.value = 'saving'
  try {
    const updated = await campusReportApi.updateSection(props.schoolId, props.section.id, {
      title: title.value,
      content: content.value,
    })
    updated.images = images.value   // keep local image list (server doesn't track order in section JSON)
    emit('updated', updated)
    saveStatus.value = 'saved'
    setTimeout(() => { saveStatus.value = 'idle' }, 2000)
  } finally {
    saving.value = false
  }
}

async function handleFileInput(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  if (!files.length) return
  uploadError.value = ''
  uploading.value = true
  try {
    for (const file of files) {
      const result = await campusReportApi.uploadImage(props.schoolId, file)
      images.value.push(result.filename)
    }
    // Persist updated image list
    await campusReportApi.updateSection(props.schoolId, props.section.id, {
      title: title.value,
      content: content.value,
    })
    // Also persist images array via a dedicated update — we store images in the section JSON
    const updated = await campusReportApi.updateSection(props.schoolId, props.section.id, {})
    // Merge images into updated object and emit
    updated.images = images.value
    emit('updated', updated)
  } catch (err: any) {
    uploadError.value = err.message
  } finally {
    uploading.value = false
    input.value = ''
  }
}

async function removeImage(filename: string) {
  if (!confirm('确认删除这张图片？')) return
  await campusReportApi.deleteImage(props.schoolId, filename)
  images.value = images.value.filter(f => f !== filename)
  const updated = await campusReportApi.updateSection(props.schoolId, props.section.id, {})
  updated.images = images.value
  emit('updated', updated)
}

watch(() => props.section, (s) => {
  title.value = s.title
  content.value = s.content
  images.value = [...s.images]
}, { deep: true })
</script>

<template>
  <div class="flex flex-col h-full p-4 overflow-y-auto">
    <!-- Save status -->
    <div class="flex justify-end mb-2 h-4">
      <span v-if="saveStatus === 'saving'" class="text-[10px] text-text-light">保存中…</span>
      <span v-else-if="saveStatus === 'saved'" class="text-[10px] text-accent">✓ 已保存</span>
    </div>

    <!-- Title -->
    <input
      v-model="title"
      @input="scheduleSave"
      placeholder="板块标题"
      class="w-full text-[18px] font-semibold text-text-heading bg-transparent border-none outline-none placeholder-placeholder-dk mb-3"
    />

    <!-- Content -->
    <textarea
      v-model="content"
      @input="scheduleSave"
      placeholder="在此输入内容…"
      rows="8"
      class="w-full flex-1 text-[13px] text-text-body bg-transparent border-none outline-none resize-none placeholder-placeholder-dk leading-relaxed"
    />

    <!-- Divider -->
    <div class="border-t border-border my-4" />

    <!-- Images section -->
    <div>
      <div class="text-[11px] text-text-light mb-2 font-medium">图片</div>

      <!-- Image grid -->
      <div class="flex flex-wrap gap-2">
        <div
          v-for="filename in images"
          :key="filename"
          class="relative group w-[100px] h-[75px] rounded-lg overflow-hidden border border-border bg-placeholder cursor-pointer"
          @click="previewUrl = campusReportApi.imageUrl(schoolId, filename)"
        >
          <img
            :src="campusReportApi.imageUrl(schoolId, filename)"
            class="w-full h-full object-cover"
          />
          <!-- Delete overlay -->
          <div
            class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center"
            @click.stop="removeImage(filename)"
          >
            <span class="text-white text-[11px] bg-red-500/80 rounded px-1.5 py-0.5">删除</span>
          </div>
        </div>

        <!-- Upload button -->
        <label
          class="w-[100px] h-[75px] rounded-lg border border-dashed border-border flex flex-col items-center justify-center cursor-pointer hover:border-accent hover:bg-accent-light/30 transition-colors"
          :class="{ 'opacity-50 pointer-events-none': uploading }"
        >
          <span class="text-[20px] text-text-light">＋</span>
          <span class="text-[10px] text-text-light mt-0.5">{{ uploading ? '上传中…' : '上传图片' }}</span>
          <input
            type="file"
            accept="image/*"
            multiple
            class="hidden"
            @change="handleFileInput"
          />
        </label>
      </div>

      <div v-if="uploadError" class="mt-1.5 text-[11px] text-red-500">{{ uploadError }}</div>
    </div>
  </div>

  <!-- Lightbox -->
  <Teleport to="body">
    <div
      v-if="previewUrl"
      class="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-8"
      @click="previewUrl = null"
    >
      <img
        :src="previewUrl"
        class="max-w-full max-h-full object-contain rounded-lg shadow-2xl"
        @click.stop
      />
      <button
        @click="previewUrl = null"
        class="absolute top-4 right-4 text-white text-2xl hover:text-gray-300"
      >✕</button>
    </div>
  </Teleport>
</template>
```

**Note on image persistence:** The section JSON currently stores `images[]` as filenames. The `updateSection` API only accepts `title`, `content`, and `order`. To persist the image list we need to also store images in the section JSON. Add `images` to the `SectionUpdate` Pydantic model and the `update_section` endpoint in `campus_report_routes.py`:

In `campus_report_routes.py`, update `SectionUpdate`:
```python
class SectionUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    order: Optional[int] = None
    images: Optional[List[str]] = None
```

And in `update_section`:
```python
    if body.images is not None:
        section["images"] = body.images
```

Update `campusReportApi.ts` `updateSection` signature:
```typescript
  updateSection: (
    schoolId: string,
    sectionId: string,
    patch: Partial<Pick<Section, 'title' | 'content' | 'order' | 'images'>>
  ): Promise<Section> =>
    put(`${BASE}/schools/${schoolId}/sections/${sectionId}`, patch),
```

And in `SectionEditor.vue`, replace the `handleFileInput` upload+persist block with:
```typescript
async function handleFileInput(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  if (!files.length) return
  uploadError.value = ''
  uploading.value = true
  try {
    for (const file of files) {
      const result = await campusReportApi.uploadImage(props.schoolId, file)
      images.value.push(result.filename)
    }
    const updated = await campusReportApi.updateSection(props.schoolId, props.section.id, {
      images: images.value,
    })
    updated.images = images.value
    emit('updated', updated)
  } catch (err: any) {
    uploadError.value = err.message
  } finally {
    uploading.value = false
    input.value = ''
  }
}
```

And `removeImage`:
```typescript
async function removeImage(filename: string) {
  if (!confirm('确认删除这张图片？')) return
  await campusReportApi.deleteImage(props.schoolId, filename)
  images.value = images.value.filter(f => f !== filename)
  const updated = await campusReportApi.updateSection(props.schoolId, props.section.id, {
    images: images.value,
  })
  updated.images = images.value
  emit('updated', updated)
}
```

- [ ] **Step 2: Apply the SectionUpdate images patch to the backend**

In `backend/api/campus_report_routes.py`, update `SectionUpdate` class and `update_section` handler as shown above.

- [ ] **Step 3: Apply the campusReportApi.ts signature update**

In `src/services/campusReportApi.ts`, update the `updateSection` type signature as shown above.

- [ ] **Step 4: Type-check**

```bash
cd /Users/wangjun/Desktop/ai_analyst_v2 && npm run type-check
```
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add src/ui/pages/analytics/components/SectionEditor.vue \
        src/services/campusReportApi.ts \
        backend/api/campus_report_routes.py
git commit -m "feat: implement SectionEditor with autosave and image upload"
```

---

## Task 8: ChartsTab.vue — placeholder

**Files:**
- Replace: `src/ui/pages/analytics/components/ChartsTab.vue`

- [ ] **Step 1: Write the placeholder charts tab**

```vue
<!-- src/ui/pages/analytics/components/ChartsTab.vue -->
<script setup lang="ts">
import type { School } from '@/services/campusReportApi'
defineProps<{ school: School }>()
</script>

<template>
  <div class="h-full flex flex-col">
    <div class="grid grid-cols-2 gap-3.5 flex-1 min-h-0">
      <div
        v-for="chart in [
          { title: '性别分布', icon: '◑', note: '饼图' },
          { title: '月度上课人次', icon: '▦', note: '柱状图' },
          { title: '月度到课率', icon: '╱', note: '折线图' },
          { title: '教练上课情况', icon: '▤', note: '横向柱状图' },
        ]"
        :key="chart.title"
        class="bg-card-bg border border-border rounded-xl p-4 flex flex-col"
      >
        <div class="flex items-center justify-between mb-3">
          <div class="text-[13px] font-medium text-text-heading">{{ chart.title }}</div>
          <span class="text-[10px] text-text-light border border-border rounded px-1.5 py-0.5">{{ chart.note }}</span>
        </div>
        <div class="flex-1 flex flex-col items-center justify-center gap-2 text-center border border-dashed border-border rounded-lg bg-page-bg">
          <span class="text-3xl text-placeholder-dk">{{ chart.icon }}</span>
          <div class="text-[11px] text-text-light">SQL 待配置</div>
          <div class="text-[10px] text-text-light/70">确定查询语句后此图表将自动渲染</div>
        </div>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: Type-check**

```bash
cd /Users/wangjun/Desktop/ai_analyst_v2 && npm run type-check
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add src/ui/pages/analytics/components/ChartsTab.vue
git commit -m "feat: add ChartsTab placeholder with 4 chart slots"
```

---

## Task 9: Rename sidebar label

**Files:**
- Modify: `src/ui/components/layout/Sidebar.vue`

- [ ] **Step 1: Update the nav item label**

In `src/ui/components/layout/Sidebar.vue`, find:
```typescript
  { icon: '◉', label: '高级数据分析', key: 'analytics', path: '/analytics' },
```
Replace with:
```typescript
  { icon: '◉', label: '校园报告', key: 'analytics', path: '/analytics' },
```

- [ ] **Step 2: Update the route meta title in router**

In `src/router/index.ts`, find:
```typescript
    meta: { title: '高级数据分析' }
```
(the one under `/analytics`) and replace with:
```typescript
    meta: { title: '校园报告' }
```

- [ ] **Step 3: Type-check + commit**

```bash
cd /Users/wangjun/Desktop/ai_analyst_v2 && npm run type-check
git add src/ui/components/layout/Sidebar.vue src/router/index.ts
git commit -m "chore: rename 高级数据分析 → 校园报告 in sidebar and router"
```

---

## Task 10: End-to-end smoke test

- [ ] **Step 1: Start backend**

```bash
cd /Users/wangjun/Desktop/ai_analyst_v2/backend
source .venv/bin/activate
uvicorn main:app --reload --port 8003
```

- [ ] **Step 2: Start frontend**

```bash
cd /Users/wangjun/Desktop/ai_analyst_v2
npm run dev
```

- [ ] **Step 3: Manual test checklist**

Open `http://localhost:3000/analytics` and verify:

- [ ] Sidebar shows「校园报告」label
- [ ] Left panel shows empty state + "新建学校" button
- [ ] Click "新建学校" → modal opens, dropdown loads schools from `gs_school`
- [ ] Select a school → school appears in left list, workspace opens with Tab bar
- [ ] Click "内容素材" tab → shows section list (empty) + editor placeholder
- [ ] Click "新建板块" → section appears in list, editor loads
- [ ] Type in title and content → status shows "保存中…" then "✓ 已保存"
- [ ] Upload an image → thumbnail appears in grid
- [ ] Click thumbnail → lightbox opens
- [ ] Hover thumbnail → delete overlay appears, click deletes it
- [ ] Click "数据图表" tab → 4 placeholder chart cards visible
- [ ] Switch to a different school in left panel → workspace resets correctly
- [ ] Hover a school in left list → ✕ button appears, click deletes it
- [ ] `data/campus_reports/` directory was created with correct structure

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "feat: campus report manager — all tasks complete, smoke tested"
```
