# 01 · 架构总览

> 本章你将看到的代码：
> - `backend/main.py`
> - `vite.config.ts`
> - `backend/api/routes.py`
> - `data/`（JSON 持久化目录）

## 1. 一张图看清这个项目

```
浏览器 (用户)
  │
  │  http://localhost:3000   (Vite Dev Server)
  ▼
┌──────────────────────────────────┐
│ Vue 3 SPA  (src/)                │
│  ├── 路由 (vue-router)            │
│  ├── 状态 (Pinia stores)          │
│  └── 组件 (ui/pages, ui/components)│
└──────────────┬───────────────────┘
               │  fetch('/api/...')
               │  ↓ Vite proxy 转发
               ▼
http://localhost:8003   (FastAPI)
┌──────────────────────────────────┐
│ FastAPI app  (backend/main.py)    │
│  ├── /api/sops/*       routes.py  │
│  ├── /api/execute/*    routes.py  │
│  ├── /api/upload                  │
│  └── /api/knowledge/*  knowledge_routes.py │
└──┬──────────────┬─────────────┬──┘
   │              │             │
   ▼              ▼             ▼
SOP 引擎      Sandbox       RAG (向量库)
code_parser   subprocess    Chroma + Embeddings
code_generator                      ↑
   │              │             │
   ▼              ▼             ▼
 data/sops.json  data/uploads/  data/chroma_db/
 execution_logs.json
```

简化叙述：**SPA 用 Vite 起在 3000，所有 `/api` 请求被 Vite 代理到 8003 的 FastAPI；FastAPI 把数据落到 `data/` 下的 JSON 文件，不用数据库；执行 Python 脚本时启子进程当沙箱跑；做知识检索时走 ChromaDB**。

## 2. 关键入口文件逐字过

### 2.1 后端入口 `backend/main.py`

```python
# backend/main.py:1-21
import logging
from fastapi import FastAPI
from api import routes
from api import knowledge_routes

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="AI Analyst", version="2.0.0")

@app.on_event("startup")
async def startup():
    logging.info("Loading embedding service...")
    from knowledge.embedder import get_embedding_service
    get_embedding_service()
    logging.info("Embedding service ready.")

app.include_router(routes.router, prefix="/api")
app.include_router(knowledge_routes.router, prefix="/api")
```

要点：

- **挂两个 router**：SOP 业务和知识库（RAG）业务。两边都顶着 `/api` 前缀，前端代理一刀切就够。
- **`startup` 钩子提前加载 embedding 模型**：第一次 RAG 调用就不会让用户傻等几秒钟。
- **没有 `add_middleware(CORSMiddleware)`**：`docs/规划/2026-04-26-local-audit-report.md` 的 Q5 已经说得很清楚——这是**本地单用户工具**，CORS 没必要加。

### 2.2 Vite 代理 `vite.config.ts:5-22`

```typescript
server: {
  port: 3000,
  open: true,
  proxy: {
    '/api': {
      target: 'http://localhost:8003',
      changeOrigin: true
    }
  }
}
```

只要前端 `fetch('/api/sops')`，浏览器看到的 URL 仍然是 `http://localhost:3000/api/sops`，但 Vite 在中间偷偷转给了 8003。**好处：前端代码不需要 `import.meta.env.VITE_API_URL` 那一套环境切换**——单用户工具，没必要为生产部署做开关。

> **决策点**：单端口 dev + proxy vs CORS。我们选了 proxy，原因是简单、不引第三方安全配置。如果以后真要把后端独立部署到另一台机器，再切到 CORS 也来得及。

## 3. 这个项目刻意没做的事（以及理由）

| 没做 | 替代方案 | 为什么不做 |
|---|---|---|
| 数据库 | `data/*.json` + fcntl 锁 + atomic write（详见第 8 章） | 单用户、单机、低并发；数据 1 万条以下完全扛得住；省掉 schema 迁移 |
| 鉴权（JWT/Session）| 无 | 本地工具，登录就是浏览器一开 |
| CORS | Vite proxy | 见上 |
| 强沙箱（Docker / firecracker）| `subprocess` + import 黑名单 + 超时（详见第 7 章） | 跑的代码来自用户自己的脚本——不是恶意代码模型；做了"好心写错"的护栏就够 |
| 异步任务队列（Celery / RQ）| 同步等 60 秒 | 单用户，不会有"几十个 SOP 同时跑"的场景 |
| 前端测试 | 暂无 | 已知缺口（第 12 章会提）；目前靠类型检查 + 手测兜底 |

> **规模红线**：上面所有"不做"成立的前提是**单用户 + 本地 + 数据量 < 万级**。一旦你想把它变成多人协作 / 部署到公网，**第 12 章会列出哪些"没做"必须先补**。

## 4. 一次完整请求的生命周期（以"执行 SOP"为例）

走一遍 `POST /api/execute/{sop_id}`：

1. **浏览器**：用户在 `SOPExecute.vue` 选好 SOP 和输入文件，点"执行"。
2. **前端 API 层**：`src/services/sopApi.ts:executeSOP()` 把文件塞进 `FormData`，`fetch('/api/execute/{sop_id}')`。
3. **Vite Proxy**：转给 `http://localhost:8003/api/execute/{sop_id}`。
4. **FastAPI 路由**：`backend/api/routes.py:execute_sop()`（行 260+）：
   - 用 `uuid` 生成 `exec_id`，建 `data/uploads/{exec_id}/` 子目录（这是 B4 修复点）。
   - 把上传文件原文件名保存进去（`safe_filename`）。
   - 写一条 `ExecutionLog`（status=`pending`）到 `data/execution_logs.json`。
5. **代码生成**：`SOPToExecutableCode(sop_dict)` 把 SOP JSON 反向生成 Python 代码字符串。
6. **路径注入**：把 `__INPUT_PATHS__ = {...}` 字典作为 preamble 拼到代码最前面，再把代码里出现的字面文件名替换成 `__INPUT_PATHS__["..."]` 索引。**这是 B6 修复点，避免文件名含中文 / 引号 / 空格时字符串替换炸掉**（详见第 6 章）。
7. **沙箱执行**：`SandboxExecutor(timeout=60).execute(code)` 启子进程跑，详见第 7 章。
8. **写回结果**：log.status 改为 `success` 或 `failed`，`completed_at` 填好。
9. **响应**：返回 `{execution_id, status}`。
10. **前端适配**：`adaptExecutionResponse()`（`sopApi.ts:20`）把 `execution_id` 重命名为 `id`、`error_message` 重命名为 `error`，再写进 `currentExecution`。详见第 5 章。

> 你下次要排查执行问题，直接对着上面这 10 步逐个 print 就行。整个项目所有"复杂"链路都走得起这种"10 行讲清"的剖析。

## 5. 决策与取舍小结

- **同步执行 + 60 秒超时**（不是异步任务）：实现简单，前端 loading 转就好；超过 60 秒的活儿当前**根本不该被 SOP 化**。
- **JSON 文件 + fcntl 锁**：原子写靠 `os.replace()`（见 `backend/sops/storage.py:26`）；牺牲并发吞吐换"零依赖"。
- **单 CLAUDE.md 真理**：`PROJECT_GUIDE.md` 已废，所有"项目当前状态"问题先看 `CLAUDE.md`。

---

## 动手练习

> 用 Claude Code 跟你协作完成。

1. **加一条根路由**：在 `backend/main.py` 里加 `@app.get("/")` 返回 `{"name": "AI Analyst", "version": "2.0.0"}`，刷新 `http://localhost:8003/` 验证。
2. **改 Vite 端口**：把前端 dev server 改到 3100，看哪些地方需要同步改（提示：`vite.config.ts` 一处就够）。
3. **画自己的图**：用本章的图作为参考，对着 `routes.py` 把 `/api/sops` 的 4 个端点（CRUD）画成一张时序图。

## 延伸阅读

- FastAPI 官方教程的 [Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/)：理解 `include_router` 的官方姿势。
- Vite [Server Options](https://vitejs.dev/config/server-options.html)：`server.proxy` 的高级用法（重写路径、wsendpoint）。
- 想了解 "为什么不上数据库" 的更深思路，看 SQLite 作者的 [Appropriate Uses For SQLite](https://www.sqlite.org/whentouse.html)。
