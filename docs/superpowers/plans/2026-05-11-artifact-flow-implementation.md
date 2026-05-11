# 工具间数据流通 (Artifact Flow) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a platform-wide artifact system so upstream tools (e.g. 月度分析) can produce data consumable by downstream tools (e.g. 课时费计算器) without manual Excel import/export.

**Architecture:** New backend CRUD API (`/api/artifacts`) stores artifact JSON files under `data/artifacts/`. Frontend gets a new Vue page for the monthly-analysis tool, a shared tool registry to replace duplicated arrays, and the fee-calculator iframe gets a `postMessage` listener for artifact data injection.

**Tech Stack:** FastAPI (Python), Vue 3 + TypeScript + Vue Router, Tailwind CSS, postMessage API

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/artifacts.py` | **Create** | Artifact CRUD logic (list/get/save/delete), reuses storage.py patterns |
| `backend/api/routes.py` | **Modify** | Add 4 artifact routes (POST, GET list, GET single, DELETE) |
| `src/types/toolbox.ts` | **Modify** | Extend `Tool` type: add `type` field ('iframe'\|'vue'), `route` field |
| `src/data/tools.ts` | **Create** | Shared tools registry (extract from duplicated ToolboxPage/ToolDetailPage) |
| `src/ui/pages/toolbox/ToolboxPage.vue` | **Modify** | Import shared registry, add monthly-analysis entry |
| `src/ui/pages/toolbox/ToolDetailPage.vue` | **Modify** | Support vue-type tools + postMessage sender for iframe tools |
| `src/ui/pages/tools/MonthlyAnalysis.vue` | **Create** | Skeleton page for 校内月度分析 tool |
| `src/router/index.ts` | **Modify** | Add `/tools/monthly-analysis` route |
| `public/tools/课时费计算器.html` | **Modify** | Add "从平台导入" button + `postMessage` listener |
| `src/services/artifactApi.ts` | **Create** | Frontend API service for artifact CRUD |

---

### Task 1: Backend Artifact Storage Module

**Files:**
- Create: `backend/artifacts.py`
- Reference: `backend/sops/storage.py` (reuse `_read_json` / `_write_json` pattern)

- [ ] **Step 1: Create `backend/artifacts.py`**

```python
# backend/artifacts.py
"""Artifact CRUD — reuses the same JSON-file + fcntl-lock pattern as sops/storage.py."""

import os
import json
import fcntl
from typing import List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
ARTIFACTS_DIR = os.path.join(DATA_DIR, "artifacts")


def _ensure_dir():
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)


def _artifact_path(artifact_id: str) -> str:
    return os.path.join(ARTIFACTS_DIR, f"{artifact_id}.json")


def _read_json(path: str):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        return json.load(f)


def _write_json(path: str, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def list_artifacts(type: Optional[str] = None) -> List[dict]:
    """List all artifacts, optionally filtered by type."""
    _ensure_dir()
    results = []
    for fname in os.listdir(ARTIFACTS_DIR):
        if not fname.endswith(".json"):
            continue
        data = _read_json(os.path.join(ARTIFACTS_DIR, fname))
        if data is None:
            continue
        if type and data.get("type") != type:
            continue
        results.append(data)
    results.sort(key=lambda a: a.get("created_at", ""), reverse=True)
    return results


def get_artifact(artifact_id: str) -> Optional[dict]:
    """Get a single artifact by id."""
    path = _artifact_path(artifact_id)
    return _read_json(path)


def save_artifact(artifact: dict) -> dict:
    """Save (create or overwrite) an artifact."""
    _ensure_dir()
    path = _artifact_path(artifact["id"])
    _write_json(path, artifact)
    return artifact


def delete_artifact(artifact_id: str) -> bool:
    """Delete an artifact. Returns True if deleted, False if not found."""
    path = _artifact_path(artifact_id)
    if not os.path.exists(path):
        return False
    os.remove(path)
    return True
```

- [ ] **Step 2: Verify the module loads**

```bash
cd backend && python -c "import artifacts; print('OK')"
```

Expected: `OK`

---

### Task 2: Backend Artifact API Routes

**Files:**
- Modify: `backend/api/routes.py`

- [ ] **Step 1: Add artifact imports and routes to `backend/api/routes.py`**

Add at the top imports section (after existing imports):
```python
import artifacts as artifact_store
```

Add the following route code at the **end** of `routes.py` (before the file routes, after the execution routes section):

```python
# ==================== Artifact 路由 ====================

class ArtifactCreateRequest(BaseModel):
    name: str
    type: str
    source_tool: str
    data: dict
    schema_version: str = "1"


@router.post("/artifacts", response_model=dict)
async def create_artifact(body: ArtifactCreateRequest):
    """创建 artifact"""
    artifact_id = f"art_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    now = datetime.now().isoformat()
    artifact = {
        "id": artifact_id,
        "name": body.name,
        "type": body.type,
        "source_tool": body.source_tool,
        "created_at": now,
        "schema_version": body.schema_version,
        "data": body.data,
    }
    artifact_store.save_artifact(artifact)
    return artifact


@router.get("/artifacts", response_model=List[dict])
async def list_artifacts(type: Optional[str] = None):
    """获取 artifact 列表，可按 type 筛选"""
    return artifact_store.list_artifacts(type=type)


@router.get("/artifacts/{artifact_id}", response_model=dict)
async def get_artifact(artifact_id: str):
    """获取单个 artifact 完整数据"""
    artifact = artifact_store.get_artifact(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact


@router.delete("/artifacts/{artifact_id}")
async def delete_artifact(artifact_id: str):
    """删除 artifact"""
    success = artifact_store.delete_artifact(artifact_id)
    if not success:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return {"message": "Artifact deleted successfully"}
```

- [ ] **Step 2: Verify backend starts without errors**

```bash
cd backend && python -c "from api.routes import router; print('Routes loaded OK')"
```

Expected: `Routes loaded OK`

---

### Task 3: Frontend Tool Type Extension

**Files:**
- Modify: `src/types/toolbox.ts`

- [ ] **Step 1: Extend the `Tool` interface**

Replace the contents of `src/types/toolbox.ts`:

```typescript
/** 工具类型 */
export type ToolKind = 'iframe' | 'vue'

/** 单个工具的注册信息 */
export interface Tool {
  /** 唯一标识 */
  id: string
  /** 工具名称，显示在卡片上 */
  name: string
  /** 一句话描述 */
  description: string
  /** 卡片图标（emoji 或字符） */
  icon: string
  /** 主题色（hex） */
  color: string
  /** 分类标签 */
  tags: string[]
  /** 工具类型：iframe 加载 HTML 或 vue 原生页面 */
  type: ToolKind
  /** iframe 加载的 URL 路径（相对于 public/），type=iframe 时必填 */
  src?: string
  /** Vue 路由路径，type=vue 时必填 */
  route?: string
  /** 展开后面板的默认高度（px），默认 800，仅 iframe 工具有效 */
  iframeHeight?: number
  /** 是否启用，默认 true */
  enabled?: boolean
}
```

- [ ] **Step 2: Verify type check passes**

```bash
npm run type-check
```

Expected: No errors related to toolbox.ts (existing errors in other files are OK)

---

### Task 4: Shared Tools Registry

**Files:**
- Create: `src/data/tools.ts`

- [ ] **Step 1: Create the shared tools registry**

```typescript
// src/data/tools.ts
import type { Tool } from '@/types/toolbox'

export const tools: Tool[] = [
  {
    id: 'fee-calculator',
    name: '课时费计算器',
    description: '上传 Excel 数据，按教练×课程规则计算课时费，支持多种计费方式和补贴配置',
    icon: '◈',
    color: '#5B8F7A',
    tags: ['财务', 'Excel'],
    type: 'iframe',
    src: '/tools/课时费计算器.html',
    iframeHeight: 800,
  },
  {
    id: 'monthly-analysis',
    name: '校内月度分析',
    description: '月度校内数据分析，产出课时费计算所需的月度分析表',
    icon: '◈',
    color: '#6366f1',
    tags: ['分析', '月度'],
    type: 'vue',
    route: '/tools/monthly-analysis',
  },
]
```

---

### Task 5: Update ToolboxPage to Use Shared Registry

**Files:**
- Modify: `src/ui/pages/toolbox/ToolboxPage.vue`

- [ ] **Step 1: Replace hardcoded tools with shared import**

Replace the entire `<script setup>` block:

```vue
<script setup lang="ts">
import { useRouter } from 'vue-router'
import Card from '@/ui/components/common/Card.vue'
import Chip from '@/ui/components/common/Chip.vue'
import { tools } from '@/data/tools'

const router = useRouter()

const enabledTools = tools.filter(t => t.enabled !== false)
const getIconBg = (color: string) => color + '15'
</script>
```

The `<template>` section stays unchanged — it already uses `enabledTools`.

- [ ] **Step 2: Verify type check**

```bash
npm run type-check
```

Expected: No new errors

---

### Task 6: Create MonthlyAnalysis Skeleton Page

**Files:**
- Create: `src/ui/pages/tools/MonthlyAnalysis.vue`

- [ ] **Step 1: Create the skeleton page**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import Button from '@/ui/components/common/Button.vue'
import Card from '@/ui/components/common/Card.vue'

const saving = ref(false)
const message = ref('')

async function handleSaveToPlatform() {
  saving.value = true
  message.value = '保存功能待实现（后续接入分析逻辑）'
  saving.value = false
}
</script>

<template>
  <div class="p-6">
    <Card>
      <div class="flex flex-col gap-4">
        <div>
          <h2 class="text-lg font-bold text-text-heading">校内月度分析</h2>
          <p class="text-sm text-text-light mt-1">上传原始数据，执行分析，保存结果到平台</p>
        </div>

        <div class="border border-dashed border-border rounded-xl p-8 text-center">
          <p class="text-text-light text-sm">分析功能开发中...</p>
          <p class="text-text-light text-xs mt-1">后续支持上传数据文件并执行分析计算</p>
        </div>

        <div class="flex items-center gap-3">
          <Button
            variant="primary"
            :loading="saving"
            @click="handleSaveToPlatform"
          >
            保存到平台
          </Button>
          <span v-if="message" class="text-xs text-text-light">{{ message }}</span>
        </div>
      </div>
    </Card>
  </div>
</template>
```

---

### Task 7: Update ToolDetailPage to Support Vue Tools + Artifact Injection

**Files:**
- Modify: `src/ui/pages/toolbox/ToolDetailPage.vue`

- [ ] **Step 1: Rewrite ToolDetailPage with vue-type support and postMessage**

Replace the entire file:

```vue
<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { tools } from '@/data/tools'

const route = useRoute()
const router = useRouter()
const iframeRef = ref<HTMLIFrameElement | null>(null)

const tool = computed(() => tools.find(t => t.id === route.params.toolId))
const getIconBg = (color: string) => color + '15'
const openInNewWindow = (src: string) => window.open(src, '_blank')

// --- Artifact injection for iframe tools ---
async function handleImportArtifact() {
  try {
    const resp = await fetch('/api/artifacts?type=monthly-analysis')
    const artifacts = await resp.json()
    if (!artifacts.length) {
      alert('暂无可用的平台数据，请先在「校内月度分析」中生成数据。')
      return
    }
    // Simple selection: pick the most recent one
    // TODO: show a proper selection dialog if multiple artifacts exist
    const chosen = artifacts[0]
    if (iframeRef.value?.contentWindow) {
      iframeRef.value.contentWindow.postMessage({
        type: 'ARTIFACT_INJECT',
        artifact: {
          name: chosen.name,
          type: chosen.type,
          data: chosen.data,
        },
      }, '*')
    }
  } catch (e) {
    console.error('Failed to import artifact:', e)
    alert('导入失败，请检查后端服务是否正常。')
  }
}
</script>

<template>
  <div v-if="tool">
    <div class="flex items-center gap-3 mb-4">
      <button
        class="flex items-center gap-1.5 text-[12px] text-text-light hover:text-text-heading transition-colors px-2 py-1 rounded-md hover:bg-chip"
        @click="router.push('/toolbox')"
      >
        ← 返回工具箱
      </button>
      <div class="w-px h-4 bg-border" />
      <div
        class="w-7 h-7 rounded-lg flex items-center justify-center text-sm"
        :style="{ backgroundColor: getIconBg(tool.color), color: tool.color }"
      >
        {{ tool.icon }}
      </div>
      <span class="text-[14px] font-bold text-text-heading">{{ tool.name }}</span>

      <!-- Artifact import button for iframe tools -->
      <button
        v-if="tool.type === 'iframe'"
        class="text-[11px] text-accent hover:text-accent-dark transition-colors px-2 py-1 rounded-md hover:bg-accent-light border border-accent/30"
        @click="handleImportArtifact"
      >
        ↓ 从平台导入
      </button>

      <button
        v-if="tool.type === 'iframe' && tool.src"
        class="ml-auto text-[11px] text-text-light hover:text-accent transition-colors px-2 py-1 rounded-md hover:bg-accent-light"
        @click="openInNewWindow(tool.src)"
      >
        ↗ 新窗口打开
      </button>
    </div>

    <!-- iframe tool -->
    <div
      v-if="tool.type === 'iframe'"
      class="bg-gradient-to-b from-card-bg to-card-gradient border border-border/70 rounded-xl shadow-card overflow-hidden"
    >
      <iframe
        ref="iframeRef"
        :src="tool.src"
        class="w-full border-0"
        :style="{ height: (tool.iframeHeight || 800) + 'px' }"
        :title="tool.name"
      />
    </div>

    <!-- vue tool -->
    <div v-else-if="tool.type === 'vue'">
      <router-view />
    </div>
  </div>

  <div v-else class="flex flex-col items-center justify-center py-20">
    <p class="text-[14px] text-text-body font-medium">工具不存在</p>
    <button
      class="mt-3 text-[12px] text-accent hover:underline"
      @click="router.push('/toolbox')"
    >
      返回工具箱
    </button>
  </div>
</template>
```

---

### Task 8: Update Router Configuration

**Files:**
- Modify: `src/router/index.ts`

- [ ] **Step 1: Add the monthly-analysis route**

Add the new route **before** the existing `/toolbox/:toolId` route (so `/tools/monthly-analysis` doesn't get caught by the `:toolId` wildcard):

```typescript
import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/home'
  },
  {
    path: '/home',
    name: 'home',
    component: () => import('@/ui/pages/home/HomePage.vue'),
    meta: { title: '工作台首页' }
  },
  {
    path: '/toolbox',
    name: 'toolbox',
    component: () => import('@/ui/pages/toolbox/ToolboxPage.vue'),
    meta: { title: '工具箱' }
  },
  {
    path: '/toolbox/:toolId',
    name: 'toolbox-detail',
    component: () => import('@/ui/pages/toolbox/ToolDetailPage.vue'),
    meta: { title: '工具' },
    children: [
      {
        path: 'monthly-analysis',
        name: 'monthly-analysis-tool',
        component: () => import('@/ui/pages/tools/MonthlyAnalysis.vue'),
        meta: { title: '校内月度分析' }
      }
    ]
  },
  {
    path: '/policy',
    name: 'policy',
    component: () => import('@/ui/pages/policy/PolicyPage.vue'),
    meta: { title: '政策报告撰写' }
  },
  {
    path: '/analytics',
    name: 'analytics',
    component: () => import('@/ui/pages/analytics/AnalyticsPage.vue'),
    meta: { title: '高级数据分析' }
  },
  {
    path: '/database',
    name: 'database',
    component: () => import('@/ui/pages/database/DatabasePage.vue'),
    meta: { title: '数据库连接' }
  },
  {
    path: '/knowledge',
    name: 'knowledge',
    component: () => import('@/ui/pages/knowledge/KnowledgePage.vue'),
    meta: { title: '个人知识库' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, _from, next) => {
  document.title = `${to.meta.title || '工作台'} - 智能工作台`
  next()
})

export default router
```

---

### Task 9: Add postMessage Listener to Fee Calculator

**Files:**
- Modify: `public/tools/课时费计算器.html`

- [ ] **Step 1: Add artifact import button to the data import page**

Insert right **before** the `<div class="up-grid">` block (at line 271, inside `#page_import`):

```html
  <!-- Platform import bar -->
  <div style="margin-bottom:16px;background:#fff;border-radius:var(--rs);padding:14px 20px;box-shadow:var(--sh-xs);display:flex;align-items:center;gap:12px">
    <span style="font-size:13px;color:var(--g600)">或从平台直接导入已有数据</span>
    <button class="btn btn-o" onclick="importFromPlatform()" id="btnPlatformImport">↓ 从平台导入</button>
    <span id="platformImportStatus" style="font-size:11px;color:var(--g400)"></span>
  </div>
```

- [ ] **Step 2: Add postMessage listener and import handler**

Insert right **before** the closing `</script>` tag at the end of the file (before the very last line):

```javascript
// ===== Platform Artifact Import =====
function injectArtifactData(artifact) {
  if (!artifact || !artifact.data) return;
  const { courses, attendance } = artifact.data;

  // Inject courses
  if (courses && courses.length) {
    DATA.courses = courses.map(c => ({
      dept: c.dept || '',
      school: c.school || '',
      course: c.course || '',
      courseRaw: c.courseRaw || c.course || '',
      coach: c.coach || '',
      people: Number(c.people) || 0,
      lessons: Number(c.lessons) || 0,
      revenue: Number(c.revenue) || 0,
      type: '',
      attInfo: null,
    }));
  }

  // Inject attendance
  if (attendance && typeof attendance === 'object') {
    DATA.attendance = {};
    for (const [key, val] of Object.entries(attendance)) {
      DATA.attendance[key] = {
        total: val.total || 0,
        '在岗': val['在岗'] || 0,
        '迟到': val['迟到'] || 0,
        '早退': val['早退'] || 0,
        '旷工': val['旷工'] || 0,
        dateList: val.dateList || [],
        days: (val.dateList || []).length,
        durationMap: val.durationMap || {},
      };
    }
  }

  mergeData();
  markUploaded(1, artifact.name || '平台数据');
  toast('已导入平台数据: ' + (artifact.name || ''));
}

window.addEventListener('message', function(e) {
  if (e.data && e.data.type === 'ARTIFACT_INJECT') {
    injectArtifactData(e.data.artifact);
  }
});

function importFromPlatform() {
  // When embedded in iframe, ask parent to provide artifact data
  if (window.parent !== window) {
    window.parent.postMessage({ type: 'REQUEST_ARTIFACT' }, '*');
    document.getElementById('platformImportStatus').textContent = '正在请求数据...';
  } else {
    document.getElementById('platformImportStatus').textContent = '请在平台工具箱中使用此功能';
  }
}
```

- [ ] **Step 3: Verify the HTML loads without JS errors**

Open `http://localhost:3000/tools/课时费计算器.html` in browser, check console.

---

### Task 10: Verification and Integration Test

- [ ] **Step 1: Start backend and verify artifact routes**

```bash
cd backend && uvicorn main:app --reload --port 8003
```

Test with curl:
```bash
# Create an artifact
curl -X POST http://localhost:8003/api/artifacts \
  -H "Content-Type: application/json" \
  -d '{"name":"测试数据","type":"monthly-analysis","source_tool":"test","data":{"courses":[],"attendance":{}}}'

# List artifacts
curl http://localhost:8003/api/artifacts

# List with type filter
curl "http://localhost:8003/api/artifacts?type=monthly-analysis"

# Get single artifact (replace ID with actual returned ID)
curl http://localhost:8003/api/artifacts/art_XXXXX

# Delete artifact
curl -X DELETE http://localhost:8003/api/artifacts/art_XXXXX
```

- [ ] **Step 2: Start frontend and verify toolbox shows both tools**

```bash
npm run dev
```

Open `http://localhost:3000/toolbox` — verify two tool cards appear.

- [ ] **Step 3: Click monthly-analysis tool, verify skeleton page renders**

Click the "校内月度分析" card, verify the Vue page loads (not an iframe 404).

- [ ] **Step 4: Click fee-calculator, verify "从平台导入" button appears**

Click the "课时费计算器" card, verify the import button shows in the header.

- [ ] **Step 5: Verify type check passes**

```bash
npm run type-check
```

Expected: No errors.

---

### Task 11: Commit

- [ ] **Step 1: Stage and commit all changes**

```bash
git add backend/artifacts.py backend/api/routes.py src/types/toolbox.ts src/data/tools.ts src/ui/pages/toolbox/ToolboxPage.vue src/ui/pages/toolbox/ToolDetailPage.vue src/ui/pages/tools/MonthlyAnalysis.vue src/router/index.ts public/tools/课时费计算器.html
git commit -m "feat: add artifact flow system for tool-to-tool data passing

- Backend: artifact CRUD API (POST/GET/DELETE /api/artifacts)
- Frontend: shared tools registry, vue-type tool support
- New monthly-analysis tool skeleton page
- Fee calculator: postMessage listener for platform data import
- Artifact data stored as JSON files under data/artifacts/"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Artifact data model (id, name, type, source_tool, created_at, schema_version, data) — Task 1
- [x] Backend CRUD API (POST, GET list, GET single, DELETE) — Tasks 1-2
- [x] Upstream tool: MonthlyAnalysis.vue skeleton — Task 6
- [x] Tool registration with vue type — Tasks 4-5
- [x] Downstream tool: fee calculator "从平台导入" button — Tasks 7, 9
- [x] postMessage communication protocol — Tasks 7, 9
- [x] ToolDetailPage supports both iframe and vue tools — Task 7
- [x] Router config — Task 8
- [x] Shared tools registry eliminates duplication — Tasks 4-5

**Not in scope (per spec):**
- Monthly analysis business logic (future)
- Knowledge base / RAG integration
- Auth
- Database migration
