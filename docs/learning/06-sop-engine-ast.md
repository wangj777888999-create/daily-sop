# 06 · SOP 引擎与 AST：把 Python 代码变结构、再变回去

> 本章你将看到的代码：
> - `backend/sops/code_parser.py`（Python → SOP）
> - `backend/sops/code_generator.py`（SOP → Python）
> - `backend/sops/data_source.py`（数据源识别）
> - `backend/sops/models.py`

这是整个项目的**核心创新点**——其它部分都是"通用的 Web 应用",这里才是"为什么这个项目存在"。

---

## 1. 问题：用户写的 Python 脚本，怎么变成"可复用的 SOP"

业务现场：

- 教练每周做一份 Excel 报表，基本上是 `pd.read_excel()` → 几个 `query` 过滤 → `groupby` → `to_excel()`。
- 上传新数据后想要"重跑一次"，但 Excel 文件名变了、列变了。
- 不想让用户每次都改代码，而是把"流程"抽成结构化对象，下次可以重新挂上不同的输入。

**核心思路**：

```
用户脚本.py ──[code_parser]──▶ SOP JSON ──[code_generator]──▶ 重生成代码 ──▶ 执行
```

两端可逆——这才是 SOP 的价值（不只是"记录",而是"可重放"）。

---

## 2. SOP 的形状

`backend/sops/models.py:5-9`：

```python
class Step(BaseModel):
    step: int            # 顺序
    action: str          # read_excel / filter / groupby / to_excel ...
    params: dict         # 参数（不同 action 各异）
    description: Optional[str] = ""
```

```python
# backend/sops/models.py:11-18
class DataSource(BaseModel):
    id: str
    name: str           # 推断的中文名
    type: str           # primary / reference / output
    variableName: str   # df 之类
    operation: str      # read / write
    codeSnippet: str
    lineNumber: int
```

完整 SOP：

```python
class SOP(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    steps: List[Step]
    dataSources: List[DataSource] = []
    tags: List[str] = []
    created_at: datetime
    updated_at: datetime
```

**这就是"结构化的工作流"**——每一步都不再是"一行 Python"，而是一个语义化对象。

---

## 3. 解析：从 Python 代码到 Step 列表

### 3.1 总体策略：AST 优先，正则兜底

```python
# backend/sops/code_parser.py:14-43
def parse(self, code: str) -> Dict[str, Any]:
    self.df_variables.clear()
    self.steps = []
    self.step_counter = 0

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return self._parse_with_regex(code)

    for node in tree.body:
        if isinstance(node, ast.Assign):
            self._analyze_assignment(node)
        elif isinstance(node, ast.Expr):
            self._analyze_expression(node)
        elif isinstance(node, ast.FunctionDef):
            self._analyze_function_def(node)
        elif isinstance(node, ast.Delete):
            self._analyze_delete(node)
    ...
```

要点：

- **`ast.parse(code)`**：Python 标准库。返回一棵抽象语法树，节点类型有 `Assign`, `Call`, `Attribute`, `BinOp` 等几十种。
- **顶层节点遍历**（`for node in tree.body`）：本项目只关心顶层语句，不递归进函数体（用户脚本一般是平铺的）。
- **AST 失败 → regex 回退**：用户的代码可能根本不合法 Python（漏写括号、import 丢一半），用 regex 兜底从字符串里硬抠出 `pd.read_excel('xxx')` 这类模式。**这是工程上正确的妥协**——不要让"代码错"导致整个 SOP 解析炸了。

### 3.2 一个具体识别：`pd.read_excel('foo.xlsx')`

AST 看到：
```
Assign(
  targets=[Name(id='df')],
  value=Call(
    func=Attribute(value=Name(id='pd'), attr='read_excel'),
    args=[Constant(value='foo.xlsx')],
    keywords=[]
  )
)
```

解析器把它识别为：
```json
{ "step": 1, "action": "read_excel", "params": { "file": "foo.xlsx" } }
```

regex 兜底版（`code_parser.py:51-63`）：
```python
read_excel_pattern = r"pd\.read_excel\(['\"](.+?)['\"]\s*(?:,\s*([^)]*))?\)"
for match in re.finditer(read_excel_pattern, code):
    file_path = match.group(1)
    extra = match.group(2) or ""
    params = {"file": file_path}
    sheet_match = re.search(r"sheet_name\s*=\s*['\"](.+?)['\"]", extra)
    if sheet_match:
        params["sheet_name"] = sheet_match.group(1)
    ...
```

> **本质**：AST 给你**结构**，正则只能给你**字符串模式**。AST 路径解到的更深、更准确，但写起来更长。

### 3.3 数据源推断（`data_source.py`）

仅有"step 列表"还不够，**用户更关心"我需要哪些 Excel/CSV 当输入"**。`parse_code_with_sources` 在 step 之外额外抽出 `dataSources`：

```python
{
  "id": "ds-1",
  "name": "签到原始数据",          # 从文件名推断的中文名
  "type": "primary",
  "variableName": "df",
  "operation": "read",
  "codeSnippet": "pd.read_excel('签到.xlsx')",
  "lineNumber": 3
}
```

UI 上展示成"这个 SOP 需要 1 个主数据 + 1 个参考数据"，用户上传时按名字对应即可。

> **设计点**：把"步骤"和"数据源"当两份独立的视图——同一个 AST，可以抽不同的关注点。这种"多视图解析"在 LLM 时代尤其有用（例如还可以再抽出"涉及到哪些列名"、"调用了哪些自定义函数"）。

---

## 4. 反向生成：从 SOP 到可执行代码

`backend/sops/code_generator.py:15-45`：

```python
def generate(self, sop: Dict[str, Any]) -> str:
    self.lines = []
    sop_name = sop.get("name", "未命名 SOP")
    self.lines.append(f"# SOP: {sop_name}")
    self.lines.append("import pandas as pd")
    self.lines.append("")

    for step in sop.get("steps", []):
        action = step.get("action", "")
        params = step.get("params", {})
        result_var = step.get("result_var")
        code = self._generate_step(action, params, result_var)
        if code:
            self.lines.append(code)

    return "\n".join(self.lines)
```

派发：
```python
generator_map = {
    "read_excel": self._generate_read_excel,
    "read_csv": self._generate_read_csv,
    "filter": self._generate_filter,
    "drop_columns": self._generate_drop_columns,
    "merge": self._generate_merge,
    "groupby": self._generate_groupby,
    "sort": self._generate_sort,
    "to_excel": self._generate_to_excel,
    "to_csv": self._generate_to_csv,
}
```

每个 `_generate_*` 都按 step 的 params 拼一行 Python 字符串。例如 filter：

```python
def _generate_filter(self, params, result_var):
    df = params['df']
    cond = params['condition']
    target = result_var or df
    return f"{target} = {df}.query('{cond}')"
```

### 4.1 安全考虑：condition 校验

用户的 SOP 里 filter 条件最终会进 `df.query('xxx')`——如果用户改 SOP 时塞了 `__import__("os").system("rm -rf")`，沙箱拦不住的话就麻烦了。

`_validate_condition`（行 333 附近）：

```python
pattern = r'^[\w\s\+\-\*/\.\'\"=<>!&\|(),]+$'
```

只允许字母、数字、空白和一组运算符。问题：**不允许 `in`、`not in`、`isna()`** 等常用条件。第 12 章把它列为"换 AST 校验"的修复项。

---

## 5. round-trip 不是真等价

走一遍：

```
原始代码 (用户写的) ──parse──▶ SOP ──generate──▶ 重生成代码
```

重生成代码**形式上不会和原代码一字不差**（变量名、注释、空行都丢了），但**语义上等价**——跑出来结果一样。这对用户来说够用：他们关心的是"能再跑一次得到相同结果"。

> 如果你要做"双向编辑"（在 SOP 编辑器修改后还要往原代码注释回填），那需要保留 AST 的 `lineno` 和 `col_offset`，工作量翻倍。本项目暂不支持。

---

## 6. 已知缺口（路线图重点 B 会修）

| 缺口 | 严重度 |
|---|---|
| 不支持 `apply` / `applymap` / `pivot_table` / `fillna` / `dropna` / `assign` / `astype` | 中 |
| `_validate_condition` 用正则不允许 `in`、`not in` | 中 |
| AST 失败回退 regex，regex 解出的步骤可能错乱 | 低 |
| `parse()` 函数超 100 行，分支太杂 | 低（可读性） |
| 算子规范散在 parser 和 generator 两边，没有"单一来源" | 中 |

第 12 章会把这些一次性整理为可执行任务。

---

## 动手练习

1. **跑一遍 round-trip**：找根目录的 `教练签到分析最终版.py`（用户样本），手动调用 `parse_code_with_sources(code)` 看 SOP，再 `SOPToExecutableCode(sop)` 看重生成代码——做个 diff。
2. **加 `fillna` 算子**（强推荐）：
   - 在 `code_parser.py` 加识别 `df.fillna(value)` 的分支。
   - 在 `code_generator.py` 加 `_generate_fillna` 派发。
   - 在 `test_code_parser.py` 加一条单测。
   这是 vibe coding 的经典练习题——你可以让 Claude Code 协助你把这三处一次性改完。
3. **写一个"算子规范"模块**：在 `backend/sops/operators.py` 用 dict 把每个 action 的参数 schema 列出来，让 parser/generator 都从这里读——消除当前两边各写一份的重复。

## 延伸阅读

- Python 官方 [`ast` 模块文档](https://docs.python.org/zh-cn/3/library/ast.html)：所有节点类型。
- [`ast.dump(tree, indent=2)`](https://docs.python.org/3/library/ast.html#ast.dump) —— 调试 AST 时打印节点结构最方便。
- [Green Tree Snakes](https://greentreesnakes.readthedocs.io/) —— 一份网友整理的 AST 节点说明，比官方更易读。
