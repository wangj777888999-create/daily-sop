<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import Button from '@/ui/components/common/Button.vue'
import Card from '@/ui/components/common/Card.vue'

type Step = 'upload' | 'preview' | 'result' | 'review'

interface CheckinRecord {
  id: number
  check_date: string
  department: string
  school_name: string
  course_type: string
  course_name: string
  coach_name: string
  course_date: string
  start_time: string
  end_time: string
  sign_in_time: string
  sign_out_time: string
  sign_status: string
  actual_count: number
  expected_count: number
  confirmed_revenue: number
  remark: string
}

const step = ref<Step>('upload')
const coachFile = ref<File | null>(null)
const financeFile = ref<File | null>(null)
const importFiles = ref<File[]>([])
const importMode = ref(false)
const importResults = ref<{ filename: string; status: 'pending' | 'importing' | 'ok' | 'error'; msg: string; count?: number; date?: string }[]>([])
const checkDate = ref(new Date().toISOString().slice(0, 10))
const loading = ref(false)
const errorMsg = ref('')
const successMsg = ref('')
const undoRecord = ref<any>(null)
const undoTimer = ref<ReturnType<typeof setTimeout> | null>(null)

const preview = ref<any>(null)
const processResult = ref<any>(null)
const history = ref<any[]>([])

// Review state
const reviewRecords = ref<CheckinRecord[]>([])
const reviewLoading = ref(false)
const reviewYear = ref<number>(0)
const reviewMonth = ref<number>(0)
const filterCoach = ref('')
const filterSchool = ref('')
const filterStatus = ref('')

const STATUS_OPTIONS = ['已到', '迟到', '早退', '旷工', '未签到', '请假']

const API = '/api/tools/daily-checkin'

const coachOptions = computed(() => [...new Set(reviewRecords.value.map(r => r.coach_name).filter(Boolean))].sort())
const schoolOptions = computed(() => [...new Set(reviewRecords.value.map(r => r.school_name).filter(Boolean))].sort())

const filteredRecords = computed(() => reviewRecords.value.filter(r => {
  if (filterCoach.value && r.coach_name !== filterCoach.value) return false
  if (filterSchool.value && r.school_name !== filterSchool.value) return false
  if (filterStatus.value && r.sign_status !== filterStatus.value) return false
  return true
}))

const hasFilter = computed(() => !!(filterCoach.value || filterSchool.value || filterStatus.value))
const hasHistory = computed(() => history.value.length > 0)
const availableDates = computed(() => [...new Set(history.value.map(b => b.batch_date).filter(Boolean))].sort().reverse())
const availableDateSet = computed(() => new Set(availableDates.value))
const selectedDateHasData = computed(() => availableDateSet.value.has(checkDate.value))

// ── Mini calendar ──
const today = new Date()
const calYear = ref(today.getFullYear())
const calMonth = ref(today.getMonth()) // 0-indexed

const CAL_WEEKS = computed(() => {
  const year = calYear.value
  const month = calMonth.value
  const firstDay = new Date(year, month, 1).getDay() // 0=Sun
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const cells: (string | null)[] = Array(firstDay).fill(null)
  for (let d = 1; d <= daysInMonth; d++) {
    const mm = String(month + 1).padStart(2, '0')
    const dd = String(d).padStart(2, '0')
    cells.push(`${year}-${mm}-${dd}`)
  }
  // pad to full weeks
  while (cells.length % 7 !== 0) cells.push(null)
  const weeks: (string | null)[][] = []
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7))
  return weeks
})

function calPrev() {
  if (calMonth.value === 0) { calYear.value--; calMonth.value = 11 }
  else calMonth.value--
}
function calNext() {
  if (calMonth.value === 11) { calYear.value++; calMonth.value = 0 }
  else calMonth.value++
}

const CAL_MONTH_LABEL = computed(() => `${calYear.value} 年 ${calMonth.value + 1} 月`)

// Group history by month (YYYY-MM) from batch_date, newest month first
const historyByMonth = computed(() => {
  const groups: Record<string, any[]> = {}
  for (const b of history.value) {
    const month = (b.batch_date || '').slice(0, 7) // "2026-04"
    if (!month) continue
    if (!groups[month]) groups[month] = []
    groups[month].push(b)
  }
  // Sort each group by date descending
  for (const m of Object.keys(groups)) {
    groups[m].sort((a, b) => b.batch_date.localeCompare(a.batch_date))
  }
  // Return sorted months descending
  return Object.entries(groups).sort((a, b) => b[0].localeCompare(a[0]))
})

const expandedMonths = ref<Set<string>>(new Set())
function toggleMonth(month: string) {
  if (expandedMonths.value.has(month)) {
    expandedMonths.value.delete(month)
  } else {
    expandedMonths.value.add(month)
  }
  expandedMonths.value = new Set(expandedMonths.value) // trigger reactivity
}
// Auto-expand the latest month on load
watch(historyByMonth, (groups) => {
  if (groups.length > 0 && expandedMonths.value.size === 0) {
    expandedMonths.value = new Set([groups[0][0]])
  }
}, { immediate: true })

const statusSummary = computed(() => {
  const counts: Record<string, number> = {}
  for (const r of reviewRecords.value) {
    counts[r.sign_status] = (counts[r.sign_status] || 0) + 1
  }
  return counts
})

function onFileSelect(event: Event, type: 'coach' | 'finance' | 'import') {
  const input = event.target as HTMLInputElement
  if (type === 'coach') { const f = input.files?.[0]; if (f) coachFile.value = f }
  else if (type === 'finance') { const f = input.files?.[0]; if (f) financeFile.value = f }
  else if (input.files) {
    importFiles.value = Array.from(input.files)
    importResults.value = importFiles.value.map(f => ({ filename: f.name, status: 'pending', msg: '' }))
  }
}

const canImport = computed(() => importFiles.value.length > 0 && !loading.value && !importDone.value)
const importDone = computed(() => importResults.value.length > 0 && importResults.value.every(r => r.status === 'ok' || r.status === 'error'))
const importSummary = computed(() => ({
  ok: importResults.value.filter(r => r.status === 'ok').length,
  error: importResults.value.filter(r => r.status === 'error').length,
  total: importResults.value.reduce((s, r) => s + (r.count ?? 0), 0),
}))

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

async function doImport() {
  if (!importFiles.value.length) return
  loading.value = true
  errorMsg.value = ''
  for (let i = 0; i < importFiles.value.length; i++) {
    importResults.value[i].status = 'importing'
    try {
      const fd = new FormData()
      fd.append('file', importFiles.value[i])
      fd.append('check_date', checkDate.value)
      const res = await fetch(`${API}/import`, { method: 'POST', body: fd })
      if (!res.ok) {
        const text = await res.text()
        let msg = '导入失败'
        try { msg = JSON.parse(text).detail || msg } catch { msg = text || msg }
        throw new Error(msg)
      }
      const data = await res.json()
      importResults.value[i].status = 'ok'
      importResults.value[i].count = data.record_count
      importResults.value[i].date = data.check_date
      importResults.value[i].msg = `${data.record_count} 条 · ${data.check_date}`
    } catch (e: any) {
      importResults.value[i].status = 'error'
      importResults.value[i].msg = e.message || '导入失败'
    }
  }
  loading.value = false
  loadHistory()
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

// ── Review / Edit functions ──

async function enterReview(checkDateParam?: string) {
  const dt = checkDateParam || checkDate.value
  reviewYear.value = 0
  reviewMonth.value = 0
  reviewLoading.value = true
  errorMsg.value = ''
  successMsg.value = ''
  try {
    const res = await fetch(`${API}/records/${dt}`)
    if (!res.ok) throw new Error('加载失败')
    const data = await res.json()
    reviewRecords.value = data.records || []
    clearReviewFilters()
    step.value = 'review'
  } catch (e: any) {
    errorMsg.value = e.message || '加载数据失败'
  } finally {
    reviewLoading.value = false
  }
}

async function enterReviewByMonth(year: number, month: number) {
  reviewYear.value = year
  reviewMonth.value = month
  reviewLoading.value = true
  errorMsg.value = ''
  successMsg.value = ''
  try {
    const res = await fetch(`${API}/records-by-month/${year}/${month}`)
    if (!res.ok) throw new Error('加载失败')
    const data = await res.json()
    reviewRecords.value = data.records || []
    clearReviewFilters()
    step.value = 'review'
  } catch (e: any) {
    errorMsg.value = e.message || '加载数据失败'
  } finally {
    reviewLoading.value = false
  }
}

function clearReviewFilters() {
  filterCoach.value = ''
  filterSchool.value = ''
  filterStatus.value = ''
}

function onStatusChange(record: CheckinRecord, newStatus: string) {
  const oldStatus = record.sign_status
  if (oldStatus === newStatus) return
  record.sign_status = newStatus
  // Auto-append modification note to remark
  const tag = `[状态已修改: ${oldStatus}→${newStatus}]`
  if (!record.remark || !record.remark.includes(tag)) {
    record.remark = record.remark ? `${record.remark} ${tag}` : tag
  }
  updateRecord(record)
}

async function updateRecord(record: CheckinRecord) {
  try {
    const res = await fetch(`${API}/record/${record.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sign_status: record.sign_status,
        actual_count: record.actual_count,
        expected_count: record.expected_count,
        confirmed_revenue: record.confirmed_revenue,
        remark: record.remark,
      }),
    })
    if (!res.ok) throw new Error('保存失败')
    successMsg.value = '已保存'
    setTimeout(() => successMsg.value = '', 2000)
  } catch (e: any) {
    errorMsg.value = e.message || '保存失败'
  }
}

function clearUndo() {
  undoRecord.value = null
  if (undoTimer.value) {
    clearTimeout(undoTimer.value)
    undoTimer.value = null
  }
}

async function deleteRecord(record: CheckinRecord) {
  if (!confirm(`确定删除该记录？\n${record.coach_name} — ${record.course_name} — ${record.check_date}`)) return
  clearUndo()
  try {
    const res = await fetch(`${API}/record/${record.id}`, { method: 'DELETE' })
    if (!res.ok) throw new Error('删除失败')
    const data = await res.json()
    reviewRecords.value.splice(
      reviewRecords.value.findIndex(r => r.id === record.id),
      1
    )
    undoRecord.value = data.record
    undoTimer.value = setTimeout(() => { undoRecord.value = null }, 5000)
  } catch (e: any) {
    errorMsg.value = e.message || '删除失败'
  }
}

async function undoDelete() {
  if (!undoRecord.value) return
  const record = undoRecord.value
  undoRecord.value = null
  if (undoTimer.value) { clearTimeout(undoTimer.value); undoTimer.value = null }
  try {
    const res = await fetch(`${API}/record/restore`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(record),
    })
    if (!res.ok) throw new Error('撤销失败')
    await enterReview(record.check_date)
    successMsg.value = '已撤销删除'
    setTimeout(() => { successMsg.value = '' }, 2000)
  } catch (e: any) {
    errorMsg.value = e.message || '撤销删除失败'
  }
}

function resetImport() {
  importFiles.value = []
  importResults.value = []
}

function reset() {
  step.value = 'upload'
  coachFile.value = null
  financeFile.value = null
  importFiles.value = []
  importResults.value = []
  importMode.value = false
  preview.value = null
  processResult.value = null
  reviewRecords.value = []
  reviewYear.value = 0
  reviewMonth.value = 0
  errorMsg.value = ''
  successMsg.value = ''
  clearReviewFilters()
}

function formatDate(d: string) {
  return d?.replace('T', ' ').slice(0, 19) || '-'
}

function statusStyle(status: string): string {
  if (status === '已到') return 'color:#166534; background:#f0fdf4; border-color:#bbf7d0;'
  if (status === '迟到') return 'color:#92400e; background:#fffbeb; border-color:#fde68a;'
  if (status === '早退') return 'color:#92400e; background:#fffbeb; border-color:#fde68a;'
  if (status === '旷工') return 'color:#991b1b; background:#fef2f2; border-color:#fecaca;'
  if (status === '未签到') return 'color:#991b1b; background:#fef2f2; border-color:#fecaca;'
  if (status === '请假') return 'color:#1e40af; background:#eff6ff; border-color:#bfdbfe;'
  return 'color:#3D3530; background:#fff; border-color:#d1cdc9;'
}

loadHistory()
</script>

<template>
  <div class="p-6 max-w-7xl mx-auto">
    <Card>
      <div class="flex flex-col gap-6">
        <!-- Header -->
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-bold text-text-heading">每日教练签到分析</h2>
            <p class="text-sm text-text-light mt-1">上传签到+财务 Excel，自动处理并存库</p>
          </div>
          <div class="flex items-center gap-2">
            <Button v-if="step !== 'upload' && step !== 'review'" variant="secondary" size="small" @click="reset">
              重新上传
            </Button>
            <Button v-if="step === 'review'" variant="secondary" size="small" @click="reset">
              返回上传
            </Button>
          </div>
        </div>

        <!-- Error / Success -->
        <div v-if="errorMsg" class="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
          {{ errorMsg }}
        </div>
        <div v-if="successMsg" class="bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-sm text-green-700">
          {{ successMsg }}
        </div>
        <div v-if="undoRecord" class="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-sm text-amber-800 flex items-center justify-between">
          <span>记录已删除</span>
          <button class="text-accent hover:underline font-medium text-xs" @click="undoDelete">
            撤销
          </button>
        </div>

        <!-- Step 1: Upload -->
        <div v-if="step === 'upload'" class="flex flex-col gap-4">
          <div class="grid grid-cols-2 gap-4">
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

          <!-- Mode toggle -->
          <div class="border-t border-border pt-4 mt-2">
            <button
              class="text-xs font-medium transition-colors flex items-center gap-1"
              :style="importMode ? 'color:#9C8E82;' : 'color:#3D3530;'"
              @click="importMode = !importMode"
            >
              <span v-if="importMode">◂ 返回标准上传</span>
              <span v-else>直接导入已处理数据 ▸</span>
            </button>
          </div>

          <!-- Direct import mode -->
          <div v-if="importMode" class="flex flex-col gap-4">

            <!-- ① 完成结果面板 -->
            <div v-if="importDone" class="flex flex-col gap-3">
              <!-- 汇总 -->
              <div class="rounded-xl px-4 py-3 flex items-center gap-4"
                :style="importSummary.error ? 'background:#fef9f0; border:1px solid #fde68a;' : 'background:#f0fdf4; border:1px solid #bbf7d0;'">
                <div class="flex-1">
                  <p class="text-sm font-semibold" :style="importSummary.error ? 'color:#92400e;' : 'color:#166534;'">
                    {{ importSummary.error === 0 ? '全部导入成功' : `${importSummary.ok} 成功 · ${importSummary.error} 失败` }}
                  </p>
                  <p class="text-xs mt-0.5" style="color:#6B5F52;">
                    共写入 {{ importSummary.total }} 条记录
                  </p>
                </div>
                <button class="text-xs font-medium underline" style="color:#6B5F52;" @click="resetImport">
                  继续导入
                </button>
              </div>

              <!-- 明细表 -->
              <div class="rounded-xl border overflow-hidden" style="border-color:#e8e4e0;">
                <div class="grid text-xs font-semibold px-3 py-2"
                  style="grid-template-columns: 1fr 110px 80px 70px; background:#f5f2ef; color:#6B5F52; border-bottom:1px solid #e8e4e0;">
                  <span>文件名</span>
                  <span>批次日期</span>
                  <span class="text-center">写入记录</span>
                  <span class="text-center">状态</span>
                </div>
                <div v-for="(r, i) in importResults" :key="i"
                  class="grid items-center px-3 py-2 text-xs border-b last:border-0"
                  style="grid-template-columns: 1fr 110px 80px 70px; border-color:#f0ece8;">
                  <span class="truncate pr-2" style="color:#3D3530;" :title="r.filename">{{ r.filename }}</span>
                  <span style="color:#6B5F52;">{{ r.date || '—' }}</span>
                  <span class="text-center" style="color:#6B5F52;">{{ r.count ?? '—' }}</span>
                  <span class="text-center font-medium"
                    :style="r.status === 'ok' ? 'color:#166534;' : 'color:#991b1b;'">
                    {{ r.status === 'ok' ? '✓ 成功' : '✕ 失败' }}
                  </span>
                </div>
              </div>

              <!-- 失败详情 -->
              <div v-if="importSummary.error" class="flex flex-col gap-1">
                <p class="text-xs font-medium" style="color:#92400e;">失败原因：</p>
                <div v-for="(r, i) in importResults.filter(r => r.status === 'error')" :key="i"
                  class="text-xs rounded px-3 py-2" style="background:#fef2f2; color:#991b1b;">
                  {{ r.filename }}：{{ r.msg }}
                </div>
              </div>
            </div>

            <!-- ② 选文件 + 进行中 -->
            <template v-else>
              <label class="border border-dashed border-border rounded-xl p-6 text-center cursor-pointer hover:border-accent transition-colors"
                :class="{ 'pointer-events-none opacity-60': loading }">
                <input type="file" accept=".xlsx,.xls" multiple class="hidden" @change="onFileSelect($event, 'import')" />
                <div v-if="!importFiles.length">
                  <p class="text-sm font-medium text-text-heading">已格式化的签到数据文件</p>
                  <p class="text-xs text-text-light mt-1">支持多选，日期自动从「课程日期」列读取</p>
                </div>
                <div v-else class="flex flex-col gap-1.5 text-left">
                  <p class="text-xs font-medium mb-1" style="color:#6B5F52;">已选择 {{ importFiles.length }} 个文件</p>
                  <div v-for="(f, i) in importFiles" :key="i"
                    class="flex items-center justify-between text-xs rounded px-2 py-1.5"
                    style="background:#f5f2ef;">
                    <span class="truncate max-w-[260px]" :title="f.name">{{ f.name }}</span>
                    <span v-if="importResults[i]?.status === 'pending'" style="color:#9C8E82;">待导入</span>
                    <span v-else-if="importResults[i]?.status === 'importing'" style="color:#6B8F71;">导入中…</span>
                  </div>
                </div>
              </label>
              <Button variant="primary" :disabled="!canImport" :loading="loading" @click="doImport">
                {{ importFiles.length > 1 ? `批量导入（${importFiles.length} 个文件）` : '直接导入' }}
              </Button>
            </template>
          </div>

          <!-- Normal upload buttons -->
          <button
            v-if="!importMode"
            :disabled="!canPreview"
            @click="doPreview"
            class="px-[18px] py-2 text-[12px] rounded-lg font-medium select-none
                   transition-all duration-150 ease-spring
                   active:scale-[0.97] active:brightness-95
                   bg-gradient-to-b from-accent to-accent-dark text-white
                   border border-accent-dark/50 shadow-button-primary
                   hover:brightness-105
                   disabled:opacity-50 disabled:cursor-not-allowed"
          >
            预览数据
          </button>

          <!-- Quick access to existing data — mini calendar -->
          <div v-if="hasHistory" class="border-t border-border pt-4 mt-2">
            <h3 class="text-sm font-medium text-text-heading mb-3">查看 / 修改已处理数据</h3>
            <div class="border border-border rounded-xl overflow-hidden select-none inline-block">
              <!-- nav -->
              <div class="flex items-center justify-between px-3 py-2 bg-page-bg border-b border-border">
                <button class="w-6 h-6 flex items-center justify-center rounded hover:bg-chip text-text-light text-[13px]" @click="calPrev">‹</button>
                <span class="text-[12px] font-semibold text-text-heading">{{ CAL_MONTH_LABEL }}</span>
                <button class="w-6 h-6 flex items-center justify-center rounded hover:bg-chip text-text-light text-[13px]" @click="calNext">›</button>
              </div>
              <!-- day headers -->
              <div class="grid grid-cols-7 bg-chip">
                <span v-for="d in ['日','一','二','三','四','五','六']" :key="d"
                  class="text-center text-[10px] text-text-light py-1.5 w-9">{{ d }}</span>
              </div>
              <!-- weeks -->
              <div class="px-1.5 pt-1 pb-0.5 bg-card-bg">
                <div v-for="(week, wi) in CAL_WEEKS" :key="wi" class="grid grid-cols-7">
                  <div v-for="(date, di) in week" :key="di" class="flex items-center justify-center p-0.5">
                    <button
                      v-if="date"
                      class="relative w-9 h-8 rounded-lg text-[12px] transition-colors flex items-center justify-center"
                      :class="[
                        date === checkDate
                          ? 'bg-accent text-white font-semibold'
                          : availableDateSet.has(date)
                            ? 'hover:bg-accent-light text-text-heading font-medium'
                            : 'text-text-light cursor-default'
                      ]"
                      @click="date && (checkDate = date)"
                    >
                      {{ parseInt(date.slice(8)) }}
                      <span
                        v-if="availableDateSet.has(date) && date !== checkDate"
                        class="absolute bottom-0.5 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full bg-red-400"
                      />
                    </button>
                    <div v-else class="w-9 h-8" />
                  </div>
                </div>
              </div>
              <!-- footer: selected + action -->
              <div class="flex items-center justify-between gap-3 px-3 py-2.5 border-t border-border bg-page-bg">
                <div class="flex items-center gap-2">
                  <span class="text-[12px] text-text-body font-medium">{{ checkDate }}</span>
                  <span v-if="selectedDateHasData" class="text-[11px] text-green-600">● 有数据</span>
                  <span v-else class="text-[11px] text-text-light">暂无数据</span>
                </div>
                <Button
                  variant="secondary"
                  size="small"
                  :loading="reviewLoading"
                  :disabled="!selectedDateHasData"
                  @click="enterReview()"
                >
                  查看该日数据
                </Button>
              </div>
            </div>
          </div>
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

          <!-- Unmapped courses warning -->
          <div v-if="processResult.unmapped_courses?.length" class="bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3">
            <div class="flex items-start justify-between gap-3">
              <div class="flex-1 min-w-0">
                <p class="text-sm text-yellow-800 font-semibold">
                  ⚠️ 有 {{ processResult.unmapped_courses.length }} 个课程未设置类型
                </p>
                <p class="text-xs text-yellow-600 mt-1">
                  以下课程在「课程类型划分」中尚无映射，校内月度分析时将无法归类：
                </p>
                <div class="flex flex-wrap gap-1.5 mt-2">
                  <span v-for="c in processResult.unmapped_courses" :key="c"
                    class="text-xs bg-yellow-100 text-yellow-800 border border-yellow-300 px-2 py-0.5 rounded font-medium">
                    {{ c }}
                  </span>
                </div>
              </div>
              <router-link
                :to="{ path: '/toolbox/course-types', query: { highlight: processResult.unmapped_courses.join(',') } }"
                class="flex-shrink-0 inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-yellow-500 hover:bg-yellow-600 text-white text-xs font-semibold transition-colors whitespace-nowrap"
              >
                前往设置 →
              </router-link>
            </div>
          </div>

          <div class="flex items-center gap-3">
            <Button variant="primary" @click="downloadResult">
              下载格式化 Excel
            </Button>
            <Button
              variant="secondary"
              @click="processResult.year
                ? enterReviewByMonth(processResult.year, processResult.month)
                : enterReview(processResult.check_date)"
            >
              查看 / 编辑数据
            </Button>
          </div>
        </div>

        <!-- Step 4: Review & Edit -->
        <div v-if="step === 'review'" class="flex flex-col gap-4">
          <!-- Summary bar -->
          <div class="flex items-center justify-between rounded-lg px-4 py-2.5" style="background:#f5f2ef;">
            <div class="flex items-center gap-4 flex-wrap">
              <span class="text-sm font-semibold" style="color:#3D3530;">
                {{ reviewYear ? reviewYear + '年' + reviewMonth + '月' : checkDate }} 签到数据审查
              </span>
              <span class="text-xs" style="color:#9C8E82;">共 {{ reviewRecords.length }} 条</span>
              <div class="flex items-center gap-1.5 flex-wrap">
                <span v-for="(cnt, st) in statusSummary" :key="st"
                  class="text-[11px] px-2 py-0.5 rounded-full border"
                  :style="statusStyle(st)">
                  {{ st }} {{ cnt }}
                </span>
              </div>
            </div>
            <Button variant="primary" size="small" @click="reset">
              完成审核
            </Button>
          </div>

          <!-- Filters -->
          <div class="flex flex-wrap items-center gap-3 rounded-xl p-3 border" style="border-color:#e8e4e0; background:#faf9f7;">
            <span class="text-xs font-medium" style="color:#6B5F52;">筛选：</span>
            <select v-model="filterCoach" class="border rounded-lg px-2.5 py-1.5 text-xs" style="border-color:#d1cdc9; min-width:100px;">
              <option value="">全部教练</option>
              <option v-for="c in coachOptions" :key="c" :value="c">{{ c }}</option>
            </select>
            <select v-model="filterSchool" class="border rounded-lg px-2.5 py-1.5 text-xs" style="border-color:#d1cdc9; min-width:130px;">
              <option value="">全部学校</option>
              <option v-for="s in schoolOptions" :key="s" :value="s">{{ s }}</option>
            </select>
            <select v-model="filterStatus" class="border rounded-lg px-2.5 py-1.5 text-xs" style="border-color:#d1cdc9; min-width:100px;">
              <option value="">全部状态</option>
              <option v-for="s in STATUS_OPTIONS" :key="s" :value="s">{{ s }}</option>
            </select>
            <button v-if="hasFilter" class="text-xs underline" style="color:#9C8E82;" @click="clearReviewFilters">清除筛选</button>
            <span class="ml-auto text-xs" style="color:#9C8E82;">
              显示 {{ filteredRecords.length }} / {{ reviewRecords.length }} 条
            </span>
          </div>

          <!-- Data table -->
          <div class="rounded-xl border overflow-hidden" style="border-color:#e8e4e0;">
            <div class="overflow-x-auto">
              <!-- Table header -->
              <div class="grid text-xs font-semibold px-3 py-2 items-center"
                style="grid-template-columns: 60px 90px 100px 100px 1fr 1fr 84px 80px 80px 90px 50px; min-width:1020px; background:#f5f2ef; color:#6B5F52; border-bottom:1px solid #e8e4e0;">
                <span>#</span>
                <span>签到日期</span>
                <span>部门</span>
                <span>教练</span>
                <span>学校</span>
                <span>课程名称</span>
                <span class="text-center">状态</span>
                <span class="text-center">上课人数</span>
                <span class="text-center">应到人数</span>
                <span class="text-center">确认收入</span>
                <span class="text-center">删除</span>
              </div>

              <!-- Table body -->
              <div class="overflow-y-auto" style="max-height:56vh;">
                <div v-if="filteredRecords.length === 0"
                  class="py-12 text-center text-sm" style="color:#9C8E82; min-width:1020px;">
                  {{ hasFilter ? '没有符合筛选条件的记录' : '暂无数据' }}
                </div>

                <div
                  v-for="(record, idx) in filteredRecords"
                  :key="record.id"
                  class="grid items-center px-3 text-xs"
                  style="grid-template-columns: 60px 90px 100px 100px 1fr 1fr 84px 80px 80px 90px 50px; min-width:1020px; border-bottom:1px solid #f0ece8; min-height:38px;"
                >
                  <span style="color:#9C8E82;">{{ idx + 1 }}</span>
                  <span style="color:#6B5F52;">{{ record.check_date || '—' }}</span>
                  <span class="truncate" style="color:#9C8E82;" :title="record.department">{{ record.department || '—' }}</span>
                  <span class="font-medium truncate" :title="record.coach_name">{{ record.coach_name || '—' }}</span>
                  <span class="truncate" style="color:#6B5F52;" :title="record.school_name">{{ record.school_name || '—' }}</span>
                  <span class="truncate" style="color:#6B5F52;" :title="record.course_name">{{ record.course_name || '—' }}</span>

                  <!-- Sign status -->
                  <div class="flex justify-center">
                    <select
                      :value="record.sign_status"
                      @change="onStatusChange(record, ($event.target as HTMLSelectElement).value)"
                      class="text-xs border rounded-lg px-1.5 py-0.5 cursor-pointer w-full max-w-[78px]"
                      :style="statusStyle(record.sign_status)">
                      <option v-for="opt in STATUS_OPTIONS" :key="opt" :value="opt">{{ opt }}</option>
                    </select>
                  </div>

                  <!-- Actual count -->
                  <div class="flex justify-center">
                    <input
                      type="number"
                      :value="record.actual_count"
                      @change="record.actual_count = Number(($event.target as HTMLInputElement).value); updateRecord(record)"
                      class="text-xs border rounded px-1.5 py-0.5 w-full max-w-[70px] text-center"
                      style="border-color:#d1cdc9;"
                      min="0"
                    />
                  </div>

                  <!-- Expected count -->
                  <div class="flex justify-center">
                    <input
                      type="number"
                      :value="record.expected_count"
                      @change="record.expected_count = Number(($event.target as HTMLInputElement).value); updateRecord(record)"
                      class="text-xs border rounded px-1.5 py-0.5 w-full max-w-[70px] text-center"
                      style="border-color:#d1cdc9;"
                      min="0"
                    />
                  </div>

                  <!-- Confirmed revenue -->
                  <div class="flex justify-center">
                    <input
                      type="number"
                      :value="record.confirmed_revenue"
                      @change="record.confirmed_revenue = Number(($event.target as HTMLInputElement).value); updateRecord(record)"
                      class="text-xs border rounded px-1.5 py-0.5 w-full max-w-[80px] text-center"
                      style="border-color:#d1cdc9;"
                      min="0" step="0.01"
                    />
                  </div>

                  <!-- Delete -->
                  <div class="flex justify-center">
                    <button
                      class="text-xs hover:text-red-600 transition-colors"
                      style="color:#ef4444;"
                      @click="deleteRecord(record)"
                      title="删除此记录"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <p class="text-xs" style="color:#9C8E82;">
            修改状态、上课人数、应到人数、确认收入后自动保存。删除操作不可恢复。修改后的数据将被校内月度分析直接使用。
          </p>
        </div>

        <!-- History grouped by month -->
        <div v-if="history.length > 0" class="border-t border-border pt-4">
          <h3 class="text-sm font-medium text-text-heading mb-3">历史处理记录</h3>
          <div class="flex flex-col gap-2">
            <div v-for="[month, rows] in historyByMonth" :key="month" class="border border-border rounded-lg overflow-hidden">
              <!-- month header -->
              <button
                class="w-full flex items-center gap-2 px-3 py-2.5 bg-page-bg hover:bg-chip transition-colors text-left"
                @click="toggleMonth(month)"
              >
                <span class="text-[12px] text-text-light w-3">{{ expandedMonths.has(month) ? '▼' : '▶' }}</span>
                <span class="text-[13px] font-semibold text-text-heading">{{ month }}</span>
                <span class="text-[11px] text-text-light ml-1">{{ rows.length }} 条记录</span>
              </button>
              <!-- table -->
              <div v-if="expandedMonths.has(month)" class="overflow-auto">
                <table class="w-full text-xs">
                  <thead class="bg-chip">
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
                    <tr v-for="b in rows" :key="b.id" class="border-t border-border hover:bg-page-bg">
                      <td class="px-3 py-2">
                        <button class="text-accent hover:underline text-xs font-medium" @click="enterReview(b.batch_date)">
                          {{ b.batch_date }}
                        </button>
                      </td>
                      <td class="px-3 py-2 truncate max-w-[160px]">{{ b.coach_file }}</td>
                      <td class="px-3 py-2 truncate max-w-[160px]">{{ b.finance_file }}</td>
                      <td class="px-3 py-2 truncate max-w-[160px]">{{ b.output_filename || '-' }}</td>
                      <td class="px-3 py-2 text-center">{{ b.record_count }}</td>
                      <td class="px-3 py-2">{{ formatDate(b.created_at) }}</td>
                      <td class="px-3 py-2 text-center whitespace-nowrap">
                        <button class="text-accent hover:underline text-xs mr-2" @click="downloadHistory(b.id)">下载</button>
                        <button class="text-red-500 hover:underline text-xs" @click="deleteHistory(b.id)">删除</button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Card>
  </div>
</template>
