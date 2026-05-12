<script setup lang="ts">
import { ref } from 'vue'
import Button from '@/ui/components/common/Button.vue'
import Card from '@/ui/components/common/Card.vue'

type Step = 'select' | 'preview' | 'result'

const step = ref<Step>('select')
const year = ref(new Date().getFullYear())
const month = ref(new Date().getMonth() || 12) // 0→12（1月时取上年12月），其余月份正确对应上月
const financeFile = ref<File | null>(null)
const courseTypeFile = ref<File | null>(null)
const refundFile = ref<File | null>(null)
const loading = ref(false)
const errorMsg = ref('')

const preview = ref<any>(null)
const processResult = ref<any>(null)
const history = ref<any[]>([])

const API = '/api/tools/campus-monthly'

const monthOptions = Array.from({ length: 12 }, (_, i) => ({
  value: i + 1,
  label: `${i + 1}月`,
}))

function onFileSelect(event: Event, type: 'finance' | 'courseType' | 'refund') {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  if (type === 'finance') financeFile.value = file
  else if (type === 'courseType') courseTypeFile.value = file
  else refundFile.value = file
}

async function doPreview() {
  loading.value = true
  errorMsg.value = ''
  try {
    const fd = new FormData()
    fd.append('year', String(year.value))
    fd.append('month', String(month.value))
    const res = await fetch(`${API}/preview`, { method: 'POST', body: fd })
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
    const fd = new FormData()
    fd.append('year', String(year.value))
    fd.append('month', String(month.value))
    if (financeFile.value) fd.append('finance_file', financeFile.value)
    if (courseTypeFile.value) fd.append('course_type_file', courseTypeFile.value)
    if (refundFile.value) fd.append('refund_file', refundFile.value)
    const res = await fetch(`${API}/process`, { method: 'POST', body: fd })
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
            <h2 class="text-lg font-bold text-text-heading">校内月度分析</h2>
            <p class="text-sm text-text-light mt-1">基于签到累积数据，生成多维度月度报表</p>
          </div>
          <Button v-if="step !== 'select'" variant="secondary" size="small" @click="reset">
            重新选择
          </Button>
        </div>

        <!-- Error -->
        <div v-if="errorMsg" class="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
          {{ errorMsg }}
        </div>

        <!-- Step 1: Select month + upload files -->
        <div v-if="step === 'select'" class="flex flex-col gap-4">
          <!-- Month selector -->
          <div class="flex items-center gap-3">
            <label class="text-sm text-text-body font-medium">分析月份：</label>
            <select v-model.number="year" class="border border-border rounded-lg px-3 py-1.5 text-sm">
              <option :value="2026">2026年</option>
              <option :value="2025">2025年</option>
            </select>
            <select v-model.number="month" class="border border-border rounded-lg px-3 py-1.5 text-sm">
              <option v-for="m in monthOptions" :key="m.value" :value="m.value">{{ m.label }}</option>
            </select>
          </div>

          <!-- File uploads -->
          <div class="grid grid-cols-3 gap-4">
            <!-- Finance file (recommended) -->
            <label class="border border-dashed border-border rounded-xl p-5 text-center cursor-pointer hover:border-accent transition-colors">
              <input type="file" accept=".xlsx,.xls" class="hidden" @change="onFileSelect($event, 'finance')" />
              <div v-if="!financeFile">
                <p class="text-xl mb-1">◈</p>
                <p class="text-sm font-medium text-text-heading">财务统计明细</p>
                <p class="text-xs text-accent mt-1">推荐上传</p>
                <p class="text-xs text-text-light">生成校内分析 sheet</p>
              </div>
              <div v-else>
                <p class="text-sm font-medium text-green-600">✓ {{ financeFile.name }}</p>
                <p class="text-xs text-text-light mt-1">{{ (financeFile.size / 1024).toFixed(1) }} KB</p>
              </div>
            </label>

            <!-- Course type file (optional) -->
            <label class="border border-dashed border-border rounded-xl p-5 text-center cursor-pointer hover:border-accent transition-colors">
              <input type="file" accept=".xlsx,.xls" class="hidden" @change="onFileSelect($event, 'courseType')" />
              <div v-if="!courseTypeFile">
                <p class="text-xl mb-1">◈</p>
                <p class="text-sm font-medium text-text-heading">课程类型对照表</p>
                <p class="text-xs text-text-light mt-1">可选 · 生成类型分析</p>
              </div>
              <div v-else>
                <p class="text-sm font-medium text-green-600">✓ {{ courseTypeFile.name }}</p>
                <p class="text-xs text-text-light mt-1">{{ (courseTypeFile.size / 1024).toFixed(1) }} KB</p>
              </div>
            </label>

            <!-- Refund file (optional) -->
            <label class="border border-dashed border-border rounded-xl p-5 text-center cursor-pointer hover:border-accent transition-colors">
              <input type="file" accept=".xlsx,.xls" class="hidden" @change="onFileSelect($event, 'refund')" />
              <div v-if="!refundFile">
                <p class="text-xl mb-1">◈</p>
                <p class="text-sm font-medium text-text-heading">退款导出数据</p>
                <p class="text-xs text-text-light mt-1">可选 · 生成退款分析</p>
              </div>
              <div v-else>
                <p class="text-sm font-medium text-green-600">✓ {{ refundFile.name }}</p>
                <p class="text-xs text-text-light mt-1">{{ (refundFile.size / 1024).toFixed(1) }} KB</p>
              </div>
            </label>
          </div>

          <Button variant="primary" :loading="loading" @click="doPreview">
            预览数据
          </Button>
        </div>

        <!-- Step 2: Preview -->
        <div v-if="step === 'preview' && preview" class="flex flex-col gap-4">
          <div class="grid grid-cols-4 gap-4 text-center">
            <div class="bg-page-bg rounded-lg p-3">
              <p class="text-2xl font-bold text-text-heading">{{ preview.checkin_count }}</p>
              <p class="text-xs text-text-light">签到记录数</p>
            </div>
            <div class="bg-page-bg rounded-lg p-3">
              <p class="text-2xl font-bold text-text-heading">{{ preview.departments?.length || 0 }}</p>
              <p class="text-xs text-text-light">涉及部门</p>
            </div>
            <div class="bg-page-bg rounded-lg p-3">
              <p class="text-2xl font-bold text-text-heading">{{ preview.coaches?.length || 0 }}</p>
              <p class="text-xs text-text-light">涉及教练</p>
            </div>
            <div class="bg-page-bg rounded-lg p-3">
              <p class="text-2xl font-bold text-text-heading">{{ preview.schools?.length || 0 }}</p>
              <p class="text-xs text-text-light">涉及学校</p>
            </div>
          </div>

          <div v-if="preview.checkin_count === 0" class="bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3 text-sm text-yellow-700">
            该月暂无签到数据，请先使用「每日教练签到分析」工具积累数据。
          </div>

          <div v-else class="text-sm text-text-light">
            数据范围：{{ preview.date_range?.[0] }} ~ {{ preview.date_range?.[1] }}
          </div>

          <!-- Upload summary -->
          <div class="flex flex-wrap gap-2 text-xs">
            <span v-if="financeFile" class="bg-green-50 text-green-700 px-2 py-1 rounded">财务: {{ financeFile.name }}</span>
            <span v-if="courseTypeFile" class="bg-green-50 text-green-700 px-2 py-1 rounded">类型: {{ courseTypeFile.name }}</span>
            <span v-if="refundFile" class="bg-green-50 text-green-700 px-2 py-1 rounded">退款: {{ refundFile.name }}</span>
            <span v-if="!financeFile" class="bg-gray-100 text-gray-500 px-2 py-1 rounded">未上传财务文件 → 跳过校内分析</span>
          </div>

          <div class="flex items-center gap-3">
            <Button variant="primary" :loading="loading" @click="doProcess" :disabled="preview.checkin_count === 0">
              确认生成报表
            </Button>
            <Button variant="secondary" @click="step = 'select'">
              返回修改
            </Button>
          </div>
        </div>

        <!-- Step 3: Result -->
        <div v-if="step === 'result' && processResult" class="flex flex-col gap-4">
          <div class="bg-green-50 border border-green-200 rounded-lg px-4 py-3">
            <p class="text-sm text-green-700 font-medium">月度报表生成完成</p>
            <div class="grid grid-cols-3 gap-4 mt-2 text-center">
              <div>
                <p class="text-lg font-bold text-green-800">{{ processResult.record_count }}</p>
                <p class="text-xs text-green-600">签到记录数</p>
              </div>
              <div>
                <p class="text-lg font-bold text-green-800">{{ processResult.department_count }}</p>
                <p class="text-xs text-green-600">涉及部门</p>
              </div>
              <div>
                <p class="text-lg font-bold text-green-800">{{ processResult.coach_count }}</p>
                <p class="text-xs text-green-600">涉及教练</p>
              </div>
            </div>
            <div class="mt-2 flex flex-wrap gap-1">
              <span v-for="s in processResult.sheets" :key="s" class="text-xs bg-white border border-green-200 text-green-700 px-2 py-0.5 rounded">
                {{ s }}
              </span>
            </div>
          </div>

          <Button variant="primary" @click="downloadResult">
            下载月度分析 Excel
          </Button>
        </div>

        <!-- History -->
        <div v-if="history.length > 0" class="border-t border-border pt-4">
          <h3 class="text-sm font-medium text-text-heading mb-3">历史分析记录</h3>
          <div class="overflow-auto">
            <table class="w-full text-xs">
              <thead class="bg-page-bg">
                <tr>
                  <th class="px-3 py-2 text-left font-medium text-text-light">分析月份</th>
                  <th class="px-3 py-2 text-center font-medium text-text-light">记录数</th>
                  <th class="px-3 py-2 text-center font-medium text-text-light">部门数</th>
                  <th class="px-3 py-2 text-center font-medium text-text-light">教练数</th>
                  <th class="px-3 py-2 text-left font-medium text-text-light">生成时间</th>
                  <th class="px-3 py-2 text-center font-medium text-text-light">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="b in history" :key="b.id" class="border-t border-border hover:bg-page-bg">
                  <td class="px-3 py-2">{{ b.year }}年{{ b.month }}月</td>
                  <td class="px-3 py-2 text-center">{{ b.record_count }}</td>
                  <td class="px-3 py-2 text-center">{{ b.department_count }}</td>
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
