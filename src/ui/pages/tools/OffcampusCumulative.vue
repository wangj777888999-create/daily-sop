<script setup lang="ts">
import { ref, computed } from 'vue'
import Button from '@/ui/components/common/Button.vue'
import Card from '@/ui/components/common/Card.vue'

type Step = 'select' | 'preview' | 'result'

interface FileSlot {
  key: string
  label: string
  required: boolean
  description?: string
}

const step = ref<Step>('select')
const loading = ref(false)
const errorMsg = ref('')

const fileSlots: FileSlot[] = [
  { key: 'report_1', label: '校外月度报表1', required: true },
  { key: 'report_2', label: '校外月度报表2', required: true },
  { key: 'report_3', label: '校外月度报表3', required: true },
]

const fileMap = ref<Record<string, File | null>>(
  Object.fromEntries(fileSlots.map(s => [s.key, null]))
)

const preview = ref<any>(null)
const processResult = ref<any>(null)
const history = ref<any[]>([])

const API = '/api/tools/offcampus-cumulative'

const requiredSlots = computed(() => fileSlots.filter(s => s.required))
const canPreview = computed(() => requiredSlots.value.every(s => fileMap.value[s.key] !== null))

function onFileSelect(event: Event, key: string) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  fileMap.value[key] = file
}

function buildFormData(): FormData {
  const fd = new FormData()
  for (const slot of fileSlots) {
    const f = fileMap.value[slot.key]
    if (f) fd.append(slot.key, f)
  }
  return fd
}

async function doPreview() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await fetch(`${API}/preview`, { method: 'POST', body: buildFormData() })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '预览失败')
    }
    preview.value = await res.json()
    step.value = 'preview'
  } catch (e: any) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

async function doProcess() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await fetch(`${API}/process`, { method: 'POST', body: buildFormData() })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '处理失败')
    }
    processResult.value = await res.json()
    step.value = 'result'
    loadHistory()
  } catch (e: any) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

function downloadResult() {
  if (!processResult.value) return
  window.open(`${API}/download/${processResult.value.id}`, '_blank')
}

function downloadHistory(id: number) {
  window.open(`${API}/download/${id}`, '_blank')
}

async function loadHistory() {
  try {
    const res = await fetch(`${API}/history`)
    history.value = await res.json()
  } catch {}
}

function reset() {
  step.value = 'select'
  preview.value = null
  processResult.value = null
  errorMsg.value = ''
  for (const slot of fileSlots) {
    fileMap.value[slot.key] = null
  }
}

function hasFile(key: string): boolean {
  return fileMap.value[key] !== null
}

function getFile(key: string): File | null {
  return fileMap.value[key]
}

function formatMoney(n: number) {
  return n ? n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '0.00'
}

function formatDate(d: string) {
  return d?.replace('T', ' ').slice(0, 19) || '-'
}

loadHistory()
</script>

<template>
  <div class="p-6 max-w-5xl mx-auto">
    <Card>
      <div class="flex flex-col gap-6">
        <!-- Header -->
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-bold text-text-heading">校外累积分析</h2>
            <p class="text-sm text-text-light mt-1">校外多校区跨月份累积数据分析与汇总报表</p>
          </div>
          <Button v-if="step !== 'select'" variant="secondary" size="small" @click="reset">
            重新选择
          </Button>
        </div>

        <!-- Error -->
        <div v-if="errorMsg" class="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
          {{ errorMsg }}
        </div>

        <!-- Step 1: Upload files -->
        <div v-if="step === 'select'" class="flex flex-col gap-4">
          <p class="text-sm text-text-light">请上传数据文件以开始累积分析</p>

          <div :class="`grid gap-4`" :style="`grid-template-columns: repeat(${Math.min(fileSlots.length, 3)}, 1fr);`">
            <label
              v-for="slot in fileSlots"
              :key="slot.key"
              class="border border-dashed border-border rounded-xl p-5 text-center cursor-pointer hover:border-accent transition-colors"
            >
              <input type="file" accept=".xlsx,.xls" class="hidden" @change="onFileSelect($event, slot.key)" />
              <div v-if="!hasFile(slot.key)">
                <p class="text-xl mb-1">◈</p>
                <p class="text-sm font-medium text-text-heading">{{ slot.label }}</p>
                <p v-if="slot.required" class="text-xs text-red-400 mt-1">必需</p>
                <p v-else class="text-xs text-text-light mt-1">可选</p>
              </div>
              <div v-else>
                <p class="text-sm font-medium text-green-600">✓ {{ getFile(slot.key)!.name }}</p>
                <p class="text-xs text-text-light mt-1">{{ (getFile(slot.key)!.size / 1024).toFixed(1) }} KB</p>
              </div>
            </label>
          </div>

          <Button variant="primary" :loading="loading" :disabled="!canPreview" @click="doPreview">
            预览数据
          </Button>
        </div>

        <!-- Step 2: Preview -->
        <div v-if="step === 'preview' && preview" class="flex flex-col gap-4">
          <div class="grid grid-cols-4 gap-4 text-center">
            <div class="bg-page-bg rounded-lg p-3">
              <p class="text-2xl font-bold text-text-heading">{{ preview.total_records ?? '-' }}</p>
              <p class="text-xs text-text-light">总记录数</p>
            </div>
            <div class="bg-page-bg rounded-lg p-3">
              <p class="text-2xl font-bold text-text-heading">{{ preview.month_count ?? '-' }}</p>
              <p class="text-xs text-text-light">覆盖月份数</p>
            </div>
            <div class="bg-page-bg rounded-lg p-3">
              <p class="text-2xl font-bold text-text-heading">{{ preview.campus_count ?? '-' }}</p>
              <p class="text-xs text-text-light">涉及校区</p>
            </div>
            <div class="bg-page-bg rounded-lg p-3">
              <p class="text-2xl font-bold text-text-heading">{{ preview.coach_count ?? '-' }}</p>
              <p class="text-xs text-text-light">涉及教练</p>
            </div>
          </div>

          <!-- File status -->
          <div class="flex flex-wrap gap-2 text-xs">
            <span
              v-for="slot in fileSlots"
              :key="slot.key"
              :class="hasFile(slot.key) ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-500'"
              class="px-2 py-1 rounded"
            >
              {{ hasFile(slot.key) ? `${slot.label}: ${getFile(slot.key)!.name}` : `${slot.label}: 未上传` }}
            </span>
          </div>

          <div class="flex items-center gap-3">
            <Button variant="primary" :loading="loading" @click="doProcess">
              确认生成累积报表
            </Button>
            <Button variant="secondary" @click="step = 'select'">
              返回修改
            </Button>
          </div>
        </div>

        <!-- Step 3: Result -->
        <div v-if="step === 'result' && processResult" class="flex flex-col gap-4">
          <div class="bg-green-50 border border-green-200 rounded-lg px-4 py-3">
            <p class="text-sm text-green-700 font-medium">校外累积分析生成完成</p>
            <div class="grid grid-cols-4 gap-4 mt-2 text-center">
              <div>
                <p class="text-lg font-bold text-green-800">{{ processResult.summary?.month_count || 0 }}</p>
                <p class="text-xs text-green-600">月份数</p>
              </div>
              <div>
                <p class="text-lg font-bold text-green-800">{{ processResult.summary?.campus_count || 0 }}</p>
                <p class="text-xs text-green-600">校区数</p>
              </div>
              <div>
                <p class="text-lg font-bold text-green-800">{{ processResult.summary?.coach_count || 0 }}</p>
                <p class="text-xs text-green-600">教练数</p>
              </div>
              <div>
                <p class="text-lg font-bold text-green-800">{{ formatMoney(processResult.summary?.total_revenue) }}</p>
                <p class="text-xs text-green-600">累计营收</p>
              </div>
            </div>
            <div class="mt-2 flex flex-wrap gap-1">
              <span v-for="s in processResult.sheets" :key="s" class="text-xs bg-white border border-green-200 text-green-700 px-2 py-0.5 rounded">
                {{ s }}
              </span>
            </div>
          </div>

          <Button variant="primary" @click="downloadResult">
            下载校外累积分析 Excel
          </Button>
        </div>

        <!-- History -->
        <div v-if="history.length > 0" class="border-t border-border pt-4">
          <h3 class="text-sm font-medium text-text-heading mb-3">历史分析记录</h3>
          <div class="overflow-auto">
            <table class="w-full text-xs">
              <thead class="bg-page-bg">
                <tr>
                  <th class="px-3 py-2 text-left font-medium text-text-light">分析周期</th>
                  <th class="px-3 py-2 text-center font-medium text-text-light">月份数</th>
                  <th class="px-3 py-2 text-center font-medium text-text-light">校区数</th>
                  <th class="px-3 py-2 text-center font-medium text-text-light">教练数</th>
                  <th class="px-3 py-2 text-left font-medium text-text-light">生成时间</th>
                  <th class="px-3 py-2 text-center font-medium text-text-light">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="b in history" :key="b.id" class="border-t border-border hover:bg-page-bg">
                  <td class="px-3 py-2">{{ b.period || '-' }}</td>
                  <td class="px-3 py-2 text-center">{{ b.month_count }}</td>
                  <td class="px-3 py-2 text-center">{{ b.campus_count }}</td>
                  <td class="px-3 py-2 text-center">{{ b.coach_count }}</td>
                  <td class="px-3 py-2">{{ formatDate(b.created_at) }}</td>
                  <td class="px-3 py-2 text-center">
                    <button class="text-accent hover:underline" @click="downloadHistory(b.id)">下载</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Card>
  </div>
</template>
