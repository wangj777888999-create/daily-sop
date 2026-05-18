<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Button from '@/ui/components/common/Button.vue'
import Card from '@/ui/components/common/Card.vue'

const API = '/api/tools/offcampus-cumulative'

const availableMonths = ref<{ year: number; month: number }[]>([])
const yearFrom = ref<number | null>(null)
const monthFrom = ref<number | null>(null)
const yearTo = ref<number | null>(null)
const monthTo = ref<number | null>(null)

const loading = ref(false)
const errorMsg = ref('')
const processResult = ref<any>(null)
const history = ref<any[]>([])
const step = ref<'select' | 'result'>('select')

const canProcess = computed(
  () => yearFrom.value != null && monthFrom.value != null && yearTo.value != null && monthTo.value != null
)

const fromMonthsForYear = computed(() =>
  availableMonths.value.filter(m => m.year === yearFrom.value)
)
const toMonthsForYear = computed(() =>
  availableMonths.value.filter(m => m.year === yearTo.value)
)

async function loadAvailableMonths() {
  try {
    const res = await fetch(`${API}/available-months`)
    availableMonths.value = await res.json()
    if (availableMonths.value.length > 0) {
      const first = availableMonths.value[0]
      const last = availableMonths.value[availableMonths.value.length - 1]
      yearFrom.value = first.year
      monthFrom.value = first.month
      yearTo.value = last.year
      monthTo.value = last.month
    }
  } catch {}
}

async function doProcess() {
  loading.value = true
  errorMsg.value = ''
  try {
    const fd = new FormData()
    fd.append('year_from', String(yearFrom.value))
    fd.append('month_from', String(monthFrom.value))
    fd.append('year_to', String(yearTo.value))
    fd.append('month_to', String(monthTo.value))
    const res = await fetch(`${API}/process`, { method: 'POST', body: fd })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '生成失败')
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

async function deleteHistory(id: number) {
  try {
    await fetch(`${API}/analysis/${id}`, { method: 'DELETE' })
    loadHistory()
  } catch {}
}

async function loadHistory() {
  try {
    const res = await fetch(`${API}/history`)
    history.value = await res.json()
  } catch {}
}

function reset() {
  step.value = 'select'
  processResult.value = null
  errorMsg.value = ''
}

function formatMoney(n: number) {
  return n ? n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '0.00'
}

function formatDate(d: string) {
  return d?.replace('T', ' ').slice(0, 19) || '-'
}

onMounted(() => {
  loadAvailableMonths()
  loadHistory()
})
</script>

<template>
  <div class="p-6 max-w-5xl mx-auto">
    <Card>
      <div class="flex flex-col gap-6">
        <!-- Header -->
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-bold text-text-heading">校外累积分析</h2>
            <p class="text-sm text-text-light mt-1">多月校外数据累积汇总分析，含到课率、营收、场地费跨月统计</p>
          </div>
          <Button v-if="step !== 'select'" variant="secondary" size="small" @click="reset">
            重新选择
          </Button>
        </div>

        <!-- Error -->
        <div v-if="errorMsg" class="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
          {{ errorMsg }}
        </div>

        <!-- Step 1: Select month range -->
        <div v-if="step === 'select'" class="flex flex-col gap-5">
          <!-- No data prompt -->
          <div v-if="availableMonths.length === 0" class="bg-amber-50 border border-amber-200 rounded-lg px-4 py-4 text-sm text-amber-700">
            <p class="font-medium">暂无累积数据</p>
            <p class="mt-1">请先通过「校外月度分析」工具完成至少一个月的分析，系统会自动保存数据供累积分析使用。</p>
          </div>

          <!-- Month range selector -->
          <div v-if="availableMonths.length > 0" class="flex flex-col gap-4">
            <p class="text-sm text-text-body">
              已有数据：
              <span class="font-medium text-text-heading">
                {{ availableMonths[0].year }}年{{ availableMonths[0].month }}月
                —
                {{ availableMonths[availableMonths.length - 1].year }}年{{ availableMonths[availableMonths.length - 1].month }}月
              </span>
              （共 {{ availableMonths.length }} 个月）
            </p>

            <div class="grid grid-cols-2 gap-6">
              <!-- From -->
              <div class="flex flex-col gap-2">
                <label class="text-sm font-medium text-text-heading">起始月份</label>
                <div class="flex gap-2">
                  <select
                    v-model.number="yearFrom"
                    class="flex-1 border border-border rounded-lg px-3 py-2 text-sm bg-white text-text-body focus:outline-none focus:border-accent"
                  >
                    <option v-for="y in [...new Set(availableMonths.map(m => m.year))]" :key="y" :value="y">
                      {{ y }} 年
                    </option>
                  </select>
                  <select
                    v-model.number="monthFrom"
                    class="flex-1 border border-border rounded-lg px-3 py-2 text-sm bg-white text-text-body focus:outline-none focus:border-accent"
                  >
                    <option v-for="m in fromMonthsForYear" :key="m.month" :value="m.month">
                      {{ m.month }} 月
                    </option>
                  </select>
                </div>
              </div>

              <!-- To -->
              <div class="flex flex-col gap-2">
                <label class="text-sm font-medium text-text-heading">结束月份</label>
                <div class="flex gap-2">
                  <select
                    v-model.number="yearTo"
                    class="flex-1 border border-border rounded-lg px-3 py-2 text-sm bg-white text-text-body focus:outline-none focus:border-accent"
                  >
                    <option v-for="y in [...new Set(availableMonths.map(m => m.year))]" :key="y" :value="y">
                      {{ y }} 年
                    </option>
                  </select>
                  <select
                    v-model.number="monthTo"
                    class="flex-1 border border-border rounded-lg px-3 py-2 text-sm bg-white text-text-body focus:outline-none focus:border-accent"
                  >
                    <option v-for="m in toMonthsForYear" :key="m.month" :value="m.month">
                      {{ m.month }} 月
                    </option>
                  </select>
                </div>
              </div>
            </div>

            <!-- Range preview -->
            <div v-if="canProcess" class="bg-page-bg rounded-lg px-4 py-3 text-sm text-text-body">
              将生成
              <span class="font-medium text-text-heading">
                {{ yearFrom }}年{{ monthFrom }}月 — {{ yearTo }}年{{ monthTo }}月
              </span>
              的累积分析报表
            </div>
          </div>

          <Button
            variant="primary"
            :loading="loading"
            :disabled="!canProcess"
            @click="doProcess"
          >
            生成累积分析报表
          </Button>
        </div>

        <!-- Step 2: Result -->
        <div v-if="step === 'result' && processResult" class="flex flex-col gap-4">
          <div class="bg-green-50 border border-green-200 rounded-lg px-4 py-3">
            <p class="text-sm text-green-700 font-medium">累积分析生成完成</p>
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
                <p class="text-lg font-bold text-green-800">{{ processResult.summary?.total_lessons || 0 }}</p>
                <p class="text-xs text-green-600">累积课次</p>
              </div>
              <div>
                <p class="text-lg font-bold text-green-800">{{ formatMoney(processResult.summary?.total_revenue) }}</p>
                <p class="text-xs text-green-600">累积确认收入</p>
              </div>
            </div>
          </div>

          <Button variant="primary" @click="downloadResult">
            下载累积分析 Excel
          </Button>
        </div>

        <!-- History -->
        <div v-if="history.length > 0" class="border-t border-border pt-4">
          <h3 class="text-sm font-medium text-text-heading mb-3">历史累积报表</h3>
          <div class="overflow-auto">
            <table class="w-full text-xs">
              <thead class="bg-page-bg">
                <tr>
                  <th class="px-3 py-2 text-left font-medium text-text-light">月份范围</th>
                  <th class="px-3 py-2 text-center font-medium text-text-light">校区数</th>
                  <th class="px-3 py-2 text-center font-medium text-text-light">教练数</th>
                  <th class="px-3 py-2 text-left font-medium text-text-light">生成时间</th>
                  <th class="px-3 py-2 text-center font-medium text-text-light">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in history" :key="r.id" class="border-t border-border hover:bg-page-bg">
                  <td class="px-3 py-2">{{ r.year_from }}年{{ r.month_from }}月 — {{ r.year_to }}年{{ r.month_to }}月</td>
                  <td class="px-3 py-2 text-center">{{ r.campus_count }}</td>
                  <td class="px-3 py-2 text-center">{{ r.coach_count }}</td>
                  <td class="px-3 py-2">{{ formatDate(r.created_at) }}</td>
                  <td class="px-3 py-2 text-center">
                    <div class="flex items-center justify-center gap-3">
                      <button class="text-accent hover:underline" @click="downloadHistory(r.id)">下载</button>
                      <button class="text-red-400 hover:underline" @click="deleteHistory(r.id)">删除</button>
                    </div>
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
