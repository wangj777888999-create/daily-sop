# RAG 知识库开发计划

> **架构更新（2026-05-12）**：检索层从"向量嵌入 + ChromaDB"改为 **BM25 + jieba**，去掉 torch/transformers/text2vec/ChromaDB 等重依赖。API Key 通过 `ANTHROPIC_API_KEY` 环境变量读取（由 ccswitch 管理），不通过前端传参。

## Context

智能工作台需要知识库功能，存储公司内部资料（政策文档、报告模板等），通过 RAG（检索增强生成）让生成的内容能学习参考文档的表达方式和知识。

**核心技术栈：** BM25（关键词检索） + jieba（中文分词） + Claude API（生成）

**核心场景：**
- 政策撰写：参考以往政策格式和表达
- 校园成果报告：基于模板学习，更改基础信息后生成新报告

**RAG 流程：**
```
Upload → Parse → Chunk → JSON Store
                              ↓ 启动时重建 BM25 索引
Query → jieba 分词 → BM25 Scoring → Top-K Chunks
                                          ↓
Chunks + Prompt → Claude API → Generated Content
```

## New Dependencies

```
# backend/requirements.txt 新增
rank-bm25>=0.2.2
jieba>=0.42.1
anthropic>=0.30.0
python-docx>=1.1.0
pdfplumber>=0.10.0

# 不再需要（删除）：
# chromadb, text2vec, torch, transformers, sentence-transformers
```

## Backend Architecture

### 新增目录结构

```
backend/
  knowledge/
    __init__.py              # 包导出
    models.py                # Pydantic 模型
    storage.py               # 文档元数据 + chunk JSON 持久化（fcntl + 原子写入）
    parser.py                # 文档解析（PDF/DOCX/XLSX/TXT/MD）
    chunker.py               # 文本分块（中文文档优化）
    indexer.py               # BM25 索引（jieba 分词，启动时从 JSON 重建，内存常驻）
    rag.py                   # RAG 检索 + 生成管线
    generator.py             # Claude API 调用（读 ANTHROPIC_API_KEY env var）
  api/
    knowledge_routes.py      # 知识库 API 端点
data/
  knowledge_metadata.json    # 文档元数据（快速列表）
  knowledge_chunks.json      # 所有 chunk 文本（BM25 索引数据源）
  knowledge_files/           # 上传的原始文件
    {doc_id}/original.ext
```

### 核心模块设计

#### `backend/knowledge/models.py` — Pydantic 模型

```python
class DocType(str, Enum):
    PDF = "PDF"
    DOCX = "DOCX"
    XLSX = "XLSX"
    TXT = "TXT"
    MD = "MD"

class Folder(BaseModel):
    id: str
    name: str
    parent_id: Optional[str] = None
    created_at: datetime

class ChunkMetadata(BaseModel):
    """存入 knowledge_chunks.json 的每个 chunk 元数据"""
    id: str               # f"{doc_id}_chunk_{chunk_index}"
    doc_id: str
    doc_name: str
    chunk_index: int
    chunk_type: str       # "heading" | "paragraph" | "table" | "list"
    heading_path: str     # 所在章节路径，如 "第一章 > 1.1 背景"
    text: str             # chunk 文本（BM25 索引的检索对象）
    page: int = 0

class KnowledgeDocument(BaseModel):
    id: str
    name: str
    type: DocType
    size_bytes: int
    folder_id: Optional[str] = None
    tags: List[str] = []
    content_hash: str
    chunk_count: int = 0
    parsed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

class ParsedDocument(BaseModel):
    """解析后的完整文档结构"""
    doc_id: str
    full_text: str
    chunks: List[dict]    # [{chunk_type, level, text, page, heading_path}, ...]

class SearchResult(BaseModel):
    doc_id: str
    doc_name: str
    doc_type: DocType
    chunk_text: str
    chunk_type: str
    heading_path: str
    score: float          # BM25 分数（归一化到 0-1），越高越相关
    page: int = 0

class RAGRequest(BaseModel):
    prompt: str
    doc_ids: Optional[List[str]] = None   # 限定搜索范围
    style: str = "policy"                 # "policy" | "report" | "general"
    top_k: int = 5

class RAGResponse(BaseModel):
    generated_text: str
    sources: List[dict]   # [{doc_name, chunk_text, heading_path, score}, ...]
```

#### `backend/knowledge/storage.py` — 元数据 JSON 持久化

完全复用 `backend/sops/storage.py` 的 `_read_json` / `_write_json`（fcntl + 原子写入）：

```python
DATA_DIR = ...
META_FILE = os.path.join(DATA_DIR, "knowledge_metadata.json")

def get_all_docs() -> List[KnowledgeDocument]
def get_doc(doc_id: str) -> Optional[KnowledgeDocument]
def save_doc(doc: KnowledgeDocument) -> KnowledgeDocument
def delete_doc(doc_id: str) -> bool
def get_all_folders() -> List[Folder]
def save_folder(folder: Folder) -> Folder
def delete_folder(folder_id: str) -> bool
def get_all_tags() -> List[str]
```

**注意：** `knowledge_metadata.json` 存文档元数据（列表/筛选用）；`knowledge_chunks.json` 存所有 chunk 文本（BM25 索引数据源）。两个文件各自用 fcntl + 原子写入保证一致性。

#### `backend/knowledge/parser.py` — 文档解析

```python
def parse_document(file_path: str, doc_type: str) -> ParsedDocument:
    """主入口，按类型分发"""
```

- **PDF**: pdfplumber 提取文本 + 坐标，按页处理。通过字号（>14pt）和位置检测标题
- **DOCX**: python-docx 提取段落 + style.name（Heading 1/2/3）+ 表格数据
- **XLSX**: openpyxl 提取 sheet 名、列头、前 500 行采样
- **TXT/MD**: UTF-8 读取 + 正则标题检测 / `#` 语法解析

所有解析器输出统一的 `ParsedDocument`（full_text + chunks 列表）。

#### `backend/knowledge/chunker.py` — 中文文本分块

```python
def chunk_document(parsed: ParsedDocument, max_chunk_size: int = 500, overlap: int = 50) -> List[dict]:
    """
    分块策略（中文文档优化）：
    1. 保留解析阶段已识别的 heading/paragraph 边界
    2. 段落级分块：每个自然段落一个 chunk
    3. 过短段落（<50字）合并到上一 chunk
    4. 过长段落（>500字）按句号分句再合并
    5. 每个 chunk 携带 heading_path（章节路径）
    6. 相邻 chunk 有 50 字重叠
    """
```

#### `backend/knowledge/indexer.py` — BM25 索引

```python
import jieba
from rank_bm25 import BM25Okapi

class BM25Index:
    """BM25 内存索引，启动时从 knowledge_chunks.json 重建，增删文档后即时更新"""

    def __init__(self):
        self._chunks: List[dict] = []   # chunk 元数据列表（含 text 字段）
        self._index: BM25Okapi | None = None

    def build(self, chunks: List[dict]):
        """从 chunk 列表重建索引（每条含 id/doc_id/text/heading_path 等字段）"""
        self._chunks = chunks
        tokenized = [list(jieba.cut(c["text"])) for c in chunks]
        self._index = BM25Okapi(tokenized)

    def search(self, query: str, top_k: int = 5,
               doc_ids: List[str] = None) -> List[dict]:
        """BM25 检索，返回带 score 的 chunk 列表（score 归一化到 0-1）"""
        if not self._index or not self._chunks:
            return []
        tokens = list(jieba.cut(query))
        raw_scores = self._index.get_scores(tokens)
        max_score = max(raw_scores) if max(raw_scores) > 0 else 1
        results = []
        for chunk, raw in zip(self._chunks, raw_scores):
            if raw == 0:
                continue
            if doc_ids and chunk["doc_id"] not in doc_ids:
                continue
            results.append({**chunk, "score": round(raw / max_score, 4)})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def add_chunks(self, new_chunks: List[dict]):
        """追加 chunks 并重建索引"""
        self._chunks.extend(new_chunks)
        self.build(self._chunks)

    def remove_doc(self, doc_id: str):
        """删除某文档的所有 chunks 并重建索引"""
        self._chunks = [c for c in self._chunks if c["doc_id"] != doc_id]
        self.build(self._chunks) if self._chunks else setattr(self, "_index", None)

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)
```

**启动策略：** FastAPI `startup` 从 `knowledge_chunks.json` 加载所有 chunks，调用 `index.build()`。文档数量 <1000 时重建耗时 <1s，无冷启动问题。索引存 `app.state.bm25_index`。

#### `backend/knowledge/rag.py` — RAG 管线

```python
class RAGPipeline:
    """检索增强生成：BM25 query → top-k chunks → build context → Claude generate"""

    def __init__(self, index: BM25Index):
        self.index = index

    def retrieve(self, query: str, top_k: int = 5,
                 doc_ids: List[str] = None) -> List[SearchResult]:
        """检索：jieba 分词 → BM25 scoring → SearchResult 列表"""

    def build_context(self, results: List[SearchResult]) -> str:
        """构建增强上下文：格式化 retrieved chunks 注入 prompt"""

    def generate(self, request: RAGRequest) -> RAGResponse:
        """
        完整 RAG 流程：
        1. BM25 检索（可选 doc_ids 范围限制）
        2. build_context → 拼接 system prompt
        3. Claude API 调用（api_key 从 ANTHROPIC_API_KEY env var 读取）
        4. 返回 RAGResponse（含来源引用）
        """
```

#### `backend/knowledge/generator.py` — Claude API 调用

```python
import os, anthropic

def generate_with_context(prompt: str, context_chunks: List[dict],
                          style: str = "policy") -> tuple[str, list]:
    # API Key 从环境变量读取，由 ccswitch 管理，无需前端传参
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    """
    构建 Claude 调用：

    System Prompt（按 style 不同）：
    - policy: "你是一位政策文件撰写专家。请参考以下参考文档的表达方式、格式和知识，
               用正式、严谨的公文风格撰写..."
    - report: "你是一位教育成果报告撰写专家。请参考以下模板的结构和表达方式..."
    - general: "请参考以下文档的内容和表达方式..."

    格式模板：
    <reference_documents>
    [文档名] 第X章 > 第Y节
    内容：...

    [文档名] ...
    </reference_documents>

    <task>
    {user_prompt}
    </task>

    请确保：
    1. 格式和结构与参考文档保持一致
    2. 使用参考文档中的专业术语和表达方式
    3. 引用来源时标注文档名称
    """
```

#### `backend/api/knowledge_routes.py` — API 端点

全部挂载于 `/api/knowledge`：

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/documents` | 列出文档（`?folder_id=&type=&tag=&sort_by=`） |
| `GET` | `/documents/{id}` | 获取文档元数据 |
| `POST` | `/documents` | 上传文档（multipart: file + folder_id + tags）→ 解析 → 分块 → 写 JSON + 更新 BM25 索引 |
| `PUT` | `/documents/{id}` | 更新元数据 |
| `DELETE` | `/documents/{id}` | 删除文档（文件 + metadata + chunks + BM25 索引重建） |
| `GET` | `/documents/{id}/content` | 获取解析后的文档内容 |
| `GET` | `/documents/{id}/download` | 下载原始文件 |
| `POST` | `/search` | BM25 关键词检索（`{query, top_k?, doc_ids?}`）→ SearchResult[] |
| `POST` | `/generate` | **RAG 生成**（`{prompt, doc_ids?, top_k?, style}`）→ RAGResponse |
| `GET` | `/folders` | 列出文件夹 |
| `POST` | `/folders` | 创建文件夹 |
| `PUT` | `/folders/{id}` | 重命名文件夹 |
| `DELETE` | `/folders/{id}` | 删除文件夹 |
| `GET` | `/tags` | 获取所有标签 |
| `POST` | `/reparse/{id}` | 强制重新解析文档，重建 chunks + 更新 BM25 索引 |

**`backend/main.py` 修改：**
```python
from api import routes, knowledge_routes
from knowledge.storage import load_all_chunks
from knowledge.indexer import BM25Index

app = FastAPI(title="AI Analyst", version="2.0.0")

@app.on_event("startup")
async def startup():
    index = BM25Index()
    chunks = load_all_chunks()      # 从 knowledge_chunks.json 加载
    if chunks:
        index.build(chunks)
    app.state.bm25_index = index
    logging.info(f"BM25 index ready: {index.chunk_count} chunks")

app.include_router(routes.router, prefix="/api")
app.include_router(knowledge_routes.router, prefix="/api")
```

### upload 端点关键流程（POST /api/knowledge/documents）

```
1. 接收文件 → 校验类型 + 大小(<100MB)
2. 保存到 data/knowledge_files/{uuid}/original.ext
3. SHA256 哈希（去重校验）
4. parser.parse_document() → ParsedDocument
5. chunker.chunk_document() → chunks[]（含 id/text/heading_path 等字段）
6. storage.save_chunks(doc_id, chunks) → 追加写入 knowledge_chunks.json
7. app.state.bm25_index.add_chunks(chunks) → 实时更新内存索引
8. storage.save_doc(KnowledgeDocument)
9. 返回 KnowledgeDocument
```

### search 端点关键流程（POST /api/knowledge/search）

```
1. app.state.bm25_index.search(query, top_k, doc_ids=...) → top-k chunks with score
2. 查询 storage 补全 doc_type 等元数据
3. 返回 SearchResult[]
```

### generate 端点关键流程（POST /api/knowledge/generate）

```
1. BM25 检索（同 search 流程）
2. generator.generate_with_context(prompt, retrieved_chunks, style)
3. 读 ANTHROPIC_API_KEY env var → Claude API 调用
4. 返回 {generated_text, sources}
```

## 前端现有钩子对齐清单

以下是前端代码中已预留的所有知识库相关占位符/钩子，以及本方案如何逐一对接。

### 1. KnowledgePage.vue → 完整 UI 壳，所有数组为空

**现状明细与对接：**

| 现有钩子 | 当前状态 | 方案对接 |
|---------|---------|---------|
| `folders: []` (15行) | 空数组 | `store.folders` → `GET /api/knowledge/folders` |
| `files: []` (21行) | 空数组 | `store.documentsInCurrentFolder` → `GET /api/knowledge/documents?folder_id=` |
| `searchResults: []` (28行) | 空数组 | `store.searchResults` → `POST /api/knowledge/search` |
| `searchQuery` ref | 绑定到顶部搜索框但无处理 | `@keyup.enter` → `store.search(searchQuery)` |
| `searchText` ref | 绑定到语义搜索框但无处理 | 点击搜索按钮 → `store.search(searchText)` |
| `typeColors` (35行) | PDF/amber, XLSX/accent, DOCX/blue | 扩展：TXT → text-body, MD → purple |
| `selectedFolder` + `selectedFolderName` | 绑定但无数据 | 从 `store.folders` 填充，点击切换筛选 |
| `fileCount` computed | 依赖空 folders | 改用 `store.documentCount` |
| `viewMode` toggle | 浏览器/搜索切换正常 | 保持不变，两种模式各自接入数据 |
| `gridView` toggle | 列表/网格切换 | 实现网格 3 列 / 列表单列切换 |
| 文件夹点击 (71行) | `@click="selectedFolder = folder.id"` | 接入 `store.currentFolderId`，触发重新加载 |
| 标签筛选 (86行) | `v-for="t in []"` | `v-for="t in store.allTags"`，点击设置 tag 过滤 |
| 文件卡片 (102行) | `v-for="(file, i) in files"` | 替换为 `<DocumentCard v-for="doc in store.documentsInCurrentFolder">` |
| 文件类型徽章 (109行) | 硬编码 `file.type` | DocumentCard 组件内使用 typeColors |
| 搜索模式类型筛选 (153行) | `v-for="t in []"` | `v-for="t in ['PDF','DOCX','XLSX','TXT','MD']"` + 复选框状态 |
| 搜索结果 (170行) | `v-for="(r, i) in searchResults"` | 替换为 `<SearchResultCard v-for="r in store.searchResults">` |
| 相关度分数 (189行) | `{{ r.match }}` | 改为 `{{ (r.score * 100).toFixed(0) }}%` |
| 查看/引用按钮 (195行) | 无事件处理 | 查看 → 打开 DocumentPreview；引用 → 添加到 PolicyPage 参考列表 |
| "上传文档" 按钮 (54行) | 无事件 | `@click` → 打开 UploadDialog |
| "新建文件夹" 按钮 (55行) | 无事件 | `@click` → 弹出输入框 → `store.createFolder(name)` |
| "搜索" 按钮 (143行) | 无事件 | `@click` → `store.search(searchText)` |
| "语义"/"关键词" chip (141行) | 展示用 | BM25 方案统一为关键词检索，chip 只保留"关键词"选项，移除"语义"选项 |

### 2. PolicyPage.vue → 文档编辑器 + KB 集成点

**现状明细与对接：**

| 现有钩子 | 当前状态 | 方案对接 |
|---------|---------|---------|
| `outline: []` (7行) | 空数组 | 从 KB 模板文档提取 → 自动填充大纲结构 |
| "参考资料" 卡片 (87-89行) | 完全空白 | **核心集成点**：嵌入迷你 KB 搜索 + 选中文档列表 |
| "AI润色" Chip (51行) | accent 高亮，无事件 | 调用 `/generate`，style="polish"，上下文=当前编辑器内容 + 参考文档 |
| 导出按钮 (78-83行) | Word/PDF/Markdown，无事件 | 实现导出功能（前端生成 blob 下载） |
| 文档信息 (66行) | 字数/章节数/状态 全为 0/- | 从编辑器内容实时计算 |
| 格式化工具栏 (44行) | B/I/U/H1/H2/列表/引用/插图 | 实现 Markdown 编辑器基础功能 |

**PolicyPage "参考资料" 卡片改造详情：**
```
改造前（空卡片）：          改造后：
┌──────────────────┐      ┌─────────────────────────┐
│ 参考资料          │      │ 参考资料                 │
│                  │      │ 🔍 搜索知识库…           │
│  (空白)          │      ├─────────────────────────┤
│                  │      │ ☑ 2024年教育政策.docx    │
│                  │      │ ☑ 校园成果报告模板.docx   │
│                  │      │ ☐ 安全管理条例.pdf       │
│                  │      ├─────────────────────────┤
│                  │      │ [以选中文档为参考生成]    │
│                  │      │ [查看选中文档内容]        │
└──────────────────┘      └─────────────────────────┘
```

### 3. AnalyticsPage.vue → 对话模式已有 "知识库" 按钮

**现状：** 对话模式的数据源卡片中有 `<Button size="small" variant="secondary">知识库</Button>`（73行），无事件处理。

**方案修改：**
- 点击 "知识库" 按钮 → 打开文档选择器弹窗
- 选中的 KB 文档内容作为分析数据源
- chat 对话可引用 KB 中的数据（如 "根据知识库中的财务报告..."）

### 4. HomePage.vue → KB 相关指标

**现状明细与对接：**

| 现有钩子 | 当前状态 | 方案对接 |
|---------|---------|---------|
| "知识库文档" MetricCard (68行) | `value="-"` | 显示 `store.documentCount`（实时文档总数） |
| `services: []` (12行) | 空数组 | 添加知识库服务入口卡片 |
| `recentTasks: []` (20行) | 空数组 | 显示最近上传/搜索/生成操作 |
| "本月分析次数" (66行) | `value="-"` | 可从 KB 生成次数统计 |
| "生成报告" (67行) | `value="-"` | 可从 PolicyPage 导出次数统计 |

### 5. 类型系统 → 需要扩展

**`src/types/index.ts` 修改：**
```typescript
// FileType 增加 MD
export type FileType = 'PDF' | 'DOCX' | 'XLSX' | 'TXT' | 'MD'

// FileItem 保持兼容（KnowledgePage 使用新的 KnowledgeDocument 类型）
export interface FileItem {
  id: string
  name: string
  type: FileType
  size: string
  date: string
  tags?: string[]
}

// AIMessage 增加 sources（RAG 引用）
export interface AIMessage {
  id: string
  role: 'ai' | 'user'
  content: string
  timestamp: number
  sources?: Array<{
    doc_name: string
    chunk_text: string
    heading_path: string
    score: number
  }>
}
```

### 6. 路由 & 导航 → 无需改动

- `/knowledge` 路由已注册，`KnowledgePage` 懒加载
- 侧边栏 "个人知识库" (◗) 已显示
- Shell 面包屑已包含 `/knowledge → ['工作台', '个人知识库']`

### 7. 空目录占位 → 可选使用

项目中存在空目录骨架（Clean Architecture 遗留）：
- `src/domain/entities/` — 可放 KB 领域实体类型
- `src/infrastructure/services/` — 可放知识库基础设施服务
- `src/use_cases/policy/` — 可放政策生成用例

**方案决策：** 不引入这些空目录，保持现有扁平结构。新代码放在 `src/stores/`、`src/services/`、`src/types/`、`src/ui/components/knowledge/`。

---

## Frontend Architecture

### 新增文件

| 文件 | 用途 |
|------|------|
| `src/types/knowledge.ts` | KB TypeScript 类型 |
| `src/services/knowledgeApi.ts` | API 服务（fetch + 响应式状态） |
| `src/stores/knowledge.ts` | Pinia 知识库 store |
| `src/ui/components/knowledge/DocumentCard.vue` | 文件卡片 |
| `src/ui/components/knowledge/UploadDialog.vue` | 上传弹窗 |
| `src/ui/components/knowledge/SearchResultCard.vue` | 搜索结果卡片 |
| `src/ui/components/knowledge/DocumentPreview.vue` | 文档内容查看器 |

### 修改文件

| 文件 | 改动 |
|------|------|
| `src/ui/pages/knowledge/KnowledgePage.vue` | **核心改造**：接入 store，所有空数组替换为响应式数据，loading/empty/error 状态全覆盖，共 19 处钩子对齐 |
| `src/ui/pages/policy/PolicyPage.vue` | "参考资料"卡片集成 KB 搜索 + RAG 生成，"AI润色"接入 Claude |
| `src/ui/pages/home/HomePage.vue` | 知识库文档指标 → 实时统计，services 添加 KB 入口，recentTasks 显示 KB 操作 |
| `src/ui/pages/analytics/AnalyticsPage.vue` | "知识库"按钮接入文档选择器 |
| `src/types/index.ts` | `FileType` 增加 `'MD'`，`AIMessage` 增加 `sources?`，`FileItem` 保持兼容 |

### RAG 生成 UI 流程（PolicyPage）

```
PolicyPage 右侧 "参考资料" 卡片：
  ┌─────────────────────────┐
  │ 🔍 搜索知识库…          │
  ├─────────────────────────┤
  │ ☑ 2024年教育政策.docx   │
  │ ☑ 校园成果报告模板.docx  │
  ├─────────────────────────┤
  │ [以选中文档为参考生成]   │  ← 调用 POST /generate
  └─────────────────────────┘
```

点击生成 → prompts 编辑区内容 + 选中 doc_ids → `/api/knowledge/generate` → 返回内容填充编辑器 → 显示来源引用

## Implementation Phases

### Phase 1: RAG 核心管线（MVP）

**Backend:**
1. 安装依赖（chromadb, text2vec, torch, transformers, sentence-transformers, anthropic, python-docx, pdfplumber, jieba）
2. 创建 `backend/knowledge/models.py`
3. 创建 `backend/knowledge/storage.py`
4. 创建 `backend/knowledge/parser.py`
5. 创建 `backend/knowledge/chunker.py`
6. 创建 `backend/knowledge/embedder.py`（启动时加载 text2vec）
7. 创建 `backend/knowledge/vector_store.py`（ChromaDB 封装）
8. 创建 `backend/knowledge/rag.py`（检索管线）
9. 创建 `backend/knowledge/generator.py`（Claude API 调用）
10. 创建 `backend/api/knowledge_routes.py`
11. 修改 `backend/main.py`

**Frontend:**
1. 创建 `src/types/knowledge.ts`（KB 专用类型）
2. 修改 `src/types/index.ts`（FileType + MD, AIMessage + sources）
3. 创建 `src/services/knowledgeApi.ts`
4. 创建 `src/stores/knowledge.ts`
5. 创建 4 个新组件（DocumentCard, UploadDialog, SearchResultCard, DocumentPreview）
6. 改造 KnowledgePage.vue（19 处钩子对齐）
7. 改造 PolicyPage.vue（参考资料卡片 + AI生成）
8. 修改 HomePage.vue（知识库指标实时统计）
9. 修改 AnalyticsPage.vue（知识库按钮接入）

### Phase 2: 增强

- 文档自动标签（基于嵌入聚类或关键词）
- 模板提取（比较同类文档，提取公共结构）
- 混合搜索（向量 + 关键词融合）
- 知识库统计仪表盘

## Verification

### Phase 1 验证清单

**Backend (API):**
1. 启动后端 → 日志显示 `BM25 index ready: N chunks`（首次为 0）
2. `curl -F "file=@政策文件.docx" /api/knowledge/documents` → 200 + 返回 doc_id + chunk_count > 0
3. `curl /api/knowledge/search -d '{"query":"教育政策"}'` → 返回 top-k chunks 含 BM25 score（0-1）
4. `ANTHROPIC_API_KEY` 已由 ccswitch 设置的前提下：`curl /api/knowledge/generate -d '{"prompt":"撰写一份校园安全管理政策","style":"policy"}'` → Claude 返回生成文本 + sources
5. `curl -X DELETE /api/knowledge/documents/{id}` → 文件 + metadata + chunks 全部清理，日志显示 BM25 索引重建

**前端 — KnowledgePage（19 处钩子验证）:**
7. 页面加载 → 从 API 获取 folders + documents 列表，文件卡片正确显示类型徽章颜色
8. 文件夹点击 → 筛选文档列表 + 面包屑更新
9. 上传按钮 → UploadDialog 打开 → 拖拽/选文件 → 上传成功 → 列表中新增
10. 搜索输入 → 回车 → 搜索结果卡片展示（含相关度分数 + 摘录）
11. 搜索结果 "查看" → DocumentPreview 打开显示结构化内容
12. 搜索结果 "引用" → 文档添加到引用列表
13. 标签筛选 → 点击标签 → 文档列表过滤
14. 网格/列表视图切换正常
15. 空状态：无文档时显示引导提示

**前端 — PolicyPage 集成:**
14. "参考资料"卡片 → 搜索知识库 → 选中文档显示在列表中
15. "以选中文档为参考生成" → 调用 `/generate` → 内容填充编辑器
16. "AI生成" → 携带当前编辑器内容 + 参考文档 → Claude 生成

**前端 — HomePage + AnalyticsPage:**
17. HomePage "知识库文档" MetricCard 显示实时文档数量
18. AnalyticsPage "知识库"按钮 → 文档选择器弹窗

**回归测试:**
19. `cd backend && pytest` 无回归
20. `npm run type-check` 无类型错误
21. `npm run build` 构建成功
