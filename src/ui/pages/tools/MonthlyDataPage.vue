<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Card from '@/ui/components/common/Card.vue'

interface FileStatus {
  uploaded: boolean
  label: string
  usage: string
  original_name?: string
  size?: number
  uploaded_at?: string
}

interface MonthlyStatus {
  year: number
  month: number
  files: Record<string, FileStatus>
}

const API = '/api/tools/monthly-data'

const year = ref(new Date().getMonth() === 0 ? new Date().getFullYear() - 1 : new Date().getFullYear())
const month = ref(new Date().getMonth() === 0 ? 12 : new Date().getMonth())
const status = ref<MonthlyStatus | null>(null)
const uploading = ref<Record<string, boolean>>({})
const errorMsg = ref('')

const FILE_DEFS = [
  { key: 'skjl',         accept: '.xlsx,.xls', required: true,  badge: '共用' },
  { key: 'finance',      accept: '.xlsx,.xls', required: true,  badge: '共用' },
  { key: 'refund',       accept: '.xlsx,.xls', required: false, badge: '校内' },
  { key: 'teaching_fee', accept: '.xlsx,.xls', required: false, badge: '校外' },
  { key: 'venue_fee',    accept: '.xlsx,.xls', required: false, badge: '校外' },
  { key: 'last_month',   accept: '.xlsx,.xls', required: false, badge: '可选' },
]

const uploadedCount = computed(() => {
  if (!status.value) return 0
  return Object.values(status.value.files).filter(f => f.uploaded).length
})

const monthOptions = Array.from({ length: 12 }, (_, i) => ({ value: i + 1, label: `${i + 1}月` }))

async function loadStatus() {
  errorMsg.value = ''
  try {
    const res = await fetch(`${API}/status/${year.value}/${month.value}`)
    if (!res.ok) throw new Error(await res.text())
    status.value = await res.json()
  } catch (e: any) {
    errorMsg.value = '加载状态失败：' + e.message
  }
}

async function handleUpload(event: Event, key: string) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  input.value = ''

  uploading.value = { ...uploading.value, [key]: true }
  errorMsg.value = ''
  try {
    const fd = new FormData()
    fd.append('year', String(year.value))
    fd.append('month', String(month.value))
    fd.append('file_key', key)
    fd.append('file', file)
    const res = await fetch(`${API}/upload`, { method: 'POST', body: fd })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '上传失败')
    }
    await loadStatus()
  } catch (e: any) {
    errorMsg.value = e.message
  } finally {
    uploading.value = { ...uploading.value, [key]: false }
  }
}

async function handleDelete(key: string, label: string) {
  if (!confirm(`确认删除「${label}」？`)) return
  errorMsg.value = ''
  try {
    const res = await fetch(`${API}/${year.value}/${month.value}/${key}`, { method: 'DELETE' })
    if (!res.ok) throw new Error('删除失败')
    await loadStatus()
  } catch (e: any) {
    errorMsg.value = e.message
  }
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function formatDate(s: string) {
  return s?.replace('T', ' ').slice(0, 16) || ''
}

function onMonthChange() {
  status.value = null
  loadStatus()
}

onMounted(loadStatus)
</script>

<template>
  <div class="p-6 max-w-4xl mx-auto">
    <Card>
      <div class="flex flex-col gap-6">
        <!-- Header -->
        <div>
          <h2 class="text-lg font-bold text-text-heading">月度数据管理</h2>
          <p class="text-sm text-text-light mt-1">每月上传一次源数据，校内/校外分析工具自动读取，无需重复上传</p>
        </div>

        <!-- Error -->
        <div v-if="errorMsg" class="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
          {{ errorMsg }}
        </div>

        <!-- Month selector -->
        <div class="flex items-center gap-3">
          <label class="text-sm text-text-body font-medium">数据月份：</label>
          <select v-model.number="year" @change="onMonthChange" class="border border-border rounded-lg px-3 py-1.5 text-sm">
            <option :value="2026">2026年</option>
            <option :value="2025">2025年</option>
          </select>
          <select v-model.number="month" @change="onMonthChange" class="border border-border rounded-lg px-3 py-1.5 text-sm">
            <option v-for="m in monthOptions" :key="m.value" :value="m.value">{{ m.label }}</option>
          </select>
          <span class="ml-auto text-sm text-text-light">
            已上传
            <span :class="uploadedCount >= 4 ? 'text-green-600 font-bold' : 'text-text-heading font-bold'">
              {{ uploadedCount }}
            </span>
            / 6 个文件
          </span>
        </div>

        <!-- File grid -->
        <div v-if="status" class="grid grid-cols-3 gap-4">
          <div
            v-for="def in FILE_DEFS"
            :key="def.key"
            :class="[
              'rounded-xl border-2 p-4 flex flex-col gap-2 transition-colors',
              status.files[def.key]?.uploaded
                ? 'border-green-300 bg-green-50/40'
                : 'border-dashed border-border hover:border-accent'
            ]"
          >
            <div class="flex items-center justify-between">
              <span class="text-sm font-medium text-text-heading">{{ status.files[def.key]?.label }}</span>
              <span :class="[
                'text-xs px-1.5 py-0.5 rounded font-medium',
                def.badge === '共用' ? 'bg-accent/10 text-accent' :
                def.badge === '校外' ? 'bg-blue-50 text-blue-600' :
                def.badge === '校内' ? 'bg-orange-50 text-orange-600' :
                'bg-gray-100 text-gray-500'
              ]">{{ def.badge }}</span>
            </div>

            <p class="text-xs text-text-light leading-tight">{{ status.files[def.key]?.usage }}</p>

            <!-- Uploaded state -->
            <template v-if="status.files[def.key]?.uploaded">
              <div class="mt-auto">
                <p class="text-xs font-medium text-green-700 truncate">✓ {{ status.files[def.key]?.original_name }}</p>
                <p class="text-xs text-text-light">
                  {{ formatSize(status.files[def.key]?.size || 0) }} · {{ formatDate(status.files[def.key]?.uploaded_at || '') }}
                </p>
                <div class="flex gap-2 mt-2">
                  <label class="flex-1 text-center text-xs text-accent cursor-pointer hover:underline">
                    <input type="file" :accept="def.accept" class="hidden" @change="handleUpload($event, def.key)" />
                    重新上传
                  </label>
                  <button
                    class="flex-1 text-xs text-red-500 hover:underline"
                    @click="handleDelete(def.key, status!.files[def.key]?.label)"
                  >删除</button>
                </div>
              </div>
            </template>

            <!-- Not uploaded state -->
            <template v-else>
              <label class="mt-auto flex flex-col items-center justify-center py-3 cursor-pointer">
                <input type="file" :accept="def.accept" class="hidden" @change="handleUpload($event, def.key)" />
                <template v-if="uploading[def.key]">
                  <span class="text-xs text-text-light">上传中...</span>
                </template>
                <template v-else>
                  <span class="text-2xl text-border mb-1">+</span>
                  <span class="text-xs text-text-light">点击上传</span>
                  <span class="text-xs text-text-light opacity-60">{{ def.accept }}</span>
                </template>
              </label>
            </template>
          </div>
        </div>

        <div v-else class="text-center py-8 text-sm text-text-light">加载中...</div>

        <!-- Usage guide -->
        <div class="bg-page-bg rounded-xl p-4 text-sm">
          <p class="font-medium text-text-heading mb-2">文件用途说明</p>
          <div class="flex flex-col gap-1 text-xs text-text-body">
            <p><span class="font-medium">校内月报（文件模式）：</span>上课记录 + 财务统计明细 + 退款导出</p>
            <p><span class="font-medium">校外月报：</span>上课记录 + 财务统计明细 + 校外课时费 + 场地费（+ 上月报告）</p>
            <p><span class="font-medium">折扣率计算：</span>仅需上课记录</p>
            <p class="mt-1 text-text-light">上传后打开对应工具，顶部会显示「已找到存储数据」提示，点击即可直接分析。</p>
          </div>
        </div>
      </div>
    </Card>
  </div>
</template>
