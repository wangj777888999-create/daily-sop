<script setup lang="ts">
import { ref, computed } from 'vue'
import Button from '@/ui/components/common/Button.vue'
import Card from '@/ui/components/common/Card.vue'

type Step = 'upload' | 'preview' | 'result'

const step = ref<Step>('upload')
const coachFile = ref<File | null>(null)
const financeFile = ref<File | null>(null)
const checkDate = ref(new Date().toISOString().slice(0, 10))
const loading = ref(false)
const errorMsg = ref('')

// Preview data
const preview = ref<any>(null)

// Result data
const processResult = ref<any>(null)

// History
const history = ref<any[]>([])

const API = '/api/tools/daily-checkin'

function onFileSelect(event: Event, type: 'coach' | 'finance') {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  if (type === 'coach') coachFile.value = file
  else financeFile.value = file
}

const canPreview = computed(() => coachFile.value && financeFile.value)

async function doPreview() {
  if (!canPreview.value) return
  loading.value = true
  errorMsg.value = ''
  try {
    const fd = new FormData()
    fd.append('coach_file', coachFile.value!)
    fd.append('finance_file', financeFile.value!)
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
  if (!canPreview.value) return
  loading.value = true
  errorMsg.value = ''
  try {
    const fd = new FormData()
    fd.append('coach_file', coachFile.value!)
    fd.append('finance_file', financeFile.value!)
    fd.append('check_date', checkDate.value)
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
  window.open(`${API}/download/${processResult.value.batch_id}`, '_blank')
}

function downloadHistory(id: number) {
  window.open(`${API}/download/${id}`, '_blank')
}

async function deleteHistory(id: number) {
  if (!confirm('确定删除该批次？关联的签到数据和生成文件将一并删除，此操作不可恢复。')) return
  try {
    const res = await fetch(`${API}/batch/${id}`, { method: 'DELETE' })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '删除失败')
    }
    loadHistory()
  } catch (e: any) {
    errorMsg.value = e.message
  }
}

async function loadHistory() {
  try {
    const res = await fetch(`${API}/history`)
    history.value = await res.json()
  } catch {}
}

function reset() {
  step.value = 'upload'
  coachFile.value = null
  financeFile.value = null
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
            <h2 class="text-lg font-bold text-text-heading">每日教练签到分析</h2>
            <p class="text-sm text-text-light mt-1">上传签到+财务 Excel，自动处理并存库</p>
          </div>
          <Button v-if="step !== 'upload'" variant="secondary" size="small" @click="reset">
            重新上传
          </Button>
        </div>

        <!-- Error -->
        <div v-if="errorMsg" class="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
          {{ errorMsg }}
        </div>

        <!-- Step 1: Upload -->
        <div v-if="step === 'upload'" class="flex flex-col gap-4">
          <div class="grid grid-cols-2 gap-4">
            <!-- Coach file -->
            <label class="border border-dashed border-border rounded-xl p-6 text-center cursor-pointer hover:border-accent transition-colors">
              <input type="file" accept=".xlsx,.xls" class="hidden" @change="onFileSelect($event, 'coach')" />
              <div v-if="!coachFile">
                <p class="text-2xl mb-2">◈</p>
                <p class="text-sm font-medium text-text-heading">教练签到文件</p>
                <p class="text-xs text-text-light mt-1">点击选择 .xls/.xlsx 文件</p>
              </div>
              <div v-else>
                <p class="text-sm font-medium text-green-600">✓ {{ coachFile.name }}</p>
                <p class="text-xs text-text-light mt-1">{{ (coachFile.size / 1024).toFixed(1) }} KB</p>
              </div>
            </label>

            <!-- Finance file -->
            <label class="border border-dashed border-border rounded-xl p-6 text-center cursor-pointer hover:border-accent transition-colors">
              <input type="file" accept=".xlsx,.xls" class="hidden" @change="onFileSelect($event, 'finance')" />
              <div v-if="!financeFile">
                <p class="text-2xl mb-2">◈</p>
                <p class="text-sm font-medium text-text-heading">财务统计文件</p>
                <p class="text-xs text-text-light mt-1">点击选择 .xls/.xlsx 文件</p>
              </div>
              <div v-else>
                <p class="text-sm font-medium text-green-600">✓ {{ financeFile.name }}</p>
                <p class="text-xs text-text-light mt-1">{{ (financeFile.size / 1024).toFixed(1) }} KB</p>
              </div>
            </label>
          </div>

          <div class="flex items-center gap-3">
            <label class="text-sm text-text-body">签到日期：</label>
            <input v-model="checkDate" type="date" class="border border-border rounded-lg px-3 py-1.5 text-sm" />
          </div>

          <Button variant="primary" :disabled="!canPreview" :loading="loading" @click="doPreview">
            预览数据
          </Button>
        </div>

        <!-- Step 2: Preview -->
        <div v-if="step === 'preview' && preview" class="flex flex-col gap-4">
          <div class="grid grid-cols-3 gap-4 text-center">
            <div class="bg-page-bg rounded-lg p-3">
              <p class="text-2xl font-bold text-text-heading">{{ preview.coach_total }}</p>
              <p class="text-xs text-text-light">教练签到行数</p>
            </div>
            <div class="bg-page-bg rounded-lg p-3">
              <p class="text-2xl font-bold text-text-heading">{{ preview.finance_total }}</p>
              <p class="text-xs text-text-light">财务数据行数</p>
            </div>
            <div class="bg-page-bg rounded-lg p-3">
              <p class="text-2xl font-bold text-text-heading">{{ preview.coach_columns?.length || 0 }}</p>
              <p class="text-xs text-text-light">教练签到列数</p>
            </div>
          </div>

          <div>
            <h3 class="text-sm font-medium text-text-heading mb-2">教练签到预览（前 20 行）</h3>
            <div class="overflow-auto max-h-64 border border-border rounded-lg">
              <table class="w-full text-xs">
                <thead class="bg-page-bg sticky top-0">
                  <tr>
                    <th v-for="col in preview.coach_columns?.slice(0, 8)" :key="col" class="px-2 py-1.5 text-left font-medium text-text-light whitespace-nowrap">
                      {{ col }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, i) in preview.coach_rows?.slice(0, 20)" :key="i" class="border-t border-border hover:bg-page-bg">
                    <td v-for="col in preview.coach_columns?.slice(0, 8)" :key="col" class="px-2 py-1 whitespace-nowrap">
                      {{ row[col] ?? '' }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="flex items-center gap-3">
            <Button variant="primary" :loading="loading" @click="doProcess">
              确认处理
            </Button>
            <Button variant="secondary" @click="step = 'upload'">
              返回修改
            </Button>
          </div>
        </div>

        <!-- Step 3: Result -->
        <div v-if="step === 'result' && processResult" class="flex flex-col gap-4">
          <div class="bg-green-50 border border-green-200 rounded-lg px-4 py-3">
            <p class="text-sm text-green-700 font-medium">处理完成</p>
            <div class="grid grid-cols-4 gap-4 mt-2 text-center">
              <div>
                <p class="text-lg font-bold text-green-800">{{ processResult.record_count }}</p>
                <p class="text-xs text-green-600">写入记录数</p>
              </div>
              <div>
                <p class="text-lg font-bold text-green-800">{{ processResult.summary?.departments }}</p>
                <p class="text-xs text-green-600">涉及部门</p>
              </div>
              <div>
                <p class="text-lg font-bold text-green-800">{{ processResult.summary?.schools }}</p>
                <p class="text-xs text-green-600">涉及学校</p>
              </div>
              <div>
                <p class="text-lg font-bold text-green-800">{{ processResult.summary?.coaches }}</p>
                <p class="text-xs text-green-600">涉及教练</p>
              </div>
            </div>
          </div>

          <Button variant="primary" @click="downloadResult">
            下载格式化 Excel
          </Button>
        </div>

        <!-- History -->
        <div v-if="history.length > 0" class="border-t border-border pt-4">
          <h3 class="text-sm font-medium text-text-heading mb-3">历史处理记录</h3>
          <div class="overflow-auto">
            <table class="w-full text-xs">
              <thead class="bg-page-bg">
                <tr>
                  <th class="px-3 py-2 text-left font-medium text-text-light">批次日期</th>
                  <th class="px-3 py-2 text-left font-medium text-text-light">教练签到文件</th>
                  <th class="px-3 py-2 text-left font-medium text-text-light">财务文件</th>
                  <th class="px-3 py-2 text-left font-medium text-text-light">生成文件</th>
                  <th class="px-3 py-2 text-center font-medium text-text-light">记录数</th>
                  <th class="px-3 py-2 text-left font-medium text-text-light">处理时间</th>
                  <th class="px-3 py-2 text-center font-medium text-text-light">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="b in history" :key="b.id" class="border-t border-border hover:bg-page-bg">
                  <td class="px-3 py-2">{{ b.batch_date }}</td>
                  <td class="px-3 py-2 truncate max-w-[200px]">{{ b.coach_file }}</td>
                  <td class="px-3 py-2 truncate max-w-[200px]">{{ b.finance_file }}</td>
                  <td class="px-3 py-2 truncate max-w-[200px]">{{ b.output_filename || '-' }}</td>
                  <td class="px-3 py-2 text-center">{{ b.record_count }}</td>
                  <td class="px-3 py-2">{{ formatDate(b.created_at) }}</td>
                  <td class="px-3 py-2 text-center">
                    <button class="text-accent hover:underline text-xs mr-2" @click="downloadHistory(b.id)">下载</button>
                    <button class="text-red-500 hover:underline text-xs" @click="deleteHistory(b.id)">删除</button>
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
