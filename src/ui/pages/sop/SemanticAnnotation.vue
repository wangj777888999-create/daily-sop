<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import Card from '@/ui/components/common/Card.vue'
import Button from '@/ui/components/common/Button.vue'
import Input from '@/ui/components/common/Input.vue'
import { parsePythonCode, createSOP } from '@/services/sopApi'
import type { DataSource } from '@/services/sopApi'

const router = useRouter()
const route = useRoute()

// 状态
const sopName = ref((route.query.name as string) || '')
const dataSources = ref<DataSource[]>([])
const steps = ref<any[]>([])
const isSaving = ref(false)
const code = ref((route.query.code as string) || '')

// 初始化
async function initialize() {
  if (!code.value) {
    router.replace('/sop/import')
    return
  }
  const result = await parsePythonCode(code.value)
  if (result) {
    sopName.value = result.name || sopName.value
    dataSources.value = result.dataSources || []
    steps.value = result.steps || []
  }
}
initialize()

// 类型选项
const typeOptions = [
  { value: 'primary', label: '主数据', icon: '📊' },
  { value: 'reference', label: '参照表', icon: '📋' },
  { value: 'output', label: '输出', icon: '📤' }
]

// 更新数据源
function updateDataSourceName(index: number, name: string) {
  dataSources.value[index].name = name
}

function updateDataSourceType(index: number, type: string) {
  dataSources.value[index].type = type as any
}

// 生成步骤描述（简单版本）
function generateStepDescription(step: any): string {
  const action = step.action
  const params = step.params || {}

  if (action === 'read_excel' || action === 'read_csv') {
    // 查找关联的数据源
    const ds = dataSources.value.find(ds => ds.variableName === params.df)
    return `读取【${ds?.name || params.file || '数据源'}】`
  }
  if (action === 'filter') {
    return `筛选【${params.condition || ''}】数据`
  }
  if (action === 'merge') {
    return `合并数据`
  }
  if (action === 'sort') {
    return `按【${params.by || ''}】排序`
  }
  if (action === 'to_excel' || action === 'to_csv') {
    return `导出结果`
  }
  return action
}

// 预览步骤
const previewSteps = computed(() => {
  return steps.value.map((step, _idx) => ({
    ...step,
    description: generateStepDescription(step)
  }))
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
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <div>
        <h1 class="text-[20px] font-bold text-text-heading">语义标注</h1>
        <p class="text-[13px] text-text-light mt-0.5">请为每个数据源填写名称和类型</p>
      </div>
      <Button variant="secondary" @click="router.back()">取消</Button>
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
              style="background-color: #D6EDE7; color: #5B8F7A"
            >
              {{ index + 1 }}
            </div>
            <div class="flex-1">
              <div class="text-[12px] text-text-body">{{ step.description }}</div>
              <div class="text-[10px] text-text-light">{{ step.code || '' }}</div>
            </div>
          </div>
        </div>
      </Card>
    </div>

    <!-- Footer -->
    <div class="flex justify-end gap-2.5 mt-4 pt-4 border-t border-border">
      <Button variant="secondary" @click="router.back()">取消</Button>
      <Button variant="primary" :disabled="!sopName || isSaving" @click="handleCreate">
        {{ isSaving ? '创建中...' : '创建 SOP' }}
      </Button>
    </div>
  </div>
</template>
