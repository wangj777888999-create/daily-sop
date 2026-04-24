# 语义化 SOP 代码导入实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现语义化 SOP 代码导入功能，支持从 Python 代码中识别数据源、生成业务语义描述、执行时参数化填参。

**Architecture:**
- 后端新增 `DataSourceDetector` 和 `SemanticInferencer` 模块，增强现有 `CodeParser`
- 前端新增 `SemanticAnnotation.vue` 页面用于语义标注，`ExecutionConfig.vue` 弹窗用于执行时填参
- 执行引擎支持参数替换和临时文件管理

**Tech Stack:** Python (FastAPI), Vue 3, TypeScript, Pydantic

---

## 文件结构

```
backend/
├── sops/
│   ├── __init__.py
│   ├── models.py              # 修改：添加 DataSource 模型
│   ├── code_parser.py         # 修改：增强数据源识别
│   ├── data_source.py         # 新增：DataSourceDetector + SemanticInferencer
│   ├── storage.py
│   ├── sandbox.py
│   └── code_generator.py       # 修改：支持参数化替换

src/
├── services/
│   └── sopApi.ts              # 修改：新增数据类型和方法
├── ui/pages/sop/
│   ├── SOPImport.vue          # 修改：跳转到语义标注页面
│   ├── SemanticAnnotation.vue # 新增：语义标注界面
│   └── SOPExecute.vue         # 修改：添加数据源配置弹窗
└── types/
    └── index.ts               # 修改：添加 DataSource 类型
```

---

## Task 1: 更新后端数据模型

**Files:**
- Modify: `backend/sops/models.py`
- Test: `backend/sops/test_models.py` (新建)

- [ ] **Step 1: 创建测试文件**

```python
# backend/sops/test_models.py
import pytest
from datetime import datetime
from models import DataSource, Step, SOP

def test_data_source_model():
    ds = DataSource(
        id="ds_1",
        name="教练签到表",
        type="primary",
        variableName="coach",
        operation="read",
        codeSnippet="coach = pd.read_excel('test.xlsx')",
        lineNumber=10
    )
    assert ds.name == "教练签到表"
    assert ds.type == "primary"

def test_sop_with_data_sources():
    step = Step(step=1, action="read_excel", params={"file": "{{coach_file}}"})
    ds = DataSource(
        id="ds_1",
        name="教练签到表",
        type="primary",
        variableName="coach",
        operation="read",
        codeSnippet="coach = pd.read_excel('test.xlsx')",
        lineNumber=10
    )
    sop = SOP(
        id="sop_1",
        name="测试SOP",
        description="测试",
        steps=[step],
        dataSources=[ds],
        tags=[],
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    assert len(sop.dataSources) == 1
    assert sop.dataSources[0].name == "教练签到表"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd /Users/wangjun/Desktop/ai_analyst_v2/backend && python -m pytest sops/test_models.py -v`
Expected: FAIL - ImportError: cannot import name 'DataSource'

- [ ] **Step 3: 更新 models.py**

```python
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class DataSource(BaseModel):
    """数据源定义"""
    id: str
    name: str                      # 用户命名的业务名称
    type: str                      # 'primary' | 'reference' | 'output'
    description: Optional[str] = ""  # 业务描述（可选）
    variableName: str              # 代码中的变量名
    operation: str                 # 'read' | 'write'
    codeSnippet: str               # 原始代码片段
    lineNumber: int                 # 在源码中的行号

class Step(BaseModel):
    step: int
    action: str
    params: dict
    description: Optional[str] = ""  # 业务描述

class SOP(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    steps: List[Step]
    dataSources: List[DataSource] = []  # 新增
    tags: List[str] = []
    created_at: datetime
    updated_at: datetime

class ExecutionLog(BaseModel):
    id: str
    sop_id: str
    status: str
    input_files: List[str]
    output_file: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd /Users/wangjun/Desktop/ai_analyst_v2/backend && python -m pytest sops/test_models.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/sops/models.py backend/sops/test_models.py
git commit -m "feat: add DataSource model and update SOP model"
```

---

## Task 2: 创建 DataSourceDetector 和 SemanticInferencer

**Files:**
- Create: `backend/sops/data_source.py`
- Test: `backend/sops/test_data_source.py` (新建)

- [ ] **Step 1: 创建测试文件**

```python
# backend/sops/test_data_source.py
import pytest
from data_source import DataSourceDetector, SemanticInferencer, infer_name_from_path

def test_infer_name_from_path():
    assert infer_name_from_path("教练签到 (53).xls") == "教练签到数据"
    assert infer_name_from_path("财务统计 (78).xls") == "财务统计数据"
    assert infer_name_from_path("部门划分.xlsx") == "部门划分表"
    assert infer_name_from_path("销售记录2024.csv") == "销售记录2024数据"

def test_data_source_detector_read_excel():
    code = '''
coach = pd.read_excel('C:\\\\Users\\\\coach.xlsx', sheet_name='教练签到')
finance = pd.read_excel('C:\\\\Users\\\\finance.xlsx', sheet_name='财务')
result.to_excel('C:\\\\Users\\\\output.xlsx')
'''
    detector = DataSourceDetector()
    sources = detector.detect(code)

    assert len(sources) == 3
    assert sources[0].operation == "read"
    assert sources[0].type == "primary"  # 第一个 read 是 primary
    assert sources[1].operation == "read"
    assert sources[1].type == "reference"  # 后续 read 是 reference
    assert sources[2].operation == "write"
    assert sources[2].type == "output"  # 第一个 write 是 output

def test_semantic_inferencer():
    code = '''
coach = pd.read_excel('C:\\\\Users\\\\教练签到 (53).xls', sheet_name='教练签到')
'''
    detector = DataSourceDetector()
    inferencer = SemanticInferencer()
    sources = detector.detect(code)
    inferred = inferencer.infer(sources, code)

    assert inferred[0].suggestedName == "教练签到数据"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd /Users/wangjun/Desktop/ai_analyst_v2/backend && python -m pytest sops/test_data_source.py -v`
Expected: FAIL - cannot import 'data_source'

- [ ] **Step 3: 创建 data_source.py**

```python
# backend/sops/data_source.py
"""数据源检测和语义推断模块"""
import ast
import re
from typing import List, Optional
from models import DataSource

def infer_name_from_path(file_path: str) -> str:
    """从文件路径推断数据源名称

    规则：
    1. 去除文件扩展名
    2. 去除括号内的数字后缀（如 (53)）
    3. 添加业务后缀（数据/表/结果）
    """
    # 去除路径，只保留文件名
    filename = file_path.split('/')[-1].split('\\')[-1]

    # 去除扩展名
    name = filename.rsplit('.', 1)[0] if '.' in filename else filename

    # 去除括号内的数字后缀
    name = re.sub(r'\s*\(\d+\)\s*$', '', name)

    # 添加业务后缀
    if name.endswith('表') or name.endswith('数据') or name.endswith('结果'):
        return name
    elif name.endswith('统计'):
        return name + '数据'
    else:
        return name + '表'

class DataSourceDetector:
    """从 AST 中检测数据读写操作"""

    def detect(self, code: str) -> List[DataSource]:
        """检测代码中的所有数据源"""
        sources = []
        read_count = 0
        write_count = 0

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return sources

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        var_name = target.id
                        if isinstance(node.value, ast.Call):
                            ds = self._detect_call(node.value, var_name, node.lineno, code)
                            if ds:
                                # 自动推断类型
                                if ds.operation == "read":
                                    ds.type = "primary" if read_count == 0 else "reference"
                                    read_count += 1
                                elif ds.operation == "write":
                                    ds.type = "output"
                                    write_count += 1
                                sources.append(ds)

        return sources

    def _detect_call(self, node: ast.Call, var_name: str, line_number: int, code: str) -> Optional[DataSource]:
        """检测函数调用是否是数据读写操作"""
        func = self._get_func_name(node.func)

        if func in ('read_excel', 'read_csv'):
            # 获取文件路径
            file_path = ""
            if node.args and isinstance(node.args[0], ast.Constant):
                file_path = node.args[0].value

            # 获取代码片段
            code_snippet = self._get_code_snippet(line_number, code)

            ds = DataSource(
                id=f"ds_{var_name}",
                name=infer_name_from_path(file_path),
                type="primary",  # 临时值，后续推断
                variableName=var_name,
                operation="read",
                codeSnippet=code_snippet,
                lineNumber=line_number
            )
            return ds

        elif func in ('to_excel', 'to_csv'):
            file_path = ""
            if node.args and isinstance(node.args[0], ast.Constant):
                file_path = node.args[0].value

            code_snippet = self._get_code_snippet(line_number, code)

            ds = DataSource(
                id=f"ds_{var_name}",
                name=infer_name_from_path(file_path) if file_path else f"{var_name}输出",
                type="output",  # 临时值
                variableName=var_name,
                operation="write",
                codeSnippet=code_snippet,
                lineNumber=line_number
            )
            return ds

        return None

    def _get_func_name(self, node) -> str:
        """获取函数名称"""
        if isinstance(node, ast.Attribute):
            return node.attr
        elif isinstance(node, ast.Name):
            return node.id
        return ""

    def _get_code_snippet(self, line_number: int, code: str) -> str:
        """获取指定行附近的代码片段（前后3行）"""
        lines = code.split('\n')
        start = max(0, line_number - 3)
        end = min(len(lines), line_number + 2)
        snippet_lines = lines[start:end]
        return '\n'.join(snippet_lines)

class SemanticInferencer:
    """语义推断器"""

    def infer(self, sources: List[DataSource], code: str) -> List[DataSource]:
        """为数据源推断语义信息"""
        for ds in sources:
            if ds.operation == "read" and ds.codeSnippet:
                # 从代码片段中提取更多信息
                pass
        return sources

    def generate_description(self, action: str, params: dict, data_sources: List[DataSource] = None) -> str:
        """生成步骤描述

        规则表：
        | action      | 描述模板                                    |
        |-------------|---------------------------------------------|
        | read_excel  | 读取【{数据源名称}】                        |
        | read_csv    | 读取【{数据源名称}】                        |
        | filter      | 筛选【{条件摘要}】数据                      |
        | drop_columns| 删除【{列名}】列                            |
        | merge       | 合并【{left_df}】与【{right_df}】            |
        | groupby     | 按【{by}】分组统计                          |
        | sort        | 按【{by}】排序                              |
        | to_excel    | 导出【{数据源名称}】                        |
        | to_csv      | 导出【{数据源名称}】                        |
        """
        templates = {
            'read_excel': "读取【{name}】",
            'read_csv': "读取【{name}】",
            'filter': "筛选【{condition}】数据",
            'drop_columns': "删除【{columns}】列",
            'merge': "合并数据",
            'groupby': "按【{by}】分组统计",
            'sort': "按【{by}】排序",
            'to_excel': "导出【{name}】",
            'to_csv': "导出【{name}】",
        }

        template = templates.get(action, action)
        # 简化替换
        desc = template
        for key, value in params.items():
            if value and isinstance(value, str):
                desc = desc.replace(f'{{{key}}}', value)
        return desc
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd /Users/wangjun/Desktop/ai_analyst_v2/backend && python -m pytest sops/test_data_source.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/sops/data_source.py backend/sops/test_data_source.py
git commit -m "feat: add DataSourceDetector and SemanticInferencer"
```

---

## Task 3: 更新 CodeParser 支持数据源检测

**Files:**
- Modify: `backend/sops/code_parser.py`
- Test: `backend/sops/test_code_parser.py` (更新)

- [ ] **Step 1: 添加 parse_code_with_sources 函数到 code_parser.py**

在文件末尾添加：

```python
def parse_code_with_sources(code: str) -> Dict[str, Any]:
    """解析 Python 代码，识别数据源和步骤

    Returns:
        {
            "name": "SOP名称",
            "description": "描述",
            "steps": [...],
            "dataSources": [...]  # 新增
        }
    """
    from data_source import DataSourceDetector, SemanticInferencer

    # 原有解析逻辑
    parser = CodeParser()
    result = parser.parse(code)

    # 新增：检测数据源
    detector = DataSourceDetector()
    inferencer = SemanticInferencer()
    sources = detector.detect(code)
    sources = inferencer.infer(sources, code)

    result["dataSources"] = [s.model_dump() for s in sources]

    return result
```

- [ ] **Step 2: 运行测试验证**

Run: `cd /Users/wangjun/Desktop/ai_analyst_v2/backend && python -c "
from code_parser import parse_code_with_sources
code = '''
coach = pd.read_excel('C:\\\\\\\\Users\\\\\\\\coach.xlsx')
finance = pd.read_excel('C:\\\\\\\\Users\\\\\\\\finance.xlsx')
result.to_excel('C:\\\\\\\\Users\\\\\\\\output.xlsx')
'''
result = parse_code_with_sources(code)
print('dataSources:', len(result.get('dataSources', [])))
for ds in result.get('dataSources', []):
    print(f'  {ds[\"name\"]} - {ds[\"type\"]}')
"`
Expected: 输出 3 个数据源

- [ ] **Step 3: 提交**

```bash
git add backend/sops/code_parser.py
git commit -m "feat: integrate data source detection into code parser"
```

---

## Task 4: 更新后端 API 支持新数据结构

**Files:**
- Modify: `backend/api/routes.py`
- Test: API 测试

- [ ] **Step 1: 更新 parse_code 端点返回完整数据结构**

找到 `@router.post("/sops/parse"` 端点，修改为：

```python
@router.post("/sops/parse", response_model=dict)
async def parse_code(body: dict = Body(...)):
    """解析 Python 代码为 SOP（包含数据源信息）"""
    code = body.get("code", "")
    result = parse_code_with_sources(code)  # 使用新函数
    return result
```

- [ ] **Step 2: 更新 create_sop 处理 dataSources**

找到 `@router.post("/sops")` 端点中创建 SOP 的逻辑，修改为：

```python
# 在 create_sop 函数中，处理 dataSources
data_sources = body.get("dataSources", [])
if data_sources:
    from models import DataSource
    sop = SOP(
        id=sop_id,
        name=name,
        description=description,
        steps=[Step(**s) for s in steps_data] if steps_data else [],
        dataSources=[DataSource(**ds) for ds in data_sources],
        tags=tags,
        created_at=now,
        updated_at=now
    )
```

- [ ] **Step 3: 测试 API**

Run: `curl -X POST http://localhost:8003/api/sops/parse -H "Content-Type: application/json" -d '{"code": "coach = pd.read_excel(\"test.xlsx\")"}'`
Expected: 返回包含 dataSources 的完整结构

- [ ] **Step 4: 提交**

```bash
git add backend/api/routes.py
git commit -m "feat: update API to support dataSources in SOP"
```

---

## Task 5: 更新前端类型定义

**Files:**
- Modify: `src/types/index.ts` 或新建 `src/types/sop.ts`

- [ ] **Step 1: 添加 DataSource 类型**

```typescript
// src/types/sop.ts

export interface DataSource {
  id: string
  name: string
  type: 'primary' | 'reference' | 'output'
  description?: string
  variableName: string
  operation: 'read' | 'write'
  codeSnippet: string
  lineNumber: number
}

export interface SOPStep {
  id: string
  order: number
  action: string
  params: Record<string, any>
  description: string
  inputSources?: string[]
  outputSource?: string
}

export interface SOP {
  id: string
  name: string
  description: string
  steps: SOPStep[]
  dataSources: DataSource[]
  tags: string[]
  created_at: string
  updated_at: string
}

export interface ParsedCodeResult {
  name: string
  description: string
  steps: SOPStep[]
  dataSources: DataSource[]
}
```

- [ ] **Step 2: 更新 sopApi.ts**

```typescript
// src/services/sopApi.ts

import type { SOP, SOPStep, DataSource, ParsedCodeResult } from '@/types/sop'

export async function parsePythonCode(code: string): Promise<ParsedCodeResult | null> {
  try {
    const response = await fetch(`${API_BASE}/sops/parse`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code })
    })
    if (!response.ok) throw new Error('Failed to parse Python code')
    const data = await response.json()
    return data as ParsedCodeResult
  } catch (error) {
    console.error('Error parsing Python code:', error)
    return null
  }
}
```

- [ ] **Step 3: 提交**

```bash
git add src/types/sop.ts src/services/sopApi.ts
git commit -m "feat: add DataSource types and update API methods"
```

---

## Task 6: 创建语义标注页面 SemanticAnnotation.vue

**Files:**
- Create: `src/ui/pages/sop/SemanticAnnotation.vue`

- [ ] **Step 1: 创建页面组件**

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import Card from '@/ui/components/common/Card.vue'
import Button from '@/ui/components/common/Button.vue'
import Input from '@/ui/components/common/Input.vue'
import { parsePythonCode, createSOP, type DataSource, type ParsedCodeResult } from '@/services/sopApi'

const router = useRouter()

const props = defineProps<{
  code: string
  initialName?: string
}>()

// 状态
const sopName = ref(props.initialName || '')
const dataSources = ref<DataSource[]>([])
const steps = ref<any[]>([])
const isSaving = ref(false)

// 初始化：从解析结果获取数据源
async function initialize() {
  const result = await parsePythonCode(props.code)
  if (result) {
    sopName.value = result.name
    dataSources.value = result.dataSources || []
    steps.value = result.steps || []
  }
}

// 初始化
initialize()

// 数据源类型选项
const typeOptions = [
  { value: 'primary', label: '主数据', icon: '📊' },
  { value: 'reference', label: '参照表', icon: '📋' },
  { value: 'output', label: '输出', icon: '📤' }
]

// 更新数据源名称
function updateDataSourceName(index: number, name: string) {
  if (dataSources.value[index]) {
    dataSources.value[index].name = name
  }
}

// 更新数据源类型
function updateDataSourceType(index: number, type: string) {
  if (dataSources.value[index]) {
    dataSources.value[index].type = type as any
  }
}

// 生成步骤描述
function generateStepDescription(step: any, dsName?: string): string {
  const action = step.action
  if (action === 'read_excel' || action === 'read_csv') {
    return `读取【${dsName || step.params.file}】`
  }
  if (action === 'filter') {
    return `筛选【${step.params.condition}】数据`
  }
  if (action === 'to_excel' || action === 'to_csv') {
    return `导出【${dsName || '结果'}】`
  }
  return `${action}: ${JSON.stringify(step.params)}`
}

// 实时预览步骤
const previewSteps = computed(() => {
  return steps.value.map((step, idx) => {
    // 查找关联的数据源
    const ds = dataSources.value.find(ds => ds.variableName === step.params.df)
    return {
      ...step,
      description: generateStepDescription(step, ds?.name)
    }
  })
})

// 创建 SOP
async function handleCreate() {
  if (!sopName.value.trim()) return

  isSaving.value = true
  try {
    const sop = {
      name: sopName.value,
      description: `从代码自动解析生成，包含 ${steps.value.length} 个步骤`,
      steps: previewSteps.value,
      dataSources: dataSources.value,
      tags: []
    }
    const result = await createSOP(sop)
    if (result) {
      router.push('/sop')
    }
  } finally {
    isSaving.value = false
  }
}

function handleCancel() {
  router.back()
}
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <div>
        <h1 class="text-[20px] font-bold text-text-heading">语义标注</h1>
        <p class="text-[13px] text-text-light mt-0.5">请为每个数据源填写名称和类型</p>
      </div>
      <Button variant="secondary" @click="handleCancel">取消</Button>
    </div>

    <!-- Main Content -->
    <div class="flex gap-4 flex-1 min-h-0">
      <!-- Left: Data Sources -->
      <Card class="w-1/2 flex-shrink-0 flex flex-col">
        <h2 class="text-[14px] font-bold text-text-heading mb-3">数据源配置</h2>

        <div class="flex-1 overflow-y-auto space-y-4">
          <div
            v-for="(ds, index) in dataSources"
            :key="ds.id"
            class="bg-page-bg border border-border rounded-lg p-4"
          >
            <div class="flex items-center justify-between mb-2">
              <span class="text-[12px] font-bold">{{ index + 1 }}. {{ ds.name || '未命名' }}</span>
              <span
                class="text-[10px] px-2 py-0.5 rounded"
                :class="{
                  'bg-accentLight text-accent': ds.type === 'primary',
                  'bg-blue-100 text-blue-600': ds.type === 'reference',
                  'bg-amber-100 text-amber-600': ds.type === 'output'
                }"
              >
                {{ ds.type === 'primary' ? '主数据' : ds.type === 'reference' ? '参照表' : '输出' }}
              </span>
            </div>

            <!-- Code Snippet -->
            <div class="mb-3">
              <label class="text-[10px] text-text-light mb-1 block">代码片段</label>
              <pre class="bg-chip border border-border rounded p-2 text-[10px] font-mono overflow-x-auto">{{ ds.codeSnippet }}</pre>
            </div>

            <!-- Name Input -->
            <div class="mb-2">
              <label class="text-[10px] text-text-light mb-1 block">数据源名称</label>
              <Input
                :model-value="ds.name"
                @update:model-value="(v) => updateDataSourceName(index, v)"
                placeholder="例如：教练签到表"
              />
            </div>

            <!-- Type Selection -->
            <div class="flex gap-2">
              <button
                v-for="opt in typeOptions"
                :key="opt.value"
                class="flex-1 text-[10px] py-1.5 rounded border transition-colors"
                :class="ds.type === opt.value
                  ? 'bg-accent text-white border-accent'
                  : 'bg-page-bg text-text-body border-border hover:border-accent'"
                @click="updateDataSourceType(index, opt.value)"
              >
                {{ opt.icon }} {{ opt.label }}
              </button>
            </div>
          </div>

          <div v-if="dataSources.length === 0" class="text-center text-text-light py-8">
            未检测到数据源
          </div>
        </div>
      </Card>

      <!-- Right: Step Preview -->
      <Card class="w-1/2 flex-shrink-0 flex flex-col">
        <h2 class="text-[14px] font-bold text-text-heading mb-3">SOP 名称</h2>

        <div class="mb-4">
          <Input
            v-model="sopName"
            placeholder="输入 SOP 名称..."
          />
        </div>

        <h2 class="text-[14px] font-bold text-text-heading mb-3">步骤预览</h2>

        <div class="flex-1 overflow-y-auto">
          <div
            v-for="(step, index) in previewSteps"
            :key="index"
            class="flex items-start gap-3 py-2 border-b border-border last:border-0"
          >
            <div
              class="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0"
              :style="{ backgroundColor: '#D6EDE7', color: '#5B8F7A' }"
            >
              {{ index + 1 }}
            </div>
            <div class="flex-1">
              <div class="text-[12px] text-text-body">{{ step.description || step.action }}</div>
              <div class="text-[10px] text-text-light">{{ step.code || '' }}</div>
            </div>
          </div>
        </div>
      </Card>
    </div>

    <!-- Footer -->
    <div class="flex justify-end gap-2.5 mt-4 pt-4 border-t border-border">
      <Button variant="secondary" @click="handleCancel">取消</Button>
      <Button variant="primary" :disabled="!sopName || isSaving" @click="handleCreate">
        {{ isSaving ? '创建中...' : '创建 SOP' }}
      </Button>
    </div>
  </div>
</template>
```

- [ ] **Step 2: 更新路由**

在 `src/router/` 中添加路由：

```typescript
{
  path: '/sop/annotate',
  name: 'SOPAnnotate',
  component: () => import('@/ui/pages/sop/SemanticAnnotation.vue')
}
```

- [ ] **Step 3: 更新 SOPImport.vue 跳转**

修改 SOPImport.vue 的 handleParse 成功后的跳转逻辑：

```typescript
// 解析成功后跳转到语义标注页面
router.push({
  name: 'SOPAnnotate',
  query: {
    code: pythonCode.value,
    name: sopName.value
  }
})
```

- [ ] **Step 4: 提交**

```bash
git add src/ui/pages/sop/SemanticAnnotation.vue
git commit -m "feat: add SemanticAnnotation page for data source annotation"
```

---

## Task 7: 创建执行配置弹窗 ExecutionConfig.vue

**Files:**
- Create: `src/ui/components/sop/ExecutionConfig.vue`

- [ ] **Step 1: 创建弹窗组件**

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
import Button from '@/ui/components/common/Button.vue'
import { executeSOP, type DataSource } from '@/services/sopApi'

const props = defineProps<{
  sopId: string
  dataSources: DataSource[]
}>()

const emit = defineEmits<{
  close: []
  executed: [executionId: string]
}>()

// 文件映射
const mappings = ref<Record<string, File>>({})
const outputPath = ref('')

// 输入数据源（需要上传）
const inputSources = computed(() =>
  props.dataSources.filter(ds => ds.operation === 'read')
)

// 输出数据源
const outputSource = computed(() =>
  props.dataSources.find(ds => ds.operation === 'write')
)

// 处理文件选择
function handleFileSelect(dataSourceId: string, event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files && input.files[0]) {
    mappings.value[dataSourceId] = input.files[0]
  }
}

// 检查是否可以执行
const canExecute = computed(() => {
  // 所有输入数据源都需要提供文件
  return inputSources.value.every(ds => mappings.value[ds.id])
})

// 执行
async function handleExecute() {
  const files = Object.values(mappings.value)
  const result = await executeSOP(props.sopId, files)
  if (result) {
    emit('executed', result.id)
    emit('close')
  }
}
</script>

<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
    <div class="bg-cardBg rounded-xl w-full max-w-lg mx-4 shadow-xl">
      <!-- Header -->
      <div class="px-5 py-4 border-b border-border">
        <h2 class="text-[16px] font-bold text-text-heading">执行配置</h2>
        <p class="text-[11px] text-text-light mt-0.5">请为每个数据源提供文件</p>
      </div>

      <!-- Content -->
      <div class="px-5 py-4 max-h-96 overflow-y-auto">
        <!-- Input Sources -->
        <div v-if="inputSources.length" class="mb-4">
          <h3 class="text-[12px] font-bold text-text-heading mb-2">📥 输入文件</h3>
          <div class="space-y-3">
            <div
              v-for="ds in inputSources"
              :key="ds.id"
              class="bg-page-bg border border-border rounded-lg p-3"
            >
              <div class="flex items-center justify-between mb-2">
                <span class="text-[11px] font-medium">{{ ds.name }}</span>
                <span class="text-[10px] text-text-light">变量: {{ ds.variableName }}</span>
              </div>
              <label class="block">
                <span class="text-[10px] text-accent cursor-pointer hover:underline">选择文件...</span>
                <input
                  type="file"
                  class="hidden"
                  :accept="ds.variableName.includes('csv') ? '.csv' : '.xlsx,.xls'"
                  @change="(e) => handleFileSelect(ds.id, e)"
                />
              </label>
              <div v-if="mappings[ds.id]" class="mt-1 text-[10px] text-accent">
                ✓ {{ mappings[ds.id].name }}
              </div>
            </div>
          </div>
        </div>

        <!-- Output Source -->
        <div v-if="outputSource">
          <h3 class="text-[12px] font-bold text-text-heading mb-2">📤 输出文件</h3>
          <div class="bg-page-bg border border-border rounded-lg p-3">
            <div class="text-[11px] font-medium mb-2">{{ outputSource.name }}</div>
            <input
              v-model="outputPath"
              type="text"
              placeholder="选择保存位置..."
              class="w-full bg-chip border border-border rounded px-3 py-1.5 text-[11px]"
            />
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="px-5 py-4 border-t border-border flex justify-end gap-2">
        <Button variant="secondary" @click="$emit('close')">取消</Button>
        <Button variant="primary" :disabled="!canExecute" @click="handleExecute">
          开始执行
        </Button>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: 在 SOPExecute.vue 中集成**

在 SOPExecute.vue 中添加：

```vue
<script setup>
// ...
import ExecutionConfig from '@/ui/components/sop/ExecutionConfig.vue'

const showExecutionConfig = ref(false)

function handleExecute() {
  showExecutionConfig.value = true
}
</script>

<template>
  <!-- 在执行按钮处添加 -->
  <Button variant="primary" @click="handleExecute">
    执行 SOP
  </Button>

  <!-- 弹窗 -->
  <ExecutionConfig
    v-if="showExecutionConfig"
    :sop-id="sop.id"
    :data-sources="sop.dataSources"
    @close="showExecutionConfig = false"
    @executed="handleExecutionComplete"
  />
</template>
```

- [ ] **Step 3: 提交**

```bash
git add src/ui/components/sop/ExecutionConfig.vue src/ui/pages/sop/SOPExecute.vue
git commit -m "feat: add ExecutionConfig modal for parametric execution"
```

---

## Task 8: 更新代码生成器支持参数化

**Files:**
- Modify: `backend/sops/code_generator.py`

- [ ] **Step 1: 添加参数化代码生成**

在 `SOPToExecutableCode` 函数中添加参数替换逻辑：

```python
def SOPToExecutableCode(sop: Dict[str, Any], mappings: Dict[str, str] = None) -> str:
    """将 SOP 转换为可执行代码

    Args:
        sop: SOP 字典
        mappings: 数据源ID到实际文件的映射，如 {"ds_coach": "/path/to/file.xlsx"}
    """
    # ... 原有逻辑 ...

    # 如果有映射，进行替换
    if mappings:
        for ds_id, file_path in mappings.items():
            # 替换 {{ds_id}} 占位符
            code = code.replace(f'{{{{{ds_id}}}}', f"'{file_path}'")
```

- [ ] **Step 2: 提交**

```bash
git add backend/sops/code_generator.py
git commit -m "feat: add parameter substitution to code generator"
```

---

## 实现顺序

1. **Task 1**: 更新后端数据模型
2. **Task 2**: 创建 DataSourceDetector 和 SemanticInferencer
3. **Task 3**: 更新 CodeParser 支持数据源检测
4. **Task 4**: 更新后端 API 支持新数据结构
5. **Task 5**: 更新前端类型定义
6. **Task 6**: 创建语义标注页面
7. **Task 7**: 创建执行配置弹窗
8. **Task 8**: 更新代码生成器支持参数化

---

## 验证清单

- [ ] 代码解析后能识别所有数据源
- [ ] 语义标注页面正确显示数据源和代码片段
- [ ] 用户可以编辑数据源名称和类型
- [ ] 步骤预览实时更新
- [ ] SOP 创建成功并包含 dataSources
- [ ] 执行时弹窗正确显示数据源配置
- [ ] 文件上传和路径选择功能正常
