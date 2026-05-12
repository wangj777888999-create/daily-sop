# AI Analyst v2 — 本地自用版分析报告

> **✅ 已完成（2026-04-26）** — B1-B6 全部修复，Q1-Q4、Q6 已清理。Q5（组件去重）和 Q7（异步执行）暂缓，无其他待办项。仅供历史参考。

> **使用场景假设**：本地单用户、单 worker、不联网部署、不对外暴露 API、不商业化。基于此重新分级。

> **进度图例**：✅ 已完成　🔲 待处理　⏸ 暂缓

---

## 进度概览

| 编号 | 任务 | 状态 |
|---|---|---|
| B1 | 状态枚举不一致 | ✅ 已完成 |
| B2 | ExecutionResult 字段对不上 | ✅ 已完成 |
| B3 | 前端调用了不存在的后端接口 | ✅ 已完成 |
| B4 | 文件名同名覆盖 | ✅ 已完成 |
| B5 | SOPImport 用 URL query 传代码 | ✅ 已完成 |
| B6 | 文件名→源码字符串替换 | ✅ 已完成 |
| Q1 | 清理调试日志 | ✅ 已完成 |
| Q2 | Vue ref<Map> 非响应式陷阱 | ✅ 已完成 |
| Q3 | 轮询清理加保险 | ✅ 已完成 |
| Q4 | 后端 storage 加单文件锁 | ✅ 已完成 |
| Q5 | 前端组件去重 | ⏸ 暂缓 |
| Q6 | accept 类型对齐 | ✅ 已完成 |
| Q7 | 同步执行阻塞 | ⏸ 暂缓 |
| 第四节 | 产品化议题 | ⏸ 暂缓 |

---

## 一、项目当前状态判断

| 维度 | 状态 | 说明 |
|---|---|---|
| 功能跑通 | ✅ 基本完整 | B1-B6 全部修复，核心链路已通 |
| 架构合理性 | ✅ 合适 | FastAPI + Vue + JSON 文件存储，单机自用刚好够 |
| 可维护性 | 🟡 良好 | 调试日志已清，类型对齐，组件去重（Q5）留待下次 |
| 安全性 | 🟢 不阻塞（本地） | 沙箱、鉴权、CORS 等暂可不管 |

---

## 二、必须修复（影响日常使用，1-2 天工作量）

### ✅ B1. 状态枚举不一致 — 已完成

- **现象**：后端返回 `status='success'`，前端判断 `status==='completed'`，UI 永远卡在"执行中"或不显示下载。
- **位置**：
  - `src/services/sopApi.ts:9` 类型定义
  - `src/ui/pages/sop/SOPExecute.vue:32, 85, 126, 135, 298`
- **修法**：选定一边，统一用 `success`。前端搜索 `'completed'` 全部替换。
- **实际改动**：
  - `src/services/sopApi.ts`：`ExecutionResult.status` 类型从 `'pending' | 'running' | 'completed' | 'failed'` 改为 `'pending' | 'running' | 'success' | 'failed'`，并新增导出 `ExecutionStatus` 类型。
  - `src/ui/pages/sop/SOPExecute.vue`：`hasResult`、轮询终止条件、`getStatusColor`、`getStatusLabel`、模板成功分支共 5 处 `'completed'` → `'success'`。
  - **未触碰**：`StepBadge.vue`、`SOPPage.vue`、`types/index.ts` 中的 `'completed'` 是步骤展示状态（StepStatus），与执行状态语义无关，保留。
- **验证**：`vue-tsc --noEmit` 在改动文件上无类型错误。

### ✅ B2. ExecutionResult 字段对不上 — 已完成

- **后端返回**：`/execute` → `{execution_id, status}`；`/execute/{id}/status` → `{execution_id, sop_id, status, input_files, output_file, error_message, created_at, completed_at}`
- **前端访问**：`execution.value.id`、`execution.progress`（后端从未返回 `progress` 字段）
- **修法**：前端 `sopApi.ts` 加适配层映射 `execution_id → id`、`error_message → error`，并删掉前端臆造的 `progress` 字段。
- **实际改动**：
  - `src/services/sopApi.ts`：
    - `ExecutionResult` 接口去掉 `progress`、`result`，补齐 `input_files`、`output_file`，将 `error_message` 在前端层重命名为 `error`。
    - 新增私有适配函数 `adaptExecutionResponse(data)`，统一处理后端两种返回格式。
    - `executeSOP` 与 `getExecutionStatus` 的返回值都过 adapter，`currentExecution`/`executions` map 写入的也是适配后的结构。
  - `src/ui/pages/sop/SOPExecute.vue`：
    - 模板中 4 处 `execution.progress` 全部替换为新加的 `getProgressPercent(execution.status)`，由状态派生百分比（pending 10、running 50、success/failed 100）。
    - "执行步骤"列表原本依赖 `execution.progress` 计算"哪些步骤已完成"，由于后端不返回逐步进度，改成统一展示步骤序号（不再骗用户假进度）。
- **验证**：`vue-tsc --noEmit` 在改动文件上无类型错误。
- **副作用 / 后续注意**：进度条现在是"语义化"而非"真实进度"。如果未来想要逐步进度条，需要后端 `ExecutionLog` 增加 `current_step` / `total_steps` 字段并在沙箱执行过程中回写。

### ✅ B3. 前端调用了不存在的后端接口 — 已完成

- `sopApi.ts` 调 `/api/sops/generate`，**后端没实现** → SOPCreate 的"智能生成步骤预览"按钮是死代码。
- **实际改动**：在 `backend/api/routes.py` 新增 `POST /sops/generate` 端点，按换行拆分描述生成步骤列表（占位实现，日后可接 LLM）。

### ✅ B4. 文件名同名覆盖 — 已完成

- **场景**：两次执行都用 `data.xlsx`，第二次会覆盖第一次的输入文件。
- **实际改动**：`backend/api/routes.py`：先生成 `exec_id`，再创建 `uploads/{exec_id}/` 目录，文件存入独立子目录，彻底隔离各次执行。

### ✅ B5. SOPImport 用 URL query 传整段 Python 代码 — 已完成

- **问题**：稍长的脚本撞 URL 长度上限，且代码出现在浏览器历史里。
- **实际改动**：`src/ui/pages/sop/SOPImport.vue`：改用 `sessionStorage.setItem('pending_sop_code', ...)` 传代码，路由只跳转不附参数。

### ✅ B6. 文件名→源码字符串替换 — 已完成

- **场景**：上传 `教练's 数据.xlsx`，单引号破坏代码生成。
- **实际改动**：`backend/api/routes.py`：废弃简单字符串替换，改为注入 `__INPUT_PATHS__ = json.dumps({...})` 前置代码块，文件名通过 `json.dumps` 正确转义，字典查找替代字面字符串。

---

## 三、值得做的清理（提升日常体验，半天）

### ✅ Q1. 清理调试日志 — 已完成

- **实际改动**：删除 `SOPCreate.vue` 中全部 `console.log('[SOPCreate] ...')`（原 4 处），以及 `SOPExecute.vue` 中的 `console.log('Execution completed:', execId)`。

### ✅ Q2. 移除 Vue ref<Map> 的非响应式陷阱 — 已完成

- **实际改动**：`src/services/sopApi.ts`：`executions` 从 `ref<Map<string, ExecutionResult>>(new Map())` 改为 `reactive(new Map<string, ExecutionResult>())`，`.set()` 调用处去掉 `.value`。

### ✅ Q3. 轮询清理加保险 — 已完成

- **实际改动**：`SOPExecute.vue`：新增 `onBeforeRouteLeave(() => stopPolling())`，与已有 `onUnmounted` 双保险。

### ✅ Q4. 后端 storage 加单文件锁 — 已完成

- **实际改动**：`backend/sops/storage.py`：
  - `_read_json`：加 `fcntl.flock(f, LOCK_SH)` 共享读锁。
  - `_write_json`：改为先写 `.tmp` 临时文件（持排他锁），完成后 `os.replace` 原子替换，彻底消除截断窗口期。

### 🔲 Q5. 前端组件去重 — 暂缓

- `SOPCreate.vue` / `SOPImport.vue` 中 `addTag/removeTag/addStep/removeStep/goBack` 完全重复。
- 计划抽到 `src/composables/useSopForm.ts`，等再加一个 SOP 表单页时一并处理。

### ✅ Q6. accept 类型对齐 — 已完成

- **实际改动**：`SOPExecute.vue`：文件上传 input 的 `accept` 属性去掉 `.txt`，与后端 `routes.py` 允许类型保持一致。

### ⏸ Q7. 同步执行阻塞 — 暂缓

- 自用单人没 DoS 问题，但 UI 在 60s 内完全卡死、没 loading 反馈。
- 计划：改成 `BackgroundTasks` + 立即返回 `exec_id`，前端已有的轮询逻辑就能复用。暂缓。

---

## 四、可暂缓（产品化 / 上线时再回来看）

> 这些**本地自用确实不用动**，记录在此供未来参考。

| 项 | 何时回来处理 |
|---|---|
| 沙箱安全（subprocess + regex 过滤可绕过） | 想给别人用、或跑不信任代码时 |
| CORS / 鉴权 / JWT / RBAC | 部署到任何非 localhost 时 |
| 限流 / CSRF | 上线对外 API 时 |
| 文件大小校验严格化（流式累计） | 处理超大文件或多用户时 |
| 沙箱网络隔离、cgroup 内存限制 | 跑外部贡献的 SOP 时 |
| 幂等键 `Idempotency-Key` | 网络不稳定环境、有重试逻辑时 |
| OpenAPI 自动生成 TS 类型 | 团队协作、契约频繁变动时 |
| 分页 `/sops`、`/logs` | 数据量超千条时 |
| 文件 magic byte 嗅探 | 接收外部上传时 |
| Vue 全局 Error Boundary | 想要更友好的错误页时 |
| 路由层 pytest | 团队协作 / CI 时 |

---

## 五、推荐执行顺序

```
✅ 第 1 天上午：B1 + B2        ← 已完成："执行成功 → 下载"流程已通
✅ 第 1 天下午：B3 + B4 + B6   ← 已完成：文件名相关 bug 全部消除
✅ 第 2 天上午：B5 + Q1 + Q6   ← 已完成：小毛刺清理完毕
✅ 第 2 天下午：Q2 + Q3 + Q4   ← 已完成：后端/前端体验升级
⏸ 未来某天：Q5（组件抽取）     ← 等再加一个 SOP 表单页时再做
⏸ 未来某天：Q7（异步执行）     ← 体验升级，暂缓
```

### 已完成变更摘要

| 日期 | 任务 | 改动文件 | 行级摘要 |
|---|---|---|---|
| 第一阶段 | B1 状态枚举统一 | `src/services/sopApi.ts`、`SOPExecute.vue` | `'completed'` → `'success'`，新增 `ExecutionStatus` 类型 |
| 第一阶段 | B2 字段适配 | 同上 | 新增 `adaptExecutionResponse()`、删除臆造 `progress`、用 `getProgressPercent(status)` 派生进度 |
| 第二阶段 | B3 后端补 `/sops/generate` | `backend/api/routes.py` | 新增端点，按换行拆分描述生成步骤列表 |
| 第二阶段 | B4 文件隔离 | `backend/api/routes.py` | 先生成 `exec_id`，上传文件存 `uploads/{exec_id}/` 子目录 |
| 第二阶段 | B5 sessionStorage 传代码 | `SOPImport.vue` | `query.code` → `sessionStorage.setItem('pending_sop_code', ...)` |
| 第二阶段 | B6 INPUT_PATHS 注入 | `backend/api/routes.py` | 废弃字符串替换，改为 JSON 序列化字典注入 + 字典查找替换 |
| 第二阶段 | Q1 清理调试日志 | `SOPCreate.vue`、`SOPExecute.vue` | 删除全部 `console.log` 调试输出 |
| 第二阶段 | Q2 reactive Map | `src/services/sopApi.ts` | `ref<Map>` → `reactive(new Map())`，`.set()` 正常触发响应式 |
| 第二阶段 | Q3 路由守卫 | `SOPExecute.vue` | 新增 `onBeforeRouteLeave(stopPolling)` 双保险 |
| 第二阶段 | Q4 文件锁 | `backend/sops/storage.py` | `fcntl` 共享/排他锁 + 原子 tmp→rename 写入 |
| 第二阶段 | Q6 accept 对齐 | `SOPExecute.vue` | 去掉 `.txt`，与后端允许类型一致 |

---

## 六、总结

**结论**：作为本地自用工具，架构选型合适、不需要大改。当前最真实的痛点是**前后端契约漂移**（B1/B2/B3）——这些是会让你"明明执行成功却看不到结果"的功能 bug，跟安全无关，必须先修。

**当前进展**：B1-B6 全部完成，Q1-Q4、Q6 清理完毕。核心功能链路（创建→导入→执行→下载）已稳定可用。剩余 Q5（组件抽取）和 Q7（异步执行）属锦上添花，第四节产品化议题暂缓。本地自用工具体验基本完整。




