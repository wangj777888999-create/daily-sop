<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'

interface CheckinBatch {
  id: number; batch_date: string; coach_file: string; finance_file: string
  output_filename: string; record_count: number; status: string; created_at: string
}
interface MonthlyAnalysis {
  id: number; year: number; month: number; analysis_type: string; filename: string
  record_count: number; department_count: number; coach_count: number; sheets: string; created_at: string
}
interface Consolidation {
  id: number; year: number; month: number; status: string; record_count: number
  filename: string; updated_at: string; created_at: string
}
interface CumulativeReport {
  id: number; year_from: number; month_from: number; year_to: number; month_to: number
  filename: string; record_count: number; created_at: string
}

interface NormalizedRecord {
  key: string; year: number; month: number
  tool: string; toolLabel: string; colorClass: string; dotColor: string
  id: number; title: string; meta: string[]
  status?: string; statusLabel?: string; statusColor?: string
  downloadUrl: string; deleteUrl: string; confirmMsg: string; createdAt: string
}

const loading = ref(false)
const errorMsg = ref('')
const records = ref<NormalizedRecord[]>([])
const filterTool = ref('')
const sortDir = ref<'desc' | 'asc'>('desc')

const TOOLS: { key: string; label: string; color: string; dot: string }[] = [
  { key: 'checkin',       label: '每日签到', color: 'bg-emerald-50 text-emerald-700 border-emerald-200', dot: '#059669' },
  { key: 'consolidation', label: '签到汇总', color: 'bg-teal-50 text-teal-700 border-teal-200',         dot: '#0d9488' },
  { key: 'campus',        label: '校内月报', color: 'bg-blue-50 text-blue-700 border-blue-200',         dot: '#2563eb' },
  { key: 'offcampus',     label: '校外月报', color: 'bg-violet-50 text-violet-700 border-violet-200',   dot: '#7c3aed' },
  { key: 'cumulative',    label: '校外累计', color: 'bg-orange-50 text-orange-700 border-orange-200',   dot: '#ea580c' },
  { key: 'discount',      label: '折扣率',   color: 'bg-amber-50 text-amber-700 border-amber-200',      dot: '#d97706' },
]
const TOOL_MAP = Object.fromEntries(TOOLS.map(t => [t.key, t]))
const TOOL_ORDER = TOOLS.map(t => t.key)

function fmtTime(iso: string) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffDays = Math.floor(diffMs / 86400000)
  if (diffDays === 0) return '今天 ' + d.toTimeString().slice(0, 5)
  if (diffDays === 1) return '昨天 ' + d.toTimeString().slice(0, 5)
  if (diffDays < 7) return `${diffDays} 天前`
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

async function fetchAll() {
  loading.value = true
  errorMsg.value = ''
  const all: NormalizedRecord[] = []

  try {
    const [r0, r1, r2, r3, r4, r5] = await Promise.allSettled([
      fetch('/api/tools/daily-checkin/history?limit=200').then(r => r.json()),
      fetch('/api/tools/checkin-consolidation/history?limit=200').then(r => r.json()),
      fetch('/api/tools/campus-monthly/history?limit=200').then(r => r.json()),
      fetch('/api/tools/offcampus-monthly/history?limit=200').then(r => r.json()),
      fetch('/api/tools/offcampus-cumulative/history?limit=200').then(r => r.json()),
      fetch('/api/tools/discount-rate/history?limit=200').then(r => r.json()),
    ])

    if (r0.status === 'fulfilled') {
      for (const b of r0.value as CheckinBatch[]) {
        const [y, m] = b.batch_date.split('-').map(Number)
        const meta = []
        if (b.record_count) meta.push(`${b.record_count} 条记录`)
        if (b.coach_file) meta.push(b.coach_file)
        all.push({
          key: `checkin-${b.id}`, year: y, month: m,
          tool: 'checkin', toolLabel: '每日签到',
          colorClass: TOOL_MAP.checkin.color, dotColor: TOOL_MAP.checkin.dot,
          id: b.id, title: b.batch_date, meta,
          downloadUrl: `/api/tools/daily-checkin/download/${b.id}`,
          deleteUrl: `/api/tools/daily-checkin/batch/${b.id}`,
          confirmMsg: '确定删除该签到批次？关联签到数据和文件将一并删除，不可恢复。',
          createdAt: b.created_at,
        })
      }
    }

    if (r1.status === 'fulfilled') {
      for (const c of r1.value as Consolidation[]) {
        const meta = []
        if (c.record_count) meta.push(`${c.record_count} 条记录`)
        const isConfirmed = c.status === 'confirmed'
        all.push({
          key: `consolidation-${c.id}`, year: c.year, month: c.month,
          tool: 'consolidation', toolLabel: '签到汇总',
          colorClass: TOOL_MAP.consolidation.color, dotColor: TOOL_MAP.consolidation.dot,
          id: c.id, title: `${c.year}年${c.month}月`, meta,
          status: c.status,
          statusLabel: isConfirmed ? '已确认' : '草稿',
          statusColor: isConfirmed ? 'bg-green-50 text-green-700 border-green-200' : 'bg-gray-100 text-gray-500 border-gray-200',
          downloadUrl: `/api/tools/checkin-consolidation/download/${c.id}`,
          deleteUrl: `/api/tools/checkin-consolidation/${c.id}`,
          confirmMsg: '确定删除该签到汇总？不可恢复。',
          createdAt: c.created_at,
        })
      }
    }

    if (r2.status === 'fulfilled') {
      for (const a of r2.value as MonthlyAnalysis[]) {
        const meta = []
        if (a.record_count) meta.push(`${a.record_count} 条`)
        if (a.coach_count) meta.push(`${a.coach_count} 名教练`)
        if (a.department_count) meta.push(`${a.department_count} 个部门`)
        all.push({
          key: `campus-${a.id}`, year: a.year, month: a.month,
          tool: 'campus', toolLabel: '校内月报',
          colorClass: TOOL_MAP.campus.color, dotColor: TOOL_MAP.campus.dot,
          id: a.id, title: `${a.year}年${a.month}月`, meta,
          downloadUrl: `/api/tools/campus-monthly/download/${a.id}`,
          deleteUrl: `/api/tools/campus-monthly/analysis/${a.id}`,
          confirmMsg: '确定删除该月度报告？生成的 Excel 文件将一并删除，不可恢复。',
          createdAt: a.created_at,
        })
      }
    }

    if (r3.status === 'fulfilled') {
      for (const a of r3.value as MonthlyAnalysis[]) {
        const meta = []
        if (a.record_count) meta.push(`${a.record_count} 条`)
        all.push({
          key: `offcampus-${a.id}`, year: a.year, month: a.month,
          tool: 'offcampus', toolLabel: '校外月报',
          colorClass: TOOL_MAP.offcampus.color, dotColor: TOOL_MAP.offcampus.dot,
          id: a.id, title: `${a.year}年${a.month}月`, meta,
          downloadUrl: `/api/tools/offcampus-monthly/download/${a.id}`,
          deleteUrl: `/api/tools/offcampus-monthly/analysis/${a.id}`,
          confirmMsg: '确定删除该校外月度报告？不可恢复。',
          createdAt: a.created_at,
        })
      }
    }

    if (r4.status === 'fulfilled') {
      for (const r of r4.value as CumulativeReport[]) {
        const meta = []
        if (r.record_count) meta.push(`${r.record_count} 条`)
        all.push({
          key: `cumulative-${r.id}`, year: r.year_to, month: r.month_to,
          tool: 'cumulative', toolLabel: '校外累计',
          colorClass: TOOL_MAP.cumulative.color, dotColor: TOOL_MAP.cumulative.dot,
          id: r.id, title: `${r.year_from}年${r.month_from}月 — ${r.year_to}年${r.month_to}月`, meta,
          downloadUrl: `/api/tools/offcampus-cumulative/download/${r.id}`,
          deleteUrl: `/api/tools/offcampus-cumulative/analysis/${r.id}`,
          confirmMsg: '确定删除该校外累计报表？不可恢复。',
          createdAt: r.created_at,
        })
      }
    }

    if (r5.status === 'fulfilled') {
      for (const a of r5.value as MonthlyAnalysis[]) {
        const meta = []
        if (a.record_count) meta.push(`${a.record_count} 条`)
        all.push({
          key: `discount-${a.id}`, year: a.year, month: a.month,
          tool: 'discount', toolLabel: '折扣率',
          colorClass: TOOL_MAP.discount.color, dotColor: TOOL_MAP.discount.dot,
          id: a.id, title: `${a.year}年${a.month}月`, meta,
          downloadUrl: `/api/tools/discount-rate/download/${a.id}`,
          deleteUrl: `/api/tools/discount-rate/analysis/${a.id}`,
          confirmMsg: '确定删除该折扣率分析？不可恢复。',
          createdAt: a.created_at,
        })
      }
    }

    records.value = all
  } catch (e: any) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

// 当前筛选下的记录数（用于各工具 chip 计数）
const toolCounts = computed(() => {
  const counts: Record<string, number> = {}
  for (const r of records.value) counts[r.tool] = (counts[r.tool] || 0) + 1
  return counts
})

const filteredRecords = computed(() =>
  filterTool.value ? records.value.filter(r => r.tool === filterTool.value) : records.value
)

const timeline = computed(() => {
  const byYM = new Map<string, NormalizedRecord[]>()
  for (const r of filteredRecords.value) {
    const k = `${r.year}-${String(r.month).padStart(2, '0')}`
    if (!byYM.has(k)) byYM.set(k, [])
    byYM.get(k)!.push(r)
  }
  const sorted = [...byYM.entries()].sort((a, b) =>
    sortDir.value === 'desc' ? b[0].localeCompare(a[0]) : a[0].localeCompare(b[0])
  )
  return sorted.map(([key, items]) => {
    const [year, month] = key.split('-').map(Number)
    items.sort((a, b) => {
      const td = TOOL_ORDER.indexOf(a.tool) - TOOL_ORDER.indexOf(b.tool)
      return td !== 0 ? td : b.createdAt.localeCompare(a.createdAt)
    })
    return { key, year, month, items }
  })
})

const collapsedMonths = ref<Set<string>>(new Set())

watch(timeline, (groups) => {
  const newSet = new Set<string>()
  groups.forEach((g, i) => { if (i > 0) newSet.add(g.key) })
  collapsedMonths.value = newSet
}, { immediate: true })

function toggleMonth(key: string) {
  const s = new Set(collapsedMonths.value)
  s.has(key) ? s.delete(key) : s.add(key)
  collapsedMonths.value = s
}

const allCollapsed = computed(() => collapsedMonths.value.size === timeline.value.length)
function toggleAll() {
  collapsedMonths.value = allCollapsed.value
    ? new Set()
    : new Set(timeline.value.map(g => g.key))
}

async function handleDelete(record: NormalizedRecord) {
  if (!confirm(record.confirmMsg)) return
  try {
    const res = await fetch(record.deleteUrl, { method: 'DELETE' })
    if (!res.ok) { const err = await res.json(); throw new Error(err.detail || '删除失败') }
    records.value = records.value.filter(r => r.key !== record.key)
  } catch (e: any) { errorMsg.value = e.message }
}

onMounted(fetchAll)
</script>

<template>
  <div class="max-w-4xl mx-auto px-1">

    <!-- 页头 -->
    <div class="flex items-start justify-between mb-5">
      <div>
        <h1 class="text-[20px] font-bold text-text-heading">数据文件</h1>
        <p class="text-[13px] text-text-light mt-0.5">
          {{ loading ? '加载中…' : `共 ${filteredRecords.length} 条${filterTool ? '（已筛选）' : ''}，按年月归档` }}
        </p>
      </div>
      <div class="flex items-center gap-2 mt-0.5">
        <!-- 排序 -->
        <button
          class="flex items-center gap-1 text-[12px] border px-3 py-1.5 rounded-lg transition-colors"
          style="border-color:#d1cdc9; color:#6B5F52;"
          @click="sortDir = sortDir === 'desc' ? 'asc' : 'desc'"
        >
          <span>{{ sortDir === 'desc' ? '↓ 最新优先' : '↑ 最旧优先' }}</span>
        </button>
        <!-- 折叠 -->
        <button
          v-if="timeline.length > 1"
          class="text-[12px] border px-3 py-1.5 rounded-lg transition-colors"
          style="border-color:#d1cdc9; color:#6B5F52;"
          @click="toggleAll"
        >
          {{ allCollapsed ? '全部展开' : '全部折叠' }}
        </button>
        <!-- 刷新 -->
        <button
          class="flex items-center gap-1.5 text-[12px] text-accent border border-accent/30 px-3 py-1.5 rounded-lg hover:bg-accent/5 transition-colors disabled:opacity-50"
          :disabled="loading"
          @click="fetchAll"
        >
          {{ loading ? '刷新中…' : '↻ 刷新' }}
        </button>
      </div>
    </div>

    <!-- 分类筛选 chips -->
    <div class="flex flex-wrap items-center gap-2 mb-5">
      <button
        class="text-[12px] px-3 py-1.5 rounded-full border font-medium transition-all"
        :style="!filterTool
          ? 'background:#4A6741; color:#fff; border-color:#4A6741;'
          : 'background:#fff; color:#6B5F52; border-color:#d1cdc9;'"
        @click="filterTool = ''"
      >
        全部
        <span class="ml-1 opacity-70">{{ records.length }}</span>
      </button>
      <button
        v-for="t in TOOLS"
        :key="t.key"
        class="text-[12px] px-3 py-1.5 rounded-full border font-medium transition-all"
        :style="filterTool === t.key
          ? `background:#4A6741; color:#fff; border-color:#4A6741;`
          : `background:#fff; color:#6B5F52; border-color:#d1cdc9;`"
        @click="filterTool = filterTool === t.key ? '' : t.key"
      >
        <span class="inline-block w-1.5 h-1.5 rounded-full mr-1.5 align-middle" :style="`background:${t.dot}`" />
        {{ t.label }}
        <span v-if="toolCounts[t.key]" class="ml-1 opacity-60">{{ toolCounts[t.key] }}</span>
      </button>
    </div>

    <!-- 错误提示 -->
    <div v-if="errorMsg" class="mb-4 px-4 py-3 rounded-lg bg-red-50 text-red-600 text-[13px]">
      {{ errorMsg }}
    </div>

    <!-- 加载骨架 -->
    <div v-if="loading && records.length === 0" class="flex flex-col gap-5">
      <div v-for="i in 3" :key="i">
        <div class="h-4 w-24 bg-border/40 rounded mb-3 animate-pulse" />
        <div class="flex flex-col gap-2">
          <div v-for="j in 3" :key="j" class="h-14 bg-border/20 rounded-xl animate-pulse" />
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!loading && timeline.length === 0" class="text-center py-20 text-text-light text-[13px]">
      {{ filterTool ? '该分类暂无数据' : '暂无数据，请先使用工具箱中的分析工具处理数据' }}
    </div>

    <!-- 时间线 -->
    <div v-else class="flex flex-col gap-5">
      <div v-for="group in timeline" :key="group.key">

        <!-- 月份标题 -->
        <button class="flex items-center gap-2 mb-2.5 w-full text-left group" @click="toggleMonth(group.key)">
          <svg
            class="w-3.5 h-3.5 text-text-light transition-transform duration-200 shrink-0"
            :class="collapsedMonths.has(group.key) ? '-rotate-90' : ''"
            viewBox="0 0 12 12" fill="currentColor"
          >
            <path d="M6 8L1 3h10L6 8z"/>
          </svg>
          <span class="text-[13px] font-semibold text-text-heading group-hover:text-accent transition-colors">
            {{ group.year }}年{{ group.month }}月
          </span>
          <span class="text-[11px] px-2 py-0.5 rounded-full font-medium" style="background:#eee8e2; color:#6B5F52;">
            {{ group.items.length }} 个文件
          </span>
          <div class="flex-1 h-px" style="background:#e8e4e0;" />
        </button>

        <!-- 记录列表 -->
        <div v-show="!collapsedMonths.has(group.key)" class="flex flex-col gap-2">
          <div
            v-for="record in group.items"
            :key="record.key"
            class="flex items-center gap-3 px-4 py-3 rounded-xl border transition-all"
            style="background:#fff; border-color:#e8e4e0;"
            @mouseenter="($event.currentTarget as HTMLElement).style.borderColor='#b5c4b1'"
            @mouseleave="($event.currentTarget as HTMLElement).style.borderColor='#e8e4e0'"
          >
            <!-- 色点 -->
            <span class="shrink-0 w-2 h-2 rounded-full" :style="`background:${record.dotColor}`" />

            <!-- 主信息 -->
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-[13px] font-semibold text-text-heading">{{ record.title }}</span>
                <!-- 汇总状态徽章 -->
                <span
                  v-if="record.statusLabel"
                  class="text-[11px] px-1.5 py-0.5 rounded border font-medium leading-4"
                  :class="record.statusColor"
                >
                  {{ record.statusLabel }}
                </span>
              </div>
              <div class="flex items-center gap-2 mt-0.5 flex-wrap">
                <!-- 工具标签 -->
                <span class="text-[11px] px-1.5 py-0.5 rounded border font-medium leading-4" :class="record.colorClass">
                  {{ record.toolLabel }}
                </span>
                <!-- meta 信息 -->
                <span v-for="(m, i) in record.meta" :key="i" class="text-[12px]" style="color:#9C8E82;">
                  {{ i > 0 ? '· ' : '' }}{{ m }}
                </span>
              </div>
            </div>

            <!-- 生成时间 -->
            <span class="shrink-0 text-[11px] hidden sm:block" style="color:#b5b0aa;">
              {{ fmtTime(record.createdAt) }}
            </span>

            <!-- 操作 -->
            <div class="shrink-0 flex gap-1.5">
              <a
                :href="record.downloadUrl"
                target="_blank"
                class="text-[12px] text-accent border border-accent/30 px-2.5 py-1 rounded-lg hover:bg-accent/5 transition-colors"
              >
                ↓ 下载
              </a>
              <button
                class="text-[12px] text-red-400 border border-red-200 px-2.5 py-1 rounded-lg hover:bg-red-50 transition-colors"
                @click="handleDelete(record)"
              >
                删除
              </button>
            </div>
          </div>
        </div>

      </div>
    </div>

  </div>
</template>
