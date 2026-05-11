# 04 · 后端 FastAPI 实战

> 本章你将看到的代码：
> - `backend/main.py`
> - `backend/api/routes.py`
> - `backend/api/knowledge_routes.py`
> - `backend/sops/models.py`

---

## 1. 为什么是 FastAPI

如果你写过 Flask：FastAPI 在 90% 的写法上和 Flask 类似（`@router.get(...)` ≈ `@app.route(...)`），但额外白送你三件礼物：

1. **类型提示驱动校验**：函数参数写 `body: SOPCreate`，FastAPI 就自动用 Pydantic 校验请求体并报错。
2. **自动 OpenAPI 文档**：跑起来访问 `http://localhost:8003/docs` 能直接看到所有接口，能在线试。
3. **`async def`（如果你需要）**：异步 IO 不必换框架。

> 本项目大量端点是 **同步 `def` 而不是 `async def`**——pandas 操作本身是 CPU/IO 阻塞的，加 `async` 也不会变快，反而把 simplicity 搞复杂。

---

## 2. 路由组织：`include_router` + 前缀

```python
# backend/main.py:19-20
app.include_router(routes.router, prefix="/api")
app.include_router(knowledge_routes.router, prefix="/api")
```

每个 router 在自己的 module 里：

```python
# backend/api/routes.py:18
router = APIRouter()

@router.get("/sops")
async def get_sops():
    ...
```

最终路径 = `/api` + `/sops` = `/api/sops`。

**为什么要拆？** 单文件 routes 长得快，按"业务域"切（SOP / Knowledge）天然合规。如果再大，可以做到 `routes/sops.py`、`routes/execute.py` 一类拆法。

---

## 3. 请求体：Pydantic 模型与 `Body(...)`

### 3.1 用模型校验（推荐）

```python
# backend/sops/models.py:5-9
class Step(BaseModel):
    step: int
    action: str
    params: dict
    description: Optional[str] = ""
```

```python
# 假想用法（本项目目前是 dict 派）：
@router.post("/sops")
async def create_sop(payload: SOPCreate):
    ...
```

**好处**：参数类型错（`step` 传成字符串）会自动 422，不用手写校验。

### 3.2 用 `dict = Body(...)`（本项目大量用）

```python
# backend/api/routes.py:148-149
@router.post("/sops", response_model=dict)
async def create_sop(body: dict = Body(...)):
    name = body.get("name", "未命名 SOP")
    ...
```

**好处**：兼容前端"今天传 code、明天传 steps"的多种 payload。  
**坏处**：失去自动校验，要自己 `body.get(...)` + `if not ...: raise HTTPException(...)`。

> **决策**：本项目选 `dict` 是因为前端传输 schema 在快速演进中（步骤格式还在变），先把灵活性占住，等 schema 稳定再换 Pydantic 模型。这是**对的取舍**——但要在 12 章列出"schema 稳定后改回 Pydantic"作为债务。

---

## 4. 响应模型：`response_model=`

```python
# backend/api/routes.py:68-70
class ExecutionResponse(BaseModel):
    execution_id: str
    status: str
```

```python
# backend/api/routes.py:260
@router.post("/execute/{sop_id}", response_model=ExecutionResponse)
async def execute_sop(sop_id: str, files: List[UploadFile] = File(...)):
    ...
    return { "execution_id": exec_id, "status": log.status }
```

`response_model` 做两件事：

1. **过滤多余字段**：你 return 一个有 5 个 key 的 dict，但 `ExecutionResponse` 只声明 2 个 → 只返回这 2 个。
2. **生成 OpenAPI schema**：`/docs` 能看到响应结构。

> 本项目部分端点 `response_model=dict`（行 132），相当于"我懒得写"——文档里就只写"返回 dict"。**新写端点请用具体模型**。

---

## 5. 文件上传：`UploadFile` + `File(...)`

```python
# backend/api/routes.py:260-273
@router.post("/execute/{sop_id}", response_model=ExecutionResponse)
async def execute_sop(sop_id: str, files: List[UploadFile] = File(...)):
    sop = get_sop(sop_id)
    if not sop:
        raise HTTPException(status_code=404, detail="SOP not found")

    exec_id = str(uuid.uuid4())
    exec_dir = os.path.join(UPLOAD_DIR, exec_id)
    os.makedirs(exec_dir, exist_ok=True)

    for file in files:
        file.file.seek(0, 2); size = file.file.tell(); file.file.seek(0)
        if size > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, ...)
        ...
```

要点：

- `UploadFile` 提供 `file` (类文件对象)、`filename`、`content_type`。
- **大小校验自己做**：FastAPI 不会替你做（它把流式上传交给你）。`seek(0, 2)` 跳到末尾拿 `tell()` = 文件大小，再 `seek(0)` 复位。
- **每次执行建一个独立子目录** `data/uploads/{exec_id}/`：避免不同执行的同名文件覆盖（这是审计中 B4 的修复）。

---

## 6. 错误处理：`HTTPException` + 状态码

`raise HTTPException(status_code=404, detail="SOP not found")` 会被 FastAPI 翻译成：

```json
{"detail": "SOP not found"}
```

状态码自动设成 404。

**反模式（本项目存在）**：

```python
# backend/api/routes.py:54  —— 裸 except
try:
    params = json.loads(desc.split(':', 1)[1].strip())
except:
    params = {}
```

裸 `except:` 会吞掉**所有**异常包括 `KeyboardInterrupt` 和 `SystemExit`，第 12 章会列为路线图修复项，正确写法是：

```python
except (json.JSONDecodeError, IndexError):
    params = {}
```

---

## 7. 日志：有的有，有的没

`backend/api/knowledge_routes.py:21` 用了：

```python
logger = logging.getLogger(__name__)
```

后续就能 `logger.info(...)` / `logger.exception(...)`。配合 `main.py:6` 的 `logging.basicConfig(level=logging.INFO)`，控制台能看到结构化日志。

但 `backend/api/routes.py` **没有** logger——SOP 路由出错你只能看到 FastAPI 默认 traceback 或者从 `log.error_message` 字符串里猜。第 12 章会把"给 routes.py 加 logger"作为整改任务。

---

## 8. 启动钩子：预热 embedding 模型

```python
# backend/main.py:11-16
@app.on_event("startup")
async def startup():
    logging.info("Loading embedding service...")
    from knowledge.embedder import get_embedding_service
    get_embedding_service()
    logging.info("Embedding service ready.")
```

`get_embedding_service()` 是单例：第一次调用加载 sentence-transformer 模型（数百 MB，几秒）。**放在 startup 里，第一个用户请求就不必等模型加载**。

> **小心**：`@app.on_event("startup")` 在 FastAPI 0.93+ 已经被建议换成 `lifespan` 上下文管理器。功能等价，但更灵活。本项目没换，第 12 章可以列为"小升级"。

---

## 9. 一个端点的完整生命周期（再看一遍）

`POST /api/execute/{sop_id}`：

```
路由匹配
   ↓
参数解析（sop_id 从 path、files 从 multipart）
   ↓
依赖注入（如果有 Depends）
   ↓
路由函数执行（同步 def，FastAPI 自动跑 threadpool）
   ↓
return value
   ↓
response_model 过滤
   ↓
JSON 序列化
   ↓
HTTP 响应
```

> 整条链条都很可读——这就是 FastAPI 的赢面。

---

## 动手练习

1. **看 `/docs`**：跑后端，访问 `http://localhost:8003/docs`，找到 `POST /api/execute/{sop_id}`，用 Try it out 上传一个文件、看返回。
2. **加一个 `/api/health` 端点**：返回 `{"status": "ok", "version": "2.0.0", "uptime_seconds": ...}`（用 `time.time() - start_time`）。
3. **改造 SOP 创建 endpoint**：把 `body: dict = Body(...)` 改成 Pydantic 的 `SOPCreatePayload`，复刻当前的"二选一（code/steps）"语义。提示：用 `Optional` + `model_validator`。

## 延伸阅读

- FastAPI [Request Files](https://fastapi.tiangolo.com/tutorial/request-files/) —— 多文件、流式上传的完整用法。
- FastAPI [Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) —— 比 `@app.on_event` 更新的写法。
- Pydantic [Validators](https://docs.pydantic.dev/latest/concepts/validators/) —— `@field_validator` 和 `@model_validator` 区别。
