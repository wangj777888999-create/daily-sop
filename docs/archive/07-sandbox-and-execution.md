# 07 · 沙箱与执行：安全边界到底在哪

> 本章你将看到的代码：
> - `backend/sops/sandbox.py`（核心）
> - `backend/api/routes.py:260-345`（执行链路）

**先把话说在前面**：本项目的"沙箱"是一组**好心写错防护**，**不是**对抗恶意代码的安全边界。理解这一点，本章后面的设计取舍才说得通。

---

## 1. 设计目标

| 目标 | 是否做到 |
|---|---|
| 防止用户脚本里的 `import os; shutil.rmtree('/')` 等好心写错 | ✅ |
| 防止脚本死循环把后端卡死 | ✅（60 秒超时） |
| 防止脚本一次读 100GB 文件耗光内存 | ❌（路线图 B 要补 rlimit） |
| 防止恶意代码提权 / 逃逸 | ❌（没做也不打算做） |

**为什么不打算做完全的安全沙箱？** 因为本项目是**本地单用户工具**，跑的脚本就是用户自己的脚本——做完全的安全沙箱（Docker / firecracker / WASM）成本极高、收益对单人用户接近 0。

> 如果你以后要把这个项目改造成 SaaS / 多人，**沙箱必须先做强**。第 12 章列为"扩张红线"。

---

## 2. 三层防护

### 2.1 静态检查：import 黑/白名单（regex）

```python
# backend/sops/sandbox.py:20-34
BLOCKED_IMPORTS = [
    'os', 'sys', 'subprocess', 'socket',
    'urllib', 'http', 'requests', 'ftplib',
    'smtplib', 'pickle', 'eval', 'exec', 'open',
    'pathlib', 'glob', 'shutil', 'tempfile',
    'commands', 'ast', 'builtins',
    '__import__', 'importlib',
]

ALLOWED_IMPORTS = [
    'pandas', 'numpy', 'math', 'json', 're',
    'datetime', 'collections', 'itertools', 'functools',
    'typing', 'decimal', 'random', 'statistics', 'time',
]
```

`_validate_imports`（`sandbox.py:116-182`）做了**三类检查**：

1. 动态导入：`__import__('os')`、`importlib.import_module('os')`。
2. `from x import y` 形式。
3. `import x` 形式。

每条都用 regex。**同时**先剥离字符串字面量和注释，避免 `print("import os")` 把整行误判。

### regex 的局限（CLAUDE.md 已确认）

```python
# 这个能绕过
exec(__import__('o' + 's').system('echo pwned'))
```

regex 看到的是 `'o' + 's'`，识别不出运行时拼出 `os`。**所以本质上 regex 是"防呆"不是"防黑"**。

> 路线图 B 把它换成 AST 遍历：用 `ast.parse` 走一遍，找所有 `Import` / `ImportFrom` 节点 + `Call(func=Name('__import__'))` 节点。这样 `__import__('o' + 's')` 也能被识别（哪怕拿不到具体模块名，也能拒绝整个 `__import__` 调用）。

### 2.2 子进程隔离：`subprocess.Popen`

```python
# backend/sops/sandbox.py:79-95
process = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=self._get_safe_env(),
    start_new_session=True
)
```

要点：

- **`start_new_session=True`**：子进程是新会话的 leader，`os.killpg(os.getpgid(process.pid), SIGTERM)` 能一次干掉它和它的孙子进程。
- **`env=self._get_safe_env()`**：剔除大部分环境变量，只保留 PATH/HOME/LANG（`sandbox.py:223-238`）——避免脚本读到 AWS_SECRET_ACCESS_KEY 之类。
- **`text=True`**：stdout/stderr 直接以字符串解码而不是 bytes。

### 2.3 超时控制

```python
# backend/sops/sandbox.py:96-104
try:
    stdout, stderr = process.communicate(timeout=self.timeout)
    ...
except subprocess.TimeoutExpired:
    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    result['error'] = f'代码执行超时（超过 {self.timeout} 秒）'
```

**两阶段杀进程**：先发 SIGTERM 给 5 秒优雅退出机会；超过 5 秒发 SIGKILL 强杀。

> 这种"温柔后强硬"是 Unix 工程的标配，比"上来就 SIGKILL"友好——SIGTERM 时进程能 flush 文件、关 socket。

---

## 3. 文件路径注入：B6 的精彩修复

### 问题

用户脚本里写的是：

```python
df = pd.read_excel('签到 (5月).xlsx')
df.to_excel('结果_2026.xlsx', index=False)
```

但执行时，文件被存到了 `data/uploads/{exec_id}/签到 (5月).xlsx`——文件名不变，但路径改了。

**最 naive 的做法**：字符串替换。`code.replace('签到 (5月).xlsx', exec_dir + '/签到 (5月).xlsx')`。

**但失败了**：

- 文件名含中文 → 不同编码下可能 mismatch。
- 含空格 / 括号 / 引号 → 替换出来的字符串可能不是合法 Python 字面量。
- 多次出现 → 容易替换太多。

### 解法（`backend/api/routes.py:307-313`）

```python
input_paths_preamble = f"__INPUT_PATHS__ = {json.dumps(filename_mapping, ensure_ascii=False)}\n"
for safe_filename in filename_mapping:
    escaped_key = json.dumps(safe_filename)
    code = code.replace(f"'{safe_filename}'", f"__INPUT_PATHS__[{escaped_key}]")
    code = code.replace(f'"{safe_filename}"', f"__INPUT_PATHS__[{escaped_key}]")
code = input_paths_preamble + code
```

最终代码长这样：

```python
__INPUT_PATHS__ = {"签到 (5月).xlsx": "/abs/path/to/data/uploads/abc-123/签到 (5月).xlsx"}
import pandas as pd
df = pd.read_excel(__INPUT_PATHS__["签到 (5月).xlsx"])
df.to_excel('结果_2026.xlsx', index=False)
```

**好处**：

- `json.dumps` 帮你处理转义（`"`、`\` 都正确）。
- 一次 dict lookup 比一次替换更"语义化"——是程序逻辑而不是字符串操作。
- 文件名怎么变态都没事。

> **这是工程上"先想清楚再写"的典范**——不是 5 分钟能想到的解法。理解它你就理解了为什么 senior 写代码慢但稳。

---

## 4. 一次执行的失败模式与对应日志

```
sandbox.execute(code) returns:
{
  'success': bool,
  'output': str,         # stdout
  'error': str,          # stderr 或 sandbox 自己的错（如禁用导入）
  'return_code': int     # 进程返回码；超时或异常时 -1
}
```

`backend/api/routes.py:325-340` 把这些写回 `ExecutionLog`：

```python
if result["success"]:
    log.status = "success"
    log.output_file = result.get("output_file")     # ⚠️ 这里目前是 None
else:
    log.status = "failed"
    log.error_message = result.get("error", "Unknown error")
```

### 已知问题：`output_file` 链路断

- SandboxExecutor 当前不把"代码生成的输出文件路径"写进 result。
- 因此 `log.output_file` 永远是 None，`/api/execute/{id}/download` 永远 404。

第 12 章修复方案：在生成代码末尾自动注入：

```python
import json as __json
result = {"output_file": "/abs/path/to/output.xlsx"}
print("__SOP_RESULT__:" + __json.dumps(result))
```

执行后从 stdout 解析 `__SOP_RESULT__:` 行得到 output_file 路径。

---

## 5. 当前所有"故意没做"的项

| 项 | 当前 | 路线图 |
|---|---|---|
| CPU/内存上限 | 没做 | 用 `resource.setrlimit(RLIMIT_CPU, ...)` 在子进程启动前设 |
| 文件系统隔离 | 没做（脚本能读写它有权限的任何路径） | 改为先 `chdir(exec_dir)`，并 chroot / mount namespace（成本大） |
| 网络隔离 | 没做（脚本理论上可以 socket，但 import 层把 socket 拦了） | 用 unshare network namespace（仍非强隔离） |
| stdout / stderr 截断 | 不截 | 长输出占内存，加 `maxsize` 截尾保留 |

---

## 动手练习

1. **试着绕过 import 检查**：写一段含 `__import__('o' + 's')` 的 SOP，看是否真能执行 `os.system(...)`。**这是合法的安全研究，前提是你只在自己机器上玩**——就当作"理解为什么 regex 不够"。
2. **加资源限制**：在 `sandbox.py` 的 `Popen` 之前加 `preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_AS, (512*1024*1024, 512*1024*1024))`，限制子进程最多用 512MB。注意 macOS 上 RLIMIT_AS 行为和 Linux 不同。
3. **修 output_file 链路**：实现第 4 节末尾的 `__SOP_RESULT__:` 协议。这是路线图 B3 的事，做完 download 接口就不再 404。

## 延伸阅读

- Python `subprocess` 模块的 [`Popen.communicate(timeout=)`](https://docs.python.org/3/library/subprocess.html#subprocess.Popen.communicate)：注意 timeout 后**必须自己 kill**，否则进程会留尸。
- Linux 的 [`prlimit(1)`](https://man7.org/linux/man-pages/man1/prlimit.1.html) / `setrlimit(2)`：限制 CPU、内存、文件大小、打开文件数等。
- 真想学强沙箱：[gVisor](https://gvisor.dev/) 与 [Firecracker](https://firecracker-microvm.github.io/) 的对比——你会更理解"我们这套"的边界。
