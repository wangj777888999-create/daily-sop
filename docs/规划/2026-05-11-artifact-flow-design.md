# 工具间数据流通方案设计

> 日期: 2026-05-11
> 状态: 待评审

## 背景与目标

当前「课时费计算器」是独立 HTML 工具，用户需手动下载上游 Excel 再上传。随着工具增多（如即将新增的「校内月度分析」），这种手动传递数据的方式不可持续。

**目标**：在平台内建立统一的数据产出物（artifact）体系，让上游工具生成的数据能直接被下游工具消费，无需手动导入导出。

## 整体架构

```
┌─────────────────────────────────────────────────┐
│                   平台前端 (Vue)                  │
│                                                   │
│  ┌──────────────┐    ┌───────────────────────┐   │
│  │ 校内月度分析   │    │  课时费计算器 (iframe)  │   │
│  │ (Vue 原生页面) │    │                       │   │
│  │              │    │  ┌─ 从平台导入 按钮 ─┐  │   │
│  │  生成 → 存储  │    │  │ postMessage 注入  │  │   │
│  └──────┬───────┘    │  └──────────────────┘  │   │
│         │            └───────────▲─────────────┘   │
│         ▼                        │                  │
│  ┌──────────────────────────────┴──────────┐       │
│  │         Artifacts API (后端)             │       │
│  │   POST /api/artifacts  创建产出物         │       │
│  │   GET  /api/artifacts   列表查询          │       │
│  │   GET  /api/artifacts/:id 获取详情        │       │
│  │   DELETE /api/artifacts/:id 删除          │       │
│  └──────────────────────────────────────────┘       │
│                        │                             │
└────────────────────────┼────────────────────────────┘
                         ▼
              ┌─────────────────────┐
              │  data/artifacts/    │
              │  {artifact_id}.json │
              │                     │
              │  元信息 + 数据内容    │
              └─────────────────────┘
```

## 模块设计

### 1. Artifact 数据模型

**存储位置**: `data/artifacts/{artifact_id}.json`

**JSON 结构**:

```json
{
  "id": "art_20260511_001",
  "name": "2026年4月 校内月度分析",
  "type": "monthly-analysis",
  "source_tool": "monthly-analysis",
  "created_at": "2026-05-11T10:30:00",
  "schema_version": "1",
  "data": {
    "courses": [
      {
        "dept": "教培一部",
        "school": "XX小学",
        "course": "篮球基础",
        "courseRaw": "张三_篮球基础",
        "coach": "张三",
        "people": 25,
        "lessons": 12,
        "revenue": 3600
      }
    ],
    "attendance": {
      "张三|篮球基础": {
        "total": 12,
        "在岗": 10,
        "迟到": 1,
        "早退": 0,
        "旷工": 1,
        "dateList": ["2026-04-01", "2026-04-03"],
        "durationMap": { "45": 8, "60": 4 }
      }
    }
  }
}
```

**`type` 字段**标识数据类型，下游工具根据 `type` 判断能否消费。初始定义:

| type | 说明 | 消费方 |
|------|------|--------|
| `monthly-analysis` | 校内月度分析表 | 课时费计算器 |

**`source_tool` 字段**标识数据由哪个工具产出，用于追溯来源。

### 2. 后端 API 设计

基于现有 `backend/sops/storage.py` 的 JSON 文件存储方案扩展。

**新增文件**: `backend/artifacts.py`

```python
# 核心函数
def list_artifacts(type: str = None) -> list[dict]   # 按 type 筛选
def get_artifact(artifact_id: str) -> dict | None     # 获取单个
def save_artifact(artifact: dict) -> dict              # 保存（原子写入）
def delete_artifact(artifact_id: str) -> bool           # 删除
```

**路由** (`backend/api/routes.py` 新增):

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/artifacts` | 创建 artifact |
| GET | `/api/artifacts?type=xxx` | 列表查询（可按 type 筛选） |
| GET | `/api/artifacts/:id` | 获取单个 artifact 完整数据 |
| DELETE | `/api/artifacts/:id` | 删除 artifact |

复用现有的 `storage.py` 文件锁和原子写入机制。

### 3. 上游工具：校内月度分析

**形态**: Vue 原生页面（`src/ui/pages/tools/MonthlyAnalysis.vue`），不走 iframe。

**理由**:
- 需要调用后端 API 存储 artifact
- 后续可能关联平台内已有数据（知识库、历史分析等）
- iframe 内无法调用平台的 API 层（跨域、鉴权等问题）

**页面功能**（本次只做框架，业务逻辑后续填充）:
- 上传原始数据文件（或从其他来源获取）
- 执行分析计算
- 预览结果
- 「保存到平台」按钮 → 调用 POST /api/artifacts

**工具注册**: 在 `ToolboxPage.vue` 的 tools 数组中新增条目，`route` 指向 Vue 路由而非 iframe HTML。

```typescript
{
  id: 'monthly-analysis',
  name: '校内月度分析',
  description: '月度校内数据分析，产出课时费计算所需的月度分析表',
  icon: '◈',
  color: '#6366f1',
  tags: ['分析', '月度'],
  route: '/tools/monthly-analysis',  // Vue 路由，非 iframe
}
```

### 4. 下游工具：课时费计算器改造

**改动点**:

a) **新增「从平台导入」按钮**（在数据导入页面上方），点击后弹出 artifact 选择弹窗

b) **Artifact 选择弹窗**:
- 调用 `GET /api/artifacts?type=monthly-analysis` 获取可用列表
- 展示名称、来源工具、创建时间
- 用户选择后，将 artifact.data 注入现有的 `DATA` 对象

c) **数据注入逻辑**:
- artifact.data.courses → `parseCourses` 的输出格式
- artifact.data.attendance → `DATA.attendance`
- 复用现有的 `mergeData()` 完成后续流程

d) **iframe 通信机制**:
- 父页面（Vue）通过 `postMessage` 将 artifact 数据发送给 iframe
- iframe 内监听 `message` 事件，收到数据后自动填充
- 通信协议:

```typescript
// 父页面 → iframe
iframe.contentWindow.postMessage({
  type: 'ARTIFACT_INJECT',
  artifact: { name, type, data: { courses, attendance } }
}, '*');

// iframe 内监听
window.addEventListener('message', (e) => {
  if (e.data?.type === 'ARTIFACT_INJECT') {
    injectArtifactData(e.data.artifact);
  }
});
```

### 5. 工具箱页面改造

**ToolDetailPage.vue** 需要区分两种工具类型：
- iframe 工具（现有课时费计算器）→ 渲染 iframe
- Vue 路由工具（校内月度分析）→ 渲染 `<router-view>`

**ToolboxPage.vue** 已有的 tools 数组通过新增字段区分:
```typescript
{
  id: 'fee-calculator',
  type: 'iframe',           // iframe 工具
  src: '/tools/课时费计算器.html',
  iframeHeight: 800,
},
{
  id: 'monthly-analysis',
  type: 'vue',              // Vue 原生页面工具
  route: '/tools/monthly-analysis',
}
```

### 6. 路由配置

在 `src/router/index.ts` 中新增:
```typescript
{
  path: '/toolbox/:toolId',
  // ...
  children: [
    { path: 'monthly-analysis', component: MonthlyAnalysis }
  ]
}
```

## 数据流总结

```
用户操作                    系统行为
────────                    ────────
1. 用户在「校内月度分析」
   上传数据 → 执行分析
                               生成 courses + attendance 数据

2. 用户点击「保存到平台」
                               POST /api/artifacts
                               → data/artifacts/art_xxx.json 持久化

3. 用户打开「课时费计算器」
   点击「从平台导入」
                               GET /api/artifacts?type=monthly-analysis
                               → 展示可选列表

4. 用户选择某个 artifact
                               父页面 postMessage → iframe
                               → 注入 DATA 对象
                               → 复用现有 mergeData() / calcFromRules() 流程
```

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/artifacts.py` | 新增 | artifact CRUD 逻辑 |
| `backend/api/routes.py` | 修改 | 新增 /api/artifacts 路由 |
| `src/ui/pages/tools/MonthlyAnalysis.vue` | 新增 | 校内月度分析页面（框架） |
| `src/ui/pages/toolbox/ToolDetailPage.vue` | 修改 | 支持 vue 类型工具 |
| `src/ui/pages/toolbox/ToolboxPage.vue` | 修改 | tools 数组新增条目、支持 vue 类型 |
| `src/router/index.ts` | 修改 | 新增工具路由 |
| `public/tools/课时费计算器.html` | 修改 | 新增平台导入按钮 + postMessage 监听 |

## 不在本次范围内

- 校内月度分析的具体业务逻辑（后续单独设计）
- 知识库 / RAG 集成
- 用户鉴权（本地单用户场景不需要）
- 数据库迁移（沿用 JSON 文件方案）
