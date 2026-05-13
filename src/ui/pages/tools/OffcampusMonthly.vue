<script setup lang="ts">
import { ref, computed } from 'vue'
import Button from '@/ui/components/common/Button.vue'
import Card from '@/ui/components/common/Card.vue'

type Step = 'select' | 'preview' | 'result'

const step = ref<Step>('select')
const skjlFile = ref<File | null>(null)
const xwksfFile = ref<File | null>(null)
const cwFile = ref<File | null>(null)
const cdfFile = ref<File | null>(null)
const lastMonthFile = ref<File | null>(null)
const loading = ref(false)
const errorMsg = ref('')

const preview = ref<any>(null)
const processResult = ref<any>(null)
const history = ref<any[]>([])

const API = '/api/tools/offcampus-monthly'

const canPreview = computed(() => skjlFile.value && xwksfFile.value && cwFile.value && cdfFile.value)

function onFileSelect(event: Event, type: 'skjl' | 'xwksf' | 'cw' | 'cdf' | 'lastMonth') {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  if (type === 'skjl') skjlFile.value = file
  else if (type === 'xwksf') xwksfFile.value = file
  else if (type === 'cw') cwFile.value = file
  else if (type === 'cdf') cdfFile.value = file
  else lastMonthFile.value = file
}

async function doPreview() {
  loading.value = true
  errorMsg.value = ''
  try {
    const fd = new FormData()
    fd.append('skjl_file', skjlFile.value!)
    fd.append('cw_file', cwFile.value!)
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
    fd.append('skjl_file', skjlFile.value!)
    fd.append('xwksf_file', xwksfFile.value!)
    fd.append('cw_file', cwFile.value!)
    fd.append('cdf_file', cdfFile.value!)
    if (lastMonthFile.value) fd.append('last_month_file', lastMonthFile.value)
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
            <h2 class="text-lg font-bold text-text-heading">校外月度分析</h2>
            <p class="text-sm text-text-light mt-1">校外校区场地/课时/营收综合分析，含环比对比</p>
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
          <p class="text-sm text-text-light">请上传 4 个必需文件 + 1 个可选文件（上月分析，用于环比计算）</p>

          <!-- Row 1: 3 required files -->
          <div class="grid grid-cols-3 gap-4">
            <!-- 上课记录 -->
            <label class="border border-dashed border-border rounded-xl p-5 text-center cursor-pointer hover:border-accent transition-colors">
              <input type="file" accept=".xlsx,.xls" class="hidden" @change="onFileSelect($event, 'skjl')" />
              <div v-if="!skjlFile">
                <p class="text-xl mb-1">◈</p>
                <p class="text-sm font-medium text-text-heading">上课记录</p>
                <p class="text-xs text-red-400 mt-1">必需</p>
              </div>
              <div v-else>
                <p class="text-sm font-medium text-green-600">✓ {{ skjlFile.name }}</p>
                <p class="text-xs text-text-light mt-1">{{ (skjlFile.size / 1024).toFixed(1) }} KB</p>
              </div>
            </label>

            <!-- 校外课时费 -->
            <label class="border border-dashed border-border rounded-xl p-5 text-center cursor-pointer hover:border-accent transition-colors">
              <input type="file" accept=".xlsx,.xls" class="hidden" @change="onFileSelect($event, 'xwksf')" />
              <div v-if="!xwksfFile">
                <p class="text-xl mb-1">◈</p>
                <p class="text-sm font-medium text-text-heading">校外课时费</p>
                <p class="text-xs text-red-400 mt-1">必需</p>
              </div>
              <div v-else>
                <p class="text-sm font-medium text-green-600">✓ {{ xwksfFile.name }}</p>
                <p class="text-xs text-text-light mt-1">{{ (xwksfFile.size / 1024).toFixed(1) }} KB</p>
              </div>
            </label>

            <!-- 财务数据 -->
            <label class="border border-dashed border-border rounded-xl p-5 text-center cursor-pointer hover:border-accent transition-colors">
              <input type="file" accept=".xlsx,.xls" class="hidden" @change="onFileSelect($event, 'cw')" />
              <div v-if="!cwFile">
                <p class="text-xl mb-1">◈</p>
                <p class="text-sm font-medium text-text-heading">财务统计明细</p>
                <p class="text-xs text-red-400 mt-1">必需</p>
              </div>
              <div v-else>
                <p class="text-sm font-medium text-green-600">✓ {{ cwFile.name }}</p>
                <p class="text-xs text-text-light mt-1">{{ (cwFile.size / 1024).toFixed(1) }} KB</p>
              </div>
            </label>
          </div>

          <!-- Row 2: 1 required + 1 optional -->
          <div class="grid grid-cols-3 gap-4">
            <!-- 场地费用汇总 -->
            <label class="border border-dashed border-border rounded-xl p-5 text-center cursor-pointer hover:border-accent transition-colors">
              <input type="file" accept=".xlsx,.xls" class="hidden" @change="onFileSelect($event, 'cdf')" />
              <div v-if="!cdfFile">
                <p class="text-xl mb-1">◈</p>
                <p class="text-sm font-medium text-text-heading">场地使用费用汇总</p>
                <p class="text-xs text-red-400 mt-1">必需</p>
              </div>
              <div v-else>
                <p class="text-sm font-medium text-green-600">✓ {{ cdfFile.name }}</p>
                <p class="text-xs text-text-light mt-1">{{ (cdfFile.size / 1024).toFixed(1) }} KB</p>
              </div>
            </label>

            <!-- 上月分析结果（可选） -->
            <label class="border border-dashed border-border rounded-xl p-5 text-center cursor-pointer hover:border-accent transition-colors">
              <input type="file" accept=".xlsx,.xls" class="hidden" @change="onFileSelect($event, 'lastMonth')" />
              <div v-if="!lastMonthFile">
                <p class="text-xl mb-1">◈</p>
                <p class="text-sm font-medium text-text-heading">上月校外分析</p>
                <p class="text-xs text-accent mt-1">可选 · 环比计算</p>
                <p class="text-xs text-text-light">无则环比为 0</p>
              </div>
              <div v-else>
                <p class="text-sm font-medium text-green-600">✓ {{ lastMonthFile.name }}</p>
                <p class="text-xs text-text-light mt-1">{{ (lastMonthFile.size / 1024).toFixed(1) }} KB</p>
              </div>
            </label>

            <!-- Placeholder to keep grid shape -->
            <div></div>
          </div>

          <Button variant="primary" :loading="loading" :disabled="!canPreview" @click="doPreview">
            预览数据
          </Button>
        </div>

        <!-- Step 2: Preview -->
        <div v-if="step === 'preview' && preview" class="flex flex-col gap-4">
          <div class="grid grid-cols-4 gap-4 text-center">
            <div class="bg-page-bg rounded-lg p-3">
              <p class="text-2xl font-bold text-text-heading">{{ preview.offcampus_count }}</p>
              <p class="text-xs text-text-light">校外记录数</p>
            </div>
            <div class="bg-page-bg rounded-lg p-3">
              <p class="text-2xl font-bold text-text-heading">{{ preview.oncampus_count }}</p>
              <p class="text-xs text-text-light">校内记录数</p>
            </div>
            <div class="bg-page-bg rounded-lg p-3">
              <p class="text-2xl font-bold text-text-heading">{{ preview.campuses?.length || 0 }}</p>
              <p class="text-xs text-text-light">涉及校区</p>
            </div>
            <div class="bg-page-bg rounded-lg p-3">
              <p class="text-2xl font-bold text-text-heading">{{ preview.coaches?.length || 0 }}</p>
              <p class="text-xs text-text-light">涉及教练</p>
            </div>
          </div>

          <div v-if="preview.offcampus_count === 0" class="bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3 text-sm text-yellow-700">
            未找到校外课程记录（课程名需包含农都/西溪/滨江等关键词），请检查上传文件。
          </div>

          <!-- Campus list -->
          <div v-if="preview.campuses?.length" class="flex flex-wrap gap-2 text-xs">
            <span v-for="c in preview.campuses" :key="c" class="bg-page-bg text-text-body px-2 py-1 rounded">
              {{ c }}
            </span>
          </div>

          <!-- File status -->
          <div class="flex flex-wrap gap-2 text-xs">
            <span v-if="skjlFile" class="bg-green-50 text-green-700 px-2 py-1 rounded">上课: {{ skjlFile.name }}</span>
            <span v-if="xwksfFile" class="bg-green-50 text-green-700 px-2 py-1 rounded">课时费: {{ xwksfFile.name }}</span>
            <span v-if="cwFile" class="bg-green-50 text-green-700 px-2 py-1 rounded">财务: {{ cwFile.name }}</span>
            <span v-if="cdfFile" class="bg-green-50 text-green-700 px-2 py-1 rounded">场地: {{ cdfFile.name }}</span>
            <span v-if="lastMonthFile" class="bg-green-50 text-green-700 px-2 py-1 rounded">上月: {{ lastMonthFile.name }}</span>
            <span v-if="!lastMonthFile" class="bg-gray-100 text-gray-500 px-2 py-1 rounded">未上传上月数据 → 环比为 0</span>
          </div>

          <div class="flex items-center gap-3">
            <Button variant="primary" :loading="loading" :disabled="preview.offcampus_count === 0" @click="doProcess">
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
            <p class="text-sm text-green-700 font-medium">校外月度分析生成完成</p>
            <div class="grid grid-cols-4 gap-4 mt-2 text-center">
              <div>
                <p class="text-lg font-bold text-green-800">{{ processResult.summary?.campus_count || 0 }}</p>
                <p class="text-xs text-green-600">校区数</p>
              </div>
              <div>
                <p class="text-lg font-bold text-green-800">{{ processResult.summary?.coach_count || 0 }}</p>
                <p class="text-xs text-green-600">教练数</p>
              </div>
              <div>
                <p class="text-lg font-bold text-green-800">{{ processResult.summary?.offcampus_count || 0 }}</p>
                <p class="text-xs text-green-600">校外记录数</p>
              </div>
              <div>
                <p class="text-lg font-bold text-green-800">{{ formatMoney(processResult.summary?.total_revenue) }}</p>
                <p class="text-xs text-green-600">总确认收入</p>
              </div>
            </div>
            <div class="mt-2 flex flex-wrap gap-1">
              <span v-for="s in processResult.sheets" :key="s" class="text-xs bg-white border border-green-200 text-green-700 px-2 py-0.5 rounded">
                {{ s }}
              </span>
            </div>
          </div>

          <Button variant="primary" @click="downloadResult">
            下载校外分析 Excel
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
                  <th class="px-3 py-2 text-center font-medium text-text-light">校区数</th>
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
