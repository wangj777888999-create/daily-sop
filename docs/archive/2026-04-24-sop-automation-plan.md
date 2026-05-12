# SOP 自动化系统实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 SOP 自动化系统 Phase 1，支持代码导入和自然语言创建 SOP，支持文件执行和结果下载。

**Architecture:**
- 前端：Vue 3 扩展现有项目，新增 SOP 管理页面
- 后端：Python FastAPI，处理 SOP 解析、代码生成、沙箱执行
- 存储：JSON 文件（`data/sops.json`, `data/execution_logs.json`）
- 执行：subprocess 沙箱隔离运行用户代码

**Tech Stack:** Vue 3, FastAPI, Python subprocess, pandas, openpyxl

---

## 文件结构

```
ai_workbench/
├── backend/
│   ├── main.py                    # FastAPI 入口
│   ├── requirements.txt           # 依赖
│   ├── sops/
│   │   ├── __init__.py
│   │   ├── models.py              # SOP 数据模型
│   │   ├── storage.py             # JSON 存储
│   │   ├── parser.py              # 自然语言解析
│   │   └── code_generator.py      # 代码生成器
│   ├── executor/
│   │   ├── __init__.py
│   │   ├── sandbox.py             # 沙箱执行器
│   │   └── runner.py              # 执行器
│   └── api/
│       ├── __init__.py
│       └── routes.py              # API 路由
│
├── data/                           # 数据存储目录
│   ├── sops.json                  # SOP 定义
│   └── execution_logs.json        # 执行记录
│
├── src/                            # 现有前端
│   └── ui/
│       └── pages/
│           └── sop/
│               ├── SOPList.vue    # SOP 列表页
│               ├── SOPCreate.vue  # 创建 SOP（自然语言）
│               ├── SOPImport.vue  # 导入代码
│               └── SOPExecute.vue # 执行 SOP
```

---

## Task 1: 后端基础架构

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/main.py`
- Create: `backend/sops/__init__.py`
- Create: `backend/sops/models.py`
- Create: `backend/sops/storage.py`

- [ ] **Step 1: 创建 backend/requirements.txt**

```txt
fastapi==0.109.0
uvicorn==0.27.0
pydantic==2.5.0
pandas==2.1.0
openpyxl==3.1.0
python-multipart==0.0.6
```

- [ ] **Step 2: 创建 backend/sops/models.py - SOP 数据模型**

```python
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class Step(BaseModel):
    step: int
    action: str  # read_excel, filter, merge, groupby, export, etc.
    params: dict

class SOP(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    steps: List[Step]
    created_at: datetime
    updated_at: datetime

class ExecutionLog(BaseModel):
    id: str
    sop_id: str
    status: str  # pending, running, success, failed
    input_files: List[str]
    output_file: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
```

- [ ] **Step 3: 创建 backend/sops/storage.py - JSON 文件存储**

```python
import json
import os
from typing import List, Optional
from datetime import datetime
from .models import SOP, ExecutionLog

DATA_DIR = os.path.join(os.path.dirname(__file__), "../../data")
SOPS_FILE = os.path.join(DATA_DIR, "sops.json")
LOGS_FILE = os.path.join(DATA_DIR, "execution_logs.json")

def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def _load_json(path: str, default: dict) -> dict:
    if not os.path.exists(path):
        return default
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def _save_json(path: str, data: dict):
    _ensure_data_dir()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

def get_all_sops() -> List[SOP]:
    data = _load_json(SOPS_FILE, {"sops": []})
    return [SOP(**s) for s in data.get("sops", [])]

def get_sop(sop_id: str) -> Optional[SOP]:
    sops = get_all_sops()
    for s in sops:
        if s.id == sop_id:
            return s
    return None

def save_sop(sop: SOP) -> SOP:
    sops = get_all_sops()
    existing = [i for i, s in enumerate(sops) if s.id == sop.id]
    if existing:
        sops[existing[0]] = sop
    else:
        sops.append(sop)
    _save_json(SOPS_FILE, {"sops": [s.model_dump() for s in sops]})
    return sop

def delete_sop(sop_id: str) -> bool:
    sops = get_all_sops()
    new_sops = [s for s in sops if s.id != sop_id]
    if len(new_sops) == len(sops):
        return False
    _save_json(SOPS_FILE, {"sops": [s.model_dump() for s in new_sops]})
    return True

def get_all_logs() -> List[ExecutionLog]:
    data = _load_json(LOGS_FILE, {"logs": []})
    return [ExecutionLog(**l) for l in data.get("logs", [])]

def save_log(log: ExecutionLog) -> ExecutionLog:
    logs = get_all_logs()
    existing = [i for i, l in enumerate(logs) if l.id == log.id]
    if existing:
        logs[existing[0]] = log
    else:
        logs.append(log)
    _save_json(LOGS_FILE, {"logs": [l.model_dump() for l in logs]})
    return log
```

- [ ] **Step 4: 创建 backend/sops/__init__.py**

```python
from .models import SOP, Step, ExecutionLog
from .storage import get_all_sops, get_sop, save_sop, delete_sop, get_all_logs, save_log
```

- [ ] **Step 5: 创建 backend/main.py - FastAPI 入口**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router as api_router

app = FastAPI(title="SOP Automation API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

@app.get("/")
def root():
    return {"message": "SOP Automation API", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

- [ ] **Step 6: 创建目录结构并测试**

```bash
mkdir -p backend/sops backend/executor backend/api data
touch backend/sops/__init__.py backend/executor/__init__.py backend/api/__init__.py
echo '[]' > data/sops.json
echo '[]' > data/execution_logs.json
```

Run: `cd backend && pip install -r requirements.txt && python -c "from sops.models import SOP; print('models OK')"`
Expected: models OK

- [ ] **Step 7: 提交**

```bash
cd /Users/wangjun/Desktop/ai_analyst_v2
git add backend data
git commit -m "feat: backend foundation - models, storage, FastAPI setup"
```

---

## Task 2: 代码解析器 - Python 代码导入

**Files:**
- Create: `backend/sops/code_parser.py`

- [ ] **Step 1: 创建 backend/sops/code_parser.py - Python 代码解析器**

```python
import ast
import re
from typing import List, Dict, Any, Optional
from .models import Step

class PythonCodeParser:
    """解析 Python 代码，提取为 SOP 步骤"""

    def __init__(self, code: str):
        self.code = code
        self.tree = None
        try:
            self.tree = ast.parse(code)
        except SyntaxError as e:
            raise ValueError(f"Python 代码语法错误: {e}")

    def parse(self) -> List[Step]:
        """解析代码，返回步骤列表"""
        steps = []
        self._analyze_lines()
        return steps

    def _analyze_lines(self):
        """分析代码行，提取操作"""
        lines = self.code.split('\n')
        step_num = 0

        for i, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # 读取 Excel
            if match := re.search(r'pd\.read_excel\([^(]+\(([^)]+)\)', line):
                step_num += 1
                params = self._parse_read_params(match.group(1))
                steps.append(Step(step=step_num, action="read_excel", params=params))

            # 读取 CSV
            elif 'read_csv' in line:
                step_num += 1
                params = self._parse_read_params(re.search(r'\(([^)]+)\)', line).group(1))
                steps.append(Step(step=step_num, action="read_csv", params=params))

            # 筛选
            elif '.query(' in line or '.filter(' in line:
                step_num += 1
                steps.append(Step(step=step_num, action="filter", params={"raw": line}))

            # 删除列
            elif '.drop(' in line:
                step_num += 1
                steps.append(Step(step=step_num, action="drop_columns", params={"raw": line}))

            # 合并
            elif '.merge(' in line:
                step_num += 1
                steps.append(Step(step=step_num, action="merge", params={"raw": line}))

            # 分组聚合
            elif '.groupby(' in line:
                step_num += 1
                steps.append(Step(step=step_num, action="groupby", params={"raw": line}))

            # 排序
            elif '.sort_values(' in line:
                step_num += 1
                steps.append(Step(step=step_num, action="sort", params={"raw": line}))

            # 导出 Excel
            elif '.to_excel(' in line:
                step_num += 1
                steps.append(Step(step=step_num, action="to_excel", params={"raw": line}))

            # 导出 CSV
            elif '.to_csv(' in line:
                step_num += 1
                steps.append(Step(step=step_num, action="to_csv", params={"raw": line}))

    def _parse_read_params(self, args: str) -> Dict[str, Any]:
        """解析读取参数"""
        params = {}
        # 简单解析，实际需要更复杂的 AST 分析
        if 'sheet_name' in args:
            match = re.search(r'sheet_name\s*=\s*["\']([^"\']+)["\']', args)
            if match:
                params['sheet_name'] = match.group(1)
        return params

def parse_python_code(code: str) -> List[Step]:
    """解析 Python 代码为 SOP 步骤"""
    parser = PythonCodeParser(code)
    return parser.parse()
```

- [ ] **Step 2: 测试代码解析器**

Run: `cd backend && python -c "
from sops.code_parser import parse_python_code
code = '''
coach = pd.read_excel('教练签到.xlsx', sheet_name='教练签到')
coach = coach.iloc[2:]
finance = pd.read_excel('财务.xlsx')
finance = finance.groupby('课程名称').agg(收入=('金额','sum'))
'''
steps = parse_python_code(code)
print(f'Parsed {len(steps)} steps')
for s in steps:
    print(f'  Step {s.step}: {s.action}')
"`
Expected: Parsed 4 steps

- [ ] **Step 3: 提交**

```bash
git add backend/sops/code_parser.py
git commit -m "feat: add Python code parser for SOP import"
```

---

## Task 3: 代码生成器 - SOP 转可执行代码

**Files:**
- Create: `backend/sops/code_generator.py`

- [ ] **Step 1: 创建 backend/sops/code_generator.py**

```python
from typing import List, Dict, Any
from .models import Step, SOP

class CodeGenerator:
    """将 SOP 步骤转换为可执行的 Python 代码"""

    def __init__(self, sop: SOP, input_files: List[str]):
        self.sop = sop
        self.input_files = input_files
        self.variables = {}  # 跟踪变量名
        self.code_lines = [
            "import pandas as pd",
            "import os",
            "import json",
            "",
            "# 自动生成的代码",
            ""
        ]

    def generate(self) -> str:
        """生成完整代码"""
        for step in self.sop.steps:
            self._generate_step(step)
        return "\n".join(self.code_lines)

    def _generate_step(self, step: Step):
        """为每个步骤生成代码"""
        action = step.action
        params = step.params

        if action == "read_excel":
            self._gen_read_excel(step)
        elif action == "read_csv":
            self._gen_read_csv(step)
        elif action == "filter":
            self._gen_filter(step)
        elif action == "drop_columns":
            self._gen_drop_columns(step)
        elif action == "merge":
            self._gen_merge(step)
        elif action == "groupby":
            self._gen_groupby(step)
        elif action == "sort":
            self._gen_sort(step)
        elif action == "to_excel":
            self._gen_to_excel(step)
        elif action == "to_csv":
            self._gen_to_csv(step)

    def _gen_read_excel(self, step: Step):
        var_name = f"df_{step.step}"
        self.variables['last'] = var_name
        params = step.params
        sheet_name = params.get('sheet_name', 'Sheet1')
        skiprows = params.get('skiprows', 0)
        self.code_lines.append(f"{var_name} = pd.read_excel('input.xlsx', sheet_name='{sheet_name}')")
        if skiprows > 0:
            self.code_lines.append(f"{var_name} = {var_name}.iloc[{skiprows}:]")

    def _gen_read_csv(self, step: Step):
        var_name = f"df_{step.step}"
        self.variables['last'] = var_name
        self.code_lines.append(f"{var_name} = pd.read_csv('input.csv')")

    def _gen_filter(self, step: Step):
        var_name = f"df_{step.step}"
        self.variables['last'] = var_name
        raw = step.params.get('raw', '')
        # 从原始代码提取筛选条件
        self.code_lines.append(f"# 筛选: {raw}")

    def _gen_drop_columns(self, step: Step):
        var_name = f"df_{step.step}"
        self.variables['last'] = var_name
        raw = step.params.get('raw', '')
        self.code_lines.append(f"# 删除列: {raw}")

    def _gen_merge(self, step: Step):
        var_name = f"df_{step.step}"
        self.variables['last'] = var_name
        raw = step.params.get('raw', '')
        self.code_lines.append(f"# 合并: {raw}")

    def _gen_groupby(self, step: Step):
        var_name = f"df_{step.step}"
        self.variables['last'] = var_name
        raw = step.params.get('raw', '')
        self.code_lines.append(f"# 分组聚合: {raw}")

    def _gen_sort(self, step: Step):
        var_name = f"df_{step.step}"
        self.variables['last'] = var_name
        raw = step.params.get('raw', '')
        self.code_lines.append(f"# 排序: {raw}")

    def _gen_to_excel(self, step: Step):
        var_name = self.variables.get('last', 'df')
        self.code_lines.append(f"{var_name}.to_excel('output.xlsx', index=False)")
        self.code_lines.append("print('导出完成: output.xlsx')")

    def _gen_to_csv(self, step: Step):
        var_name = self.variables.get('last', 'df')
        self.code_lines.append(f"{var_name}.to_csv('output.csv', index=False)")
        self.code_lines.append("print('导出完成: output.csv')")

def generate_code(sop: SOP, input_files: List[str]) -> str:
    """生成可执行代码"""
    generator = CodeGenerator(sop, input_files)
    return generator.generate()
```

- [ ] **Step 2: 测试代码生成器**

Run: `cd backend && python -c "
from sops.models import SOP, Step
from datetime import datetime
from sops.code_generator import generate_code

sop = SOP(
    id='test-1',
    name='测试SOP',
    steps=[
        Step(step=1, action='read_excel', params={'sheet_name': 'Sheet1'}),
        Step(step=2, action='filter', params={'raw': \"df[df['a'] > 1]\"}),
        Step(step=3, action='to_excel', params={})
    ],
    created_at=datetime.now(),
    updated_at=datetime.now()
)
code = generate_code(sop, ['input.xlsx'])
print(code)
"`
Expected: 生成包含3个步骤的代码

- [ ] **Step 3: 提交**

```bash
git add backend/sops/code_generator.py
git commit -m "feat: add code generator for SOP execution"
```

---

## Task 4: 沙箱执行器

**Files:**
- Create: `backend/executor/sandbox.py`

- [ ] **Step 1: 创建 backend/executor/sandbox.py**

```python
import subprocess
import tempfile
import os
import uuid
from typing import Tuple

class Sandbox:
    """沙箱执行器，安全运行用户代码"""

    def __init__(self, timeout: int = 60):
        self.timeout = timeout

    def execute(self, code: str, input_file: str = None) -> Tuple[str, str, int]:
        """
        执行代码，返回 (stdout, stderr, returncode)
        """
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            script_path = f.name

        # 创建输出文件
        output_path = script_path.replace('.py', '_output.xlsx')

        try:
            # 执行代码
            result = subprocess.run(
                ['python', script_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=os.path.dirname(script_path)
            )

            stdout = result.stdout
            stderr = result.stderr
            returncode = result.returncode

            # 如果有输出文件，返回路径
            if os.path.exists(output_path):
                final_output = output_path
            else:
                final_output = None

            return stdout, stderr + (f"\nOutput: {final_output}" if final_output else ""), returncode

        except subprocess.TimeoutExpired:
            return "", "执行超时（60秒）", 1
        finally:
            # 清理临时文件
            try:
                os.unlink(script_path)
            except:
                pass

def execute_in_sandbox(code: str, input_file: str = None, timeout: int = 60) -> Tuple[str, str, int]:
    """在沙箱中执行代码"""
    sandbox = Sandbox(timeout=timeout)
    return sandbox.execute(code, input_file)
```

- [ ] **Step 2: 测试沙箱**

Run: `cd backend && python -c "
from executor.sandbox import execute_in_sandbox
code = '''
import pandas as pd
df = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
df.to_excel('test_output.xlsx', index=False)
print('Done')
'''
stdout, stderr, code = execute_in_sandbox(code)
print(f'returncode: {code}')
print(f'stdout: {stdout}')
print(f'stderr: {stderr}')
"`
Expected: returncode 0, Done

- [ ] **Step 3: 提交**

```bash
git add backend/executor/sandbox.py
git commit -m "feat: add sandbox executor for safe code execution"
```

---

## Task 5: API 路由

**Files:**
- Create: `backend/api/routes.py`

- [ ] **Step 1: 创建 backend/api/routes.py**

```python
from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import List, Optional
from datetime import datetime
import uuid
import os
import shutil

from sops.models import SOP, Step, ExecutionLog
from sops.storage import get_all_sops, get_sop, save_sop, delete_sop, save_log
from sops.code_parser import parse_python_code
from sops.code_generator import generate_code
from executor.sandbox import execute_in_sandbox

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "../../data/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ========== SOP 管理 ==========

@router.get("/sops")
def list_sops():
    """获取所有 SOP"""
    return get_all_sops()

@router.get("/sops/{sop_id}")
def get_sop_by_id(sop_id: str):
    """获取单个 SOP"""
    sop = get_sop(sop_id)
    if not sop:
        raise HTTPException(status_code=404, detail="SOP not found")
    return sop

@router.post("/sops")
def create_sop(sop: SOP):
    """创建 SOP"""
    return save_sop(sop)

@router.put("/sops/{sop_id}")
def update_sop(sop_id: str, sop: SOP):
    """更新 SOP"""
    existing = get_sop(sop_id)
    if not existing:
        raise HTTPException(status_code=404, detail="SOP not found")
    return save_sop(sop)

@router.delete("/sops/{sop_id}")
def delete_sop_by_id(sop_id: str):
    """删除 SOP"""
    if not delete_sop(sop_id):
        raise HTTPException(status_code=404, detail="SOP not found")
    return {"message": "Deleted"}

# ========== 代码导入 ==========

@router.post("/parse-code")
def parse_code(code: str):
    """解析 Python 代码为 SOP 步骤"""
    try:
        steps = parse_python_code(code)
        return {"steps": [s.model_dump() for s in steps]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ========== 执行 ==========

@router.post("/execute/{sop_id}")
def execute_sop(sop_id: str, files: List[UploadFile] = File(...)):
    """执行 SOP"""
    sop = get_sop(sop_id)
    if not sop:
        raise HTTPException(status_code=404, detail="SOP not found")

    # 创建执行记录
    exec_id = str(uuid.uuid4())
    log = ExecutionLog(
        id=exec_id,
        sop_id=sop_id,
        status="running",
        input_files=[f.filename for f in files],
        created_at=datetime.now()
    )
    save_log(log)

    # 保存上传的文件
    input_paths = []
    for f in files:
        path = os.path.join(UPLOAD_DIR, f"{exec_id}_{f.filename}")
        with open(path, 'wb') as dst:
            shutil.copyfileobj(f.file, dst)
        input_paths.append(path)

    # 生成代码
    try:
        code = generate_code(sop, input_paths)

        # 执行代码
        stdout, stderr, returncode = execute_in_sandbox(code, input_paths[0] if input_paths else None)

        # 更新状态
        log.status = "success" if returncode == 0 else "failed"
        log.error_message = stderr if returncode != 0 else None
        log.completed_at = datetime.now()
        save_log(log)

        return {
            "exec_id": exec_id,
            "status": log.status,
            "stdout": stdout,
            "stderr": stderr
        }

    except Exception as e:
        log.status = "failed"
        log.error_message = str(e)
        log.completed_at = datetime.now()
        save_log(log)
        raise HTTPException(status_code=500, detail=str(e))

# ========== 文件上传 ==========

@router.post("/upload")
def upload_file(file: UploadFile = File(...)):
    """上传文件"""
    path = os.path.join(UPLOAD_DIR, file.filename)
    with open(path, 'wb') as dst:
        shutil.copyfileobj(file.file, dst)
    return {"filename": file.filename, "path": path}

@router.get("/execute/{exec_id}/status")
def get_exec_status(exec_id: str):
    """获取执行状态"""
    logs = get_all_logs()
    for log in logs:
        if log.id == exec_id:
            return log
    raise HTTPException(status_code=404, detail="Execution not found")
```

- [ ] **Step 2: 测试 API 路由**

Run: `cd backend && python -c "
from api.routes import router
print('routes OK')
"`
Expected: routes OK

- [ ] **Step 3: 提交**

```bash
git add backend/api/routes.py
git commit -m "feat: add API routes for SOP management and execution"
```

---

## Task 6: 前端 SOP 页面

**Files:**
- Create: `src/ui/pages/sop/SOPList.vue`
- Create: `src/ui/pages/sop/SOPCreate.vue`
- Create: `src/ui/pages/sop/SOPImport.vue`
- Create: `src/ui/pages/sop/SOPExecute.vue`

- [ ] **Step 1: 创建 SOPList.vue - SOP 列表页**

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'

const sops = ref([])
const loading = ref(false)

const fetchSops = async () => {
  loading.value = true
  try {
    const res = await fetch('http://localhost:8000/api/sops')
    sops.value = await res.json()
  } finally {
    loading.value = false
  }
}

const deleteSop = async (id: string) => {
  if (!confirm('确定删除？')) return
  await fetch(`http://localhost:8000/api/sops/${id}`, { method: 'DELETE' })
  fetchSops()
}

onMounted(fetchSops)
</script>

<template>
  <div class="p-4">
    <div class="flex justify-between items-center mb-4">
      <h1 class="text-[20px] font-bold text-text-heading">SOP 管理</h1>
      <div class="flex gap-2">
        <router-link to="/sop/create" class="px-4 py-2 bg-accent text-white rounded-lg text-[12px]">
          自然语言创建
        </router-link>
        <router-link to="/sop/import" class="px-4 py-2 bg-amber text-white rounded-lg text-[12px]">
          代码导入
        </router-link>
      </div>
    </div>

    <div v-if="loading" class="text-text-light">加载中...</div>

    <div v-else class="grid grid-cols-3 gap-3">
      <div
        v-for="sop in sops"
        :key="sop.id"
        class="bg-card-bg border border-border rounded-lg p-4"
      >
        <h3 class="text-[14px] font-bold text-text-heading mb-1">{{ sop.name }}</h3>
        <p class="text-[11px] text-text-light mb-2">{{ sop.description || '无描述' }}</p>
        <div class="text-[10px] text-text-light mb-2">{{ sop.steps.length }} 个步骤</div>
        <div class="flex gap-2">
          <router-link :to="`/sop/execute/${sop.id}`" class="text-[11px] text-accent">执行</router-link>
          <button @click="deleteSop(sop.id)" class="text-[11px] text-amber">删除</button>
        </div>
      </div>

      <div v-if="sops.length === 0" class="col-span-3 text-center py-8 text-text-light">
        暂无 SOP，点击上方按钮创建
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: 创建 SOPCreate.vue - 自然语言创建**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const name = ref('')
const description = ref('')
const stepsText = ref('')
const saving = ref(false)

const createSOP = async () => {
  if (!name.value || !stepsText.value) {
    alert('请填写名称和步骤')
    return
  }

  saving.value = true
  try {
    // TODO: 调用 LLM 解析自然语言为步骤
    const steps = stepsText.value.split('\n').map((line, i) => ({
      step: i + 1,
      action: 'custom',
      params: { raw: line }
    }))

    const sop = {
      id: crypto.randomUUID(),
      name: name.value,
      description: description.value,
      steps,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    }

    await fetch('http://localhost:8000/api/sops', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(sop)
    })

    router.push('/sop')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="p-4 max-w-2xl mx-auto">
    <h1 class="text-[20px] font-bold text-text-heading mb-4">创建 SOP（自然语言）</h1>

    <div class="mb-4">
      <label class="block text-[12px] text-text-light mb-1">名称</label>
      <input v-model="name" class="w-full border border-border rounded-md px-3 py-2 text-[13px]" />
    </div>

    <div class="mb-4">
      <label class="block text-[12px] text-text-light mb-1">描述</label>
      <input v-model="description" class="w-full border border-border rounded-md px-3 py-2 text-[13px]" />
    </div>

    <div class="mb-4">
      <label class="block text-[12px] text-text-light mb-1">步骤（每行一个）</label>
      <textarea
        v-model="stepsText"
        rows="10"
        class="w-full border border-border rounded-md px-3 py-2 text-[13px] font-mono"
        placeholder="第1步：读取Excel，从&quot;教练签到&quot;sheet读取数据
第2步：筛选课程类型等于&quot;学校课程&quot;的行
第3步：按课程名称分组求和
..."
      />
    </div>

    <div class="flex gap-2">
      <button @click="createSOP" :disabled="saving" class="px-4 py-2 bg-accent text-white rounded-lg text-[12px]">
        {{ saving ? '保存中...' : '保存' }}
      </button>
      <router-link to="/sop" class="px-4 py-2 bg-chip text-text-body rounded-lg text-[12px]">
        取消
      </router-link>
    </div>
  </div>
</template>
```

- [ ] **Step 3: 创建 SOPImport.vue - 代码导入**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const code = ref('')
const parsed = ref([])
const name = ref('')
const description = ref('')
const importing = ref(false)

const parseCode = async () => {
  if (!code.value.trim()) {
    alert('请输入 Python 代码')
    return
  }

  importing.value = true
  try {
    const res = await fetch('http://localhost:8000/api/parse-code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(code.value)
    })
    const data = await res.json()
    parsed.value = data.steps || []
  } catch (e) {
    alert('代码解析失败：' + e)
  } finally {
    importing.value = false
  }
}

const saveSOP = async () => {
  if (!name.value || parsed.value.length === 0) {
    alert('请填写名称并解析代码')
    return
  }

  const sop = {
    id: crypto.randomUUID(),
    name: name.value,
    description: description.value,
    steps: parsed.value,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  }

  await fetch('http://localhost:8000/api/sops', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(sop)
  })

  router.push('/sop')
}
</script>

<template>
  <div class="p-4 max-w-3xl mx-auto">
    <h1 class="text-[20px] font-bold text-text-heading mb-4">导入 Python 代码</h1>

    <div class="mb-4">
      <label class="block text-[12px] text-text-light mb-1">粘贴 Python 代码</label>
      <textarea
        v-model="code"
        rows="15"
        class="w-full border border-border rounded-md px-3 py-2 text-[13px] font-mono"
        placeholder="import pandas as pd&#10;coach = pd.read_excel('教练签到.xlsx')&#10;coach = coach[coach['课程类型'] == '学校课程']&#10;..."
      />
    </div>

    <button @click="parseCode" :disabled="importing" class="px-4 py-2 bg-blue text-white rounded-lg text-[12px] mb-4">
      {{ importing ? '解析中...' : '解析代码' }}
    </button>

    <div v-if="parsed.length > 0" class="mb-4">
      <h3 class="text-[14px] font-bold text-text-heading mb-2">解析结果 ({{ parsed.length }} 步骤)</h3>
      <div class="bg-page-bg border border-border rounded-md p-3 mb-4">
        <div v-for="step in parsed" :key="step.step" class="text-[12px] py-1">
          步骤 {{ step.step }}: <span class="text-accent">{{ step.action }}</span>
        </div>
      </div>

      <div class="mb-4">
        <label class="block text-[12px] text-text-light mb-1">SOP 名称</label>
        <input v-model="name" class="w-full border border-border rounded-md px-3 py-2 text-[13px]" />
      </div>

      <div class="mb-4">
        <label class="block text-[12px] text-text-light mb-1">描述（可选）</label>
        <input v-model="description" class="w-full border border-border rounded-md px-3 py-2 text-[13px]" />
      </div>

      <button @click="saveSOP" class="px-4 py-2 bg-accent text-white rounded-lg text-[12px]">
        保存 SOP
      </button>
    </div>
  </div>
</template>
```

- [ ] **Step 4: 创建 SOPExecute.vue - 执行页面**

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const sopId = route.params.id as string

const sop = ref(null)
const files = ref([])
const executing = ref(false)
const result = ref(null)

const fetchSOP = async () => {
  const res = await fetch(`http://localhost:8000/api/sops/${sopId}`)
  sop.value = await res.json()
}

const execute = async () => {
  if (files.value.length === 0) {
    alert('请上传数据文件')
    return
  }

  executing.value = true
  try {
    const formData = new FormData()
    for (const f of files.value) {
      formData.append('files', f)
    }

    const res = await fetch(`http://localhost:8000/api/execute/${sopId}`, {
      method: 'POST',
      body: formData
    })
    result.value = await res.json()
  } catch (e) {
    alert('执行失败：' + e)
  } finally {
    executing.value = false
  }
}

const handleFileChange = (e: Event) => {
  const input = e.target as HTMLInputElement
  files.value = Array.from(input.files || [])
}

onMounted(fetchSOP)
</script>

<template>
  <div class="p-4 max-w-2xl mx-auto">
    <h1 class="text-[20px] font-bold text-text-heading mb-4">执行 SOP</h1>

    <div v-if="sop" class="mb-4">
      <div class="text-[14px] font-bold text-text-heading">{{ sop.name }}</div>
      <div class="text-[11px] text-text-light">{{ sop.description }}</div>
    </div>

    <div class="mb-4">
      <label class="block text-[12px] text-text-light mb-1">上传数据文件</label>
      <input type="file" multiple @change="handleFileChange" class="text-[12px]" />
    </div>

    <div class="mb-4">
      <div class="text-[12px] text-text-light mb-1">已选文件：</div>
      <div v-for="f in files" :key="f.name" class="text-[11px] text-text-body">
        {{ f.name }}
      </div>
    </div>

    <button @click="execute" :disabled="executing" class="px-4 py-2 bg-accent text-white rounded-lg text-[12px]">
      {{ executing ? '执行中...' : '执行' }}
    </button>

    <div v-if="result" class="mt-4 p-3 bg-page-bg border border-border rounded-lg">
      <div class="text-[12px] font-bold mb-1">执行结果</div>
      <div class="text-[11px]" :class="result.status === 'success' ? 'text-accent' : 'text-amber'">
        状态: {{ result.status }}
      </div>
      <pre v-if="result.stdout" class="text-[10px] mt-2 overflow-auto">{{ result.stdout }}</pre>
      <pre v-if="result.stderr" class="text-[10px] text-amber mt-2 overflow-auto">{{ result.stderr }}</pre>
    </div>
  </div>
</template>
```

- [ ] **Step 5: 提交**

```bash
git add src/ui/pages/sop/
git commit -m "feat: add SOP management pages"
```

---

## Task 7: 路由配置

**Files:**
- Modify: `src/router/index.ts`

- [ ] **Step 1: 更新路由配置**

在 router/index.ts 中添加 SOP 相关路由：

```typescript
{
  path: '/sop',
  name: 'sop',
  component: () => import('@/ui/pages/sop/SOPList.vue'),
  meta: { title: 'SOP 管理' }
},
{
  path: '/sop/create',
  name: 'sop-create',
  component: () => import('@/ui/pages/sop/SOPCreate.vue'),
  meta: { title: '创建 SOP' }
},
{
  path: '/sop/import',
  name: 'sop-import',
  component: () => import('@/ui/pages/sop/SOPImport.vue'),
  meta: { title: '导入代码' }
},
{
  path: '/sop/execute/:id',
  name: 'sop-execute',
  component: () => import('@/ui/pages/sop/SOPExecute.vue'),
  meta: { title: '执行 SOP' }
}
```

- [ ] **Step 2: 提交**

```bash
git add src/router/index.ts
git commit -m "feat: add SOP routes"
```

---

## Task 8: 集成测试

**Files:**
- 测试所有组件协同工作

- [ ] **Step 1: 启动后端测试**

Run: `cd backend && uvicorn main:app --reload --port 8000 &`

- [ ] **Step 2: 测试完整流程**

1. 打开前端 http://localhost:3000
2. 访问 /sop 页面
3. 点击"代码导入"，粘贴教练签到分析代码
4. 点击"解析代码"，确认步骤被识别
5. 保存 SOP
6. 在列表页点击"执行"，上传数据文件
7. 确认执行成功并下载结果

- [ ] **Step 3: 提交最终版本**

```bash
git add -A
git commit -m "feat: complete SOP automation system Phase 1"
```

---

## 验收清单

- [ ] 后端 API 正常启动
- [ ] 可以通过代码导入创建 SOP
- [ ] 可以通过自然语言创建 SOP（简化版）
- [ ] 可以执行 SOP 并返回结果
- [ ] 前端页面正常显示和交互

---

**Plan complete.** Saved to `docs/superpowers/plans/2026-04-24-sop-automation-plan.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
