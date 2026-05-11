# 05 · 前后端契约与适配器

> 本章你将看到的代码：
> - `backend/api/routes.py:31-63` 的 `_convert_steps_format`
> - `src/services/sopApi.ts:20-31` 的 `adaptExecutionResponse`
> - `src/services/sopApi.ts:62-86` 的 `getSOP`（出口适配）
> - `backend/sops/models.py`（后端 schema）
> - `src/types/sop.ts`（前端 schema）

---

## 1. 前后端"该不该一致"？

理想情况下：前后端用同一份 schema（比如 OpenAPI codegen 出 TypeScript 类型），完全对称。

现实情况下：本项目两端 schema **故意不一致**——并用一个**适配层**把它们接上。这章解释为什么这么干、它的优缺点、以及怎么做才不让"适配"变成"瀑布陷阱"。

---

## 2. 三个真实的不一致点

### 2.1 SOP Step：`step` vs `order`

**后端**（`backend/sops/models.py:5-9`）：

```python
class Step(BaseModel):
    step: int            # ← 用 step 表示顺序
    action: str
    params: dict
    description: Optional[str] = ""
```

**前端**（`src/types/sop.ts:12-21`）：

```typescript
export interface SOPStep {
  id: string             // ← 多一个稳定 id
  order: number          // ← 用 order
  action: string
  params: Record<string, any>
  description: string
  inputSources?: string[]
  outputSource?: string
  code?: string          // ← 多一个原始代码片段
}
```

差三个字段：`id`、`order`（vs `step`）、`code`。

为什么不让后端也用 `id` + `order`？因为后端用 `Step` 主要是为了"驱动 `code_generator` 生成代码"——它**不需要** id（id 是前端 React-style key 用），也不需要原始 `code`（生成代码是它自己的输出）。在后端那侧加这些字段，是给业务模型塞前端关注点。

### 2.2 ExecutionLog：`execution_id` vs `id`、`error_message` vs `error`

**后端响应**（`backend/api/routes.py:68-70` 与 `:73-81`）：

```python
class ExecutionResponse(BaseModel):
    execution_id: str
    status: str

class ExecutionStatusResponse(BaseModel):
    execution_id: str
    sop_id: str
    status: str
    input_files: List[str]
    output_file: Optional[str] = None
    error_message: Optional[str] = None
    ...
```

**前端期望**（`src/services/sopApi.ts:8-17`）：

```typescript
export interface ExecutionResult {
  id: string             // ← id 而不是 execution_id
  sop_id?: string
  status: ExecutionStatus
  input_files?: string[]
  output_file?: string
  error?: string         // ← error 而不是 error_message
  ...
}
```

为什么前端要重命名？前端的 `ExecutionResult` 在多个组件里被用，`id` 比 `execution_id` 短而清晰；统一用 `error` 让 UI 层能 `if (item.error)` 不绕。

### 2.3 状态枚举名：双方一致（值得记一笔）

`pending | running | success | failed`——两端都用同一组字符串，**没分歧**（`CLAUDE.md` 把这条写进了交叉契约）。

> **教训**：枚举一致是底线。字段名可以差，**值（value）必须一致**——值不一样的话，连 type narrowing 都救不了你。

---

## 3. 适配层：单点止血

### 3.1 入口适配（前端 → 后端）：`_convert_steps_format`

```python
# backend/api/routes.py:31-63
def _convert_steps_format(steps_data: list) -> List[Step]:
    """转换步骤格式：前端格式 -> 后端格式
    前端格式: {id, order, action, params, description, code}
    后端格式: {step, action, params, description}
    """
    converted_steps = []
    for s in steps_data:
        if 'step' in s and 'action' in s and 'params' in s:
            converted_steps.append(Step(**s))             # 已经是后端格式
        elif 'order' in s:
            action = s.get('action', '')
            params = s.get('params', {})
            if not action:
                desc = s.get('description', '')
                if ':' in desc:
                    action = desc.split(':', 1)[0].strip()
                    try:
                        params = json.loads(desc.split(':', 1)[1].strip())
                    except:
                        params = {}
            converted_steps.append(Step(
                step=s.get('order', 1),
                action=action,
                params=params,
                description=s.get('description', '')
            ))
    return converted_steps
```

它做了三件事：

1. 检测 payload 是后端格式还是前端格式（看是否有 `step` 字段）。
2. 把 `order` 重映射为 `step`。
3. 兼容老格式：`description` 可能是 `"read_excel: {...}"` 串，需要从中拆出 action 和 params。

> 这个函数是**对前端宽容、对后端严格**的典范——前端可以乱传，后端照单全收并转成自己的形式。

### 3.2 出口适配（后端 → 前端）：`adaptExecutionResponse`

```typescript
// src/services/sopApi.ts:20-31
function adaptExecutionResponse(data: any): ExecutionResult {
  return {
    id: data.execution_id ?? data.id,
    sop_id: data.sop_id,
    status: data.status,
    input_files: data.input_files,
    output_file: data.output_file,
    error: data.error_message ?? data.error,
    ...
  }
}
```

**`??` 是空值合并**：当 `execution_id` 是 undefined / null 时，回退到 `id`。这个写法兼容了"未来某天后端改名"的可能。

### 3.3 出口适配 SOP：`getSOP`

```typescript
// src/services/sopApi.ts:71-79
if (data.steps) {
  data.steps = data.steps.map((s: any, idx: number) => ({
    id: `step-${idx + 1}`,
    order: s.step || idx + 1,
    action: s.action || '',
    params: s.params || {},
    description: s.description || '',
    code: s.code || ''
  }))
}
```

`step → order`、合成 `id`、补齐 `code`。**注意 `id` 是基于位置的 `step-1, step-2, ...`**，后端没有持久化 step id——这是**有意的**：当用户重新排序步骤时，前端只关心数组顺序，不关心 id 稳定性。

---

## 4. 为什么不直接用 OpenAPI 自动生成

听起来很美：让前端从 `/openapi.json` 跑 codegen 直接生成 TypeScript 类型。

但它有代价：

1. **后端改任何字段，前端立刻类型崩**。这对快速迭代期是负担。
2. **前端不一定 100% 想用后端的命名**——`execution_id` vs `id` 的差异本身有价值。
3. **codegen 的工具链得维护**（`openapi-typescript`、`orval` 等），又是一份 dev dependency。

> **决策**：本项目阶段是手工适配。当 schema 稳定（半年没动）时，再上 codegen 不迟。**早期"自动化"成本高于收益**。

---

## 5. 适配层的"三个戒律"

1. **单点而不是散落**：所有跨栈映射只允许出现在 `_convert_steps_format` / `adaptExecutionResponse` / `getSOP` 这三个函数里。**不要让组件代码自己去 `data.execution_id || data.id`**——那样以后改名要全局 grep。
2. **前向兼容用 `??` / `||`**：旧字段也读、新字段也读，**先读新的**。等老字段下线一起删。
3. **给适配函数写 doc-string**：写明 from/to 两份 schema 的关键差异（看 `_convert_steps_format` 的 docstring）——这就是"自我注释的代码"。

---

## 6. 一个常见反模式：在视图组件里 ad-hoc 转换

❌ 错误：

```vue
<script setup>
const data = await fetchExecutionStatus(id)
const errorMsg = data.error_message || data.error    // 在视图里再适配一次
const execId   = data.execution_id || data.id        // 多处出现
</script>
```

✅ 正确：

```vue
<script setup>
const result = await getExecutionStatus(id)  // 已经走 adaptExecutionResponse
const errorMsg = result.error
const execId   = result.id
</script>
```

> **第二次"适配"出现的瞬间，债务就开始累积了。**

---

## 动手练习

1. **画个表对照三处不一致**：把 `models.py:Step` 和 `types/sop.ts:SOPStep` 字段一一对照画出来——你会更直观感受两端 schema 的差异原因。
2. **加一个新字段**：给 `ExecutionLog` 加 `duration_seconds: float`，从后端 `completed_at - created_at` 算，前端在 `ExecutionResult` 加 `duration?: number`，试着按"先后端、再适配、再前端"的顺序改。
3. **找一处违反单点适配**：grep `data.execution_id`，看 `sopApi.ts` 之外是否有人偷偷在视图层里访问后端原始字段——如果有，移到适配函数里。

## 延伸阅读

- 想做 codegen 的话：[openapi-typescript](https://github.com/drwpow/openapi-typescript) 的 README 案例；先在简单接口上试。
- 适配器模式（Adapter Pattern）的"GoF" 经典讲法在大多数设计模式书里都有；本项目实际上就是它的轻量化版本。
- `??` 与 `||` 的区别：[MDN Nullish coalescing](https://developer.mozilla.org/zh-CN/docs/Web/JavaScript/Reference/Operators/Nullish_coalescing_operator)。
