<script setup lang="ts">
import { ref, onMounted } from 'vue'

type Tab = 'checkin' | 'monthly'

interface CheckinBatch {
  id: number
  batch_date: string
  coach_file: string
  finance_file: string
  record_count: number
  status: string
  created_at: string
}

interface MonthlyAnalysis {
  id: number
  year: number
  month: number
  analysis_type: string
  filename: string
  record_count: number
  department_count: number
  coach_count: number
  sheets: string
  created_at: string
}

const activeTab = ref<Tab>('checkin')
const checkinBatches = ref<CheckinBatch[]>([])
const monthlyAnalyses = ref<MonthlyAnalysis[]>([])
const loading = ref(false)
const errorMsg = ref('')

async function fetchCheckin() {
  const res = await fetch('/api/tools/daily-checkin/history?limit=100')
  if (!res.ok) throw new Error('获取签到记录失败')
  checkinBatches.value = await res.json()
}

async function fetchMonthly() {
  const res = await fetch('/api/tools/campus-monthly/history?limit=100')
  if (!res.ok) throw new Error('获取月度记录失败')
  monthlyAnalyses.value = await res.json()
}

async function loadAll() {
  loading.value = true
  errorMsg.value = ''
  try {
    await Promise.all([fetchCheckin(), fetchMonthly()])
  } catch (e: any) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

function downloadCheckin(id: number) {
  window.open(`/api/tools/daily-checkin/download/${id}`, '_blank')
}

function downloadMonthly(id: number) {
  window.open(`/api/tools/campus-monthly/download/${id}`, '_blank')
}

function formatDate(s: string) {
  return s ? s.slice(0, 10) : '-'
}

function formatDateTime(s: string) {
  return s ? s.slice(0, 16).replace('T', ' ') : '-'
}

function parseSheets(s: string): string[] {
  try { return JSON.parse(s) } catch { return [] }
}

onMounted(loadAll)
</script>

<template>
  <div class="max-w-5xl mx-auto">
    <!-- 页头 -->
    <div class="flex items-center justify-between mb-5">
      <div>
        <h1 class="text-[20px] font-bold text-text-heading">数据文件</h1>
        <p class="text-[13px] text-text-light mt-0.5">上传记录与输出文档的统一管理</p>
      </div>
      <button
        class="flex items-center gap-1.5 text-[12px] text-accent border border-accent/30 px-3 py-1.5 rounded-lg hover:bg-accent/5 transition-colors"
        :disabled="loading"
        @click="loadAll"
      >
        {{ loading ? '刷新中…' : '↻ 刷新' }}
      </button>
    </div>

    <!-- 错误提示 -->
    <div v-if="errorMsg" class="mb-4 px-4 py-3 rounded-lg bg-red-50 text-red-600 text-[13px]">
      {{ errorMsg }}
    </div>

    <!-- Tab 切换 -->
    <div class="flex gap-1 mb-4 bg-placeholder p-1 rounded-xl w-fit">
      <button
        v-for="tab in [{ key: 'checkin', label: '每日签到记录', count: checkinBatches.length },
                        { key: 'monthly', label: '月度分析报告', count: monthlyAnalyses.length }]"
        :key="tab.key"
        class="px-4 py-1.5 text-[13px] rounded-lg transition-colors font-medium flex items-center gap-1.5"
        :class="activeTab === tab.key
          ? 'bg-white text-text-heading shadow-sm'
          : 'text-text-light hover:text-text-body'"
        @click="activeTab = tab.key as Tab"
      >
        {{ tab.label }}
        <span
          class="text-[11px] px-1.5 py-0.5 rounded-full"
          :class="activeTab === tab.key ? 'bg-accent/15 text-accent' : 'bg-border text-text-light'"
        >{{ tab.count }}</span>
      </button>
    </div>

    <!-- 每日签到记录 -->
    <div v-if="activeTab === 'checkin'">
      <div v-if="loading" class="text-center py-16 text-text-light text-[13px]">加载中…</div>
      <div v-else-if="checkinBatches.length === 0" class="text-center py-16 text-text-light text-[13px]">
        暂无签到记录，请先使用「每日教练签到分析」工具处理数据
      </div>
      <div v-else class="flex flex-col gap-2">
        <!-- 表头 -->
        <div class="grid grid-cols-[120px_1fr_1fr_80px_80px_100px] gap-3 px-4 py-2 text-[11px] text-text-light font-medium">
          <span>处理日期</span>
          <span>签到文件</span>
          <span>财务文件</span>
          <span class="text-center">记录数</span>
          <span class="text-center">状态</span>
          <span class="text-center">操作</span>
        </div>
        <!-- 数据行 -->
        <div
          v-for="batch in checkinBatches"
          :key="batch.id"
          class="grid grid-cols-[120px_1fr_1fr_80px_80px_100px] gap-3 items-center px-4 py-3 bg-card-bg border border-border/70 rounded-xl text-[13px] hover:border-accent/30 transition-colors"
        >
          <span class="font-medium text-text-heading">{{ formatDate(batch.batch_date) }}</span>
          <span class="text-text-body truncate" :title="batch.coach_file">
            {{ batch.coach_file || '-' }}
          </span>
          <span class="text-text-body truncate" :title="batch.finance_file">
            {{ batch.finance_file || '-' }}
          </span>
          <span class="text-center text-text-body">{{ batch.record_count }}</span>
          <span class="text-center">
            <span
              class="text-[11px] px-2 py-0.5 rounded-full font-medium"
              :class="batch.status === 'completed'
                ? 'bg-green-50 text-green-600'
                : 'bg-red-50 text-red-500'"
            >
              {{ batch.status === 'completed' ? '完成' : batch.status }}
            </span>
          </span>
          <span class="text-center">
            <button
              class="text-[12px] text-accent hover:text-accent-dark border border-accent/30 px-2.5 py-1 rounded-lg hover:bg-accent/5 transition-colors"
              @click="downloadCheckin(batch.id)"
            >
              ↓ 下载
            </button>
          </span>
        </div>
        <p class="text-[11px] text-text-light mt-1 px-1">
          共 {{ checkinBatches.length }} 条记录，显示最近 100 条
        </p>
      </div>
    </div>

    <!-- 月度分析报告 -->
    <div v-if="activeTab === 'monthly'">
      <div v-if="loading" class="text-center py-16 text-text-light text-[13px]">加载中…</div>
      <div v-else-if="monthlyAnalyses.length === 0" class="text-center py-16 text-text-light text-[13px]">
        暂无月度报告，请先使用「校内月度分析」工具生成报表
      </div>
      <div v-else class="flex flex-col gap-2">
        <!-- 表头 -->
        <div class="grid grid-cols-[100px_80px_80px_80px_1fr_100px] gap-3 px-4 py-2 text-[11px] text-text-light font-medium">
          <span>生成时间</span>
          <span class="text-center">年月</span>
          <span class="text-center">记录数</span>
          <span class="text-center">教练数</span>
          <span>工作表</span>
          <span class="text-center">操作</span>
        </div>
        <!-- 数据行 -->
        <div
          v-for="analysis in monthlyAnalyses"
          :key="analysis.id"
          class="grid grid-cols-[100px_80px_80px_80px_1fr_100px] gap-3 items-center px-4 py-3 bg-card-bg border border-border/70 rounded-xl text-[13px] hover:border-accent/30 transition-colors"
        >
          <span class="text-text-body text-[12px]">{{ formatDateTime(analysis.created_at) }}</span>
          <span class="text-center font-medium text-text-heading">
            {{ analysis.year }}/{{ String(analysis.month).padStart(2, '0') }}
          </span>
          <span class="text-center text-text-body">{{ analysis.record_count }}</span>
          <span class="text-center text-text-body">{{ analysis.coach_count }}</span>
          <div class="flex gap-1 flex-wrap">
            <span
              v-for="sheet in parseSheets(analysis.sheets)"
              :key="sheet"
              class="text-[10px] px-1.5 py-0.5 bg-chip text-text-light rounded-md"
            >
              {{ sheet }}
            </span>
          </div>
          <span class="text-center">
            <button
              class="text-[12px] text-accent hover:text-accent-dark border border-accent/30 px-2.5 py-1 rounded-lg hover:bg-accent/5 transition-colors"
              @click="downloadMonthly(analysis.id)"
            >
              ↓ 下载
            </button>
          </span>
        </div>
        <p class="text-[11px] text-text-light mt-1 px-1">
          共 {{ monthlyAnalyses.length }} 条记录，显示最近 100 条
        </p>
      </div>
    </div>
  </div>
</template>
