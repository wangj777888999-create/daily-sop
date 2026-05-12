<script setup lang="ts">
import { ref, computed } from 'vue'
import Button from '@/ui/components/common/Button.vue'
import Card from '@/ui/components/common/Card.vue'

type Step = 'select' | 'edit' | 'confirmed'

interface CheckinRecord {
  _row_id: number
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

const STATUS_OPTIONS = ['已到', '未到', '请假']

const step = ref<Step>('select')
const year = ref(new Date().getFullYear())
const month = ref(new Date().getMonth() || 12)
const loading = ref(false)
const errorMsg = ref('')
const successMsg = ref('')

const records = ref<CheckinRecord[]>([])
const consolidationId = ref<number | null>(null)
const consolidationStatus = ref('')
const history = ref<any[]>([])

const API = '/api/tools/checkin-consolidation'

// ── 筛选状态 ──
const filterCoach = ref('')
const filterSchool = ref('')
const filterCourse = ref('')
const filterStatus = ref('')

const monthOptions = Array.from({ length: 12 }, (_, i) => ({
  value: i + 1,
  label: `${i + 1}月`,
}))

// ── 旧状态 → 新状态映射 ──
function normalizeStatus(s: string): string {
  if (s === '在岗' || s === '补签') return '已到'
  if (s === '未签到') return '未到'
  return s
}

// ── 筛选选项 ──
const coachOptions = computed(() => [...new Set(records.value.map(r => r.coach_name).filter(Boolean))].sort())
const schoolOptions = computed(() => [...new Set(records.value.map(r => r.school_name).filter(Boolean))].sort())
const courseOptions = computed(() => [...new Set(records.value.map(r => r.course_name).filter(Boolean))].sort())

// ── 筛选后记录 ──
const filteredRecords = computed(() => records.value.filter(r => {
  if (filterCoach.value && r.coach_name !== filterCoach.value) return false
  if (filterSchool.value && r.school_name !== filterSchool.value) return false
  if (filterCourse.value && r.course_name !== filterCourse.value) return false
  if (filterStatus.value && r.sign_status !== filterStatus.value) return false
  return true
}))

const hasFilter = computed(() =>
  !!(filterCoach.value || filterSchool.value || filterCourse.value || filterStatus.value)
)

// ── 状态统计 ──
const statusSummary = computed(() => {
  const counts: Record<string, number> = {}
  for (const r of records.value) {
    counts[r.sign_status] = (counts[r.sign_status] || 0) + 1
  }
  return counts
})

// ── 有备注的记录数 ──
const remarkCount = computed(() => records.value.filter(r => r.remark?.trim()).length)

function statusStyle(status: string): string {
  if (status === '已到') return 'color:#166534; background:#f0fdf4; border-color:#bbf7d0;'
  if (status === '未到') return 'color:#991b1b; background:#fef2f2; border-color:#fecaca;'
  if (status === '请假') return 'color:#92400e; background:#fffbeb; border-color:#fde68a;'
  return 'color:#3D3530; background:#fff; border-color:#d1cdc9;'
}

async function loadRecords() {
  loading.value = true
  errorMsg.value = ''
  successMsg.value = ''
  try {
    const fd = new FormData()
    fd.append('year', String(year.value))
    fd.append('month', String(month.value))
    const res = await fetch(`${API}/load`, { method: 'POST', body: fd })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '加载失败')
    }
    const data = await res.json()
    records.value = data.records.map((r: any) => ({
      ...r,
      sign_status: normalizeStatus(r.sign_status),
      remark: r.remark ?? '',
    }))
    clearFilters()

    if (data.from_consolidation) {
      consolidationId.value = data.consolidation_id
      consolidationStatus.value = data.status
      if (data.status === 'confirmed') {
        step.value = 'confirmed'
        return
      }
    } else {
      consolidationId.value = null
      consolidationStatus.value = ''
    }
    step.value = 'edit'
  } catch (e: any) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

function clearFilters() {
  filterCoach.value = ''
  filterSchool.value = ''
  filterCourse.value = ''
  filterStatus.value = ''
}

async function saveDraft() {
  loading.value = true
  errorMsg.value = ''
  successMsg.value = ''
  try {
    const cleanRecords = records.value.map(({ _row_id, ...rest }) => rest)
    const fd = new FormData()
    fd.append('year', String(year.value))
    fd.append('month', String(month.value))
    fd.append('records', JSON.stringify(cleanRecords))
    const res = await fetch(`${API}/save`, { method: 'POST', body: fd })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '保存失败')
    }
    const data = await res.json()
    consolidationId.value = data.id
    consolidationStatus.value = data.status
    successMsg.value = `草稿已保存，共 ${data.record_count} 条记录`
    loadHistory()
  } catch (e: any) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

async function confirmConsolidation() {
  if (!consolidationId.value) {
    await saveDraft()
    if (!consolidationId.value) return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    const fd = new FormData()
    fd.append('id', String(consolidationId.value))
    const res = await fetch(`${API}/confirm`, { method: 'POST', body: fd })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '确认失败')
    }
    consolidationStatus.value = 'confirmed'
    step.value = 'confirmed'
    successMsg.value = '整合已确认，校内月度分析将使用此数据'
    loadHistory()
  } catch (e: any) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

async function unconfirmConsolidation() {
  if (!consolidationId.value) return
  loading.value = true
  errorMsg.value = ''
  try {
    const fd = new FormData()
    fd.append('id', String(consolidationId.value))
    const res = await fetch(`${API}/unconfirm`, { method: 'POST', body: fd })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '取消确认失败')
    }
    consolidationStatus.value = 'draft'
    step.value = 'edit'
    successMsg.value = '已取消确认，可以继续编辑'
  } catch (e: any) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

function downloadResult() {
  if (!consolidationId.value) return
  window.open(`${API}/download/${consolidationId.value}`, '_blank')
}

function downloadHistoryItem(id: number) {
  window.open(`${API}/download/${id}`, '_blank')
}

async function deleteHistoryItem(id: number) {
  if (!confirm('确定删除该整合记录？关联的文件将一并删除。')) return
  try {
    await fetch(`${API}/${id}`, { method: 'DELETE' })
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
  records.value = []
  consolidationId.value = null
  consolidationStatus.value = ''
  errorMsg.value = ''
  successMsg.value = ''
  clearFilters()
}

function formatDate(s: string) {
  return s ? s.slice(0, 10) : '-'
}

loadHistory()
</script>

<template>
  <div class="p-6 max-w-7xl mx-auto">
    <Card>
      <div class="flex flex-col gap-5">

        <!-- ── Header ── -->
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-bold" style="color:#3D3530;">签到数据整合</h2>
            <p class="text-sm mt-1" style="color:#9C8E82;">逐条核查月度签到记录，修改签到状态与备注，确认后作为月度分析数据源</p>
          </div>
          <Button v-if="step !== 'select'" variant="secondary" size="small" @click="reset">
            重新选择
          </Button>
        </div>

        <!-- ── Messages ── -->
        <div v-if="errorMsg" class="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
          {{ errorMsg }}
        </div>
        <div v-if="successMsg" class="bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-sm text-green-700">
          {{ successMsg }}
        </div>

        <!-- ── Step 1: Select month ── -->
        <div v-if="step === 'select'" class="flex flex-col gap-4">
          <div class="flex items-center gap-3">
            <label class="text-sm" style="color:#6B5F52;">选择月份：</label>
            <select v-model.number="year" class="border rounded-lg px-3 py-1.5 text-sm" style="border-color:#d1cdc9;">
              <option :value="2025">2025年</option>
              <option :value="2026">2026年</option>
            </select>
            <select v-model.number="month" class="border rounded-lg px-3 py-1.5 text-sm" style="border-color:#d1cdc9;">
              <option v-for="opt in monthOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </div>
          <Button variant="primary" :loading="loading" @click="loadRecords">
            加载签到数据
          </Button>
        </div>

        <!-- ── Step 2: Edit ── -->
        <div v-if="step === 'edit'" class="flex flex-col gap-4">

          <!-- 概览栏 -->
          <div class="flex items-center justify-between rounded-lg px-4 py-2.5" style="background:#f5f2ef;">
            <div class="flex items-center gap-4 flex-wrap">
              <span class="text-sm font-semibold" style="color:#3D3530;">{{ year }}年{{ month }}月</span>
              <span class="text-xs" style="color:#9C8E82;">共 {{ records.length }} 条 · {{ coachOptions.length }} 位教练</span>
              <div class="flex items-center gap-1.5 flex-wrap">
                <span v-for="(cnt, st) in statusSummary" :key="st"
                  class="text-[11px] px-2 py-0.5 rounded-full border"
                  :style="statusStyle(st as string)">
                  {{ st }} {{ cnt }}
                </span>
                <span v-if="remarkCount > 0"
                  class="text-[11px] px-2 py-0.5 rounded-full border"
                  style="color:#5B4FCF; background:#f5f3ff; border-color:#c4b5fd;">
                  有备注 {{ remarkCount }}
                </span>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <span v-if="consolidationStatus === 'draft'"
                class="text-xs px-2 py-0.5 rounded-full border"
                style="color:#92400e; background:#fffbeb; border-color:#fde68a;">草稿</span>
              <span v-if="consolidationStatus === 'confirmed'"
                class="text-xs px-2 py-0.5 rounded-full border"
                style="color:#166534; background:#f0fdf4; border-color:#bbf7d0;">已确认</span>
            </div>
          </div>

          <!-- 筛选栏 -->
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
            <select v-model="filterCourse" class="border rounded-lg px-2.5 py-1.5 text-xs" style="border-color:#d1cdc9; min-width:130px;">
              <option value="">全部课程</option>
              <option v-for="c in courseOptions" :key="c" :value="c">{{ c }}</option>
            </select>
            <select v-model="filterStatus" class="border rounded-lg px-2.5 py-1.5 text-xs" style="border-color:#d1cdc9; min-width:100px;">
              <option value="">全部状态</option>
              <option v-for="s in STATUS_OPTIONS" :key="s" :value="s">{{ s }}</option>
            </select>
            <button v-if="hasFilter" class="text-xs underline" style="color:#9C8E82;" @click="clearFilters">清除筛选</button>
            <span class="ml-auto text-xs" style="color:#9C8E82;">
              显示 {{ filteredRecords.length }} / {{ records.length }} 条
            </span>
          </div>

          <!-- 表格 -->
          <div class="rounded-xl border overflow-hidden" style="border-color:#e8e4e0;">
            <!-- 横向滚动容器 -->
            <div class="overflow-x-auto">
              <!-- 表头 -->
              <div class="grid text-xs font-semibold px-3 py-2"
                style="grid-template-columns: 96px minmax(60px,0.6fr) minmax(60px,0.6fr) minmax(150px,2fr) minmax(150px,2fr) 84px minmax(150px,1.8fr); min-width:840px; background:#f5f2ef; color:#6B5F52; border-bottom:1px solid #e8e4e0;">
                <span>签到日期</span>
                <span>教练</span>
                <span>部门</span>
                <span>学校</span>
                <span>课程名称</span>
                <span class="text-center">签到状态</span>
                <span>备注</span>
              </div>

              <!-- 数据行 -->
              <div class="overflow-y-auto" style="max-height:56vh;">
                <div v-if="filteredRecords.length === 0"
                  class="py-12 text-center text-sm" style="color:#9C8E82; min-width:780px;">
                  {{ hasFilter ? '没有符合筛选条件的记录' : '暂无数据' }}
                </div>

                <div
                  v-for="record in filteredRecords"
                  :key="record._row_id"
                  class="grid items-center px-3 text-xs"
                  style="grid-template-columns: 96px minmax(60px,0.6fr) minmax(60px,0.6fr) minmax(150px,2fr) minmax(150px,2fr) 84px minmax(150px,1.8fr); min-width:840px; border-bottom:1px solid #f0ece8; min-height:38px;"
                  onmouseover="this.style.background='#faf9f7'" onmouseout="this.style.background=''">

                  <span style="color:#6B5F52;">{{ record.check_date || '—' }}</span>
                  <span class="font-medium truncate" :title="record.coach_name">{{ record.coach_name || '—' }}</span>
                  <span class="truncate" style="color:#9C8E82;" :title="record.department">{{ record.department || '—' }}</span>
                  <span class="truncate" style="color:#6B5F52;" :title="record.school_name">{{ record.school_name || '—' }}</span>
                  <span class="truncate" style="color:#6B5F52;" :title="record.course_name">{{ record.course_name || '—' }}</span>

                  <!-- 签到状态 -->
                  <div class="flex justify-center">
                    <select
                      :value="record.sign_status"
                      @change="record.sign_status = ($event.target as HTMLSelectElement).value"
                      class="text-xs border rounded-lg px-1.5 py-0.5 cursor-pointer w-full max-w-[80px]"
                      :style="statusStyle(record.sign_status)">
                      <option v-for="opt in STATUS_OPTIONS" :key="opt" :value="opt">{{ opt }}</option>
                    </select>
                  </div>

                  <!-- 备注 -->
                  <input
                    v-model="record.remark"
                    class="text-xs border rounded px-2 py-0.5 w-full"
                    :style="record.remark?.trim()
                      ? 'border-color:#c4b5fd; background:#f5f3ff; color:#4c1d95;'
                      : 'border-color:transparent; background:transparent; color:#6B5F52;'"
                    placeholder="点击添加备注…"
                  />
                </div>
              </div>
            </div>
          </div>

          <!-- 操作栏 -->
          <div class="flex items-center justify-between pt-1">
            <div class="flex items-center gap-3">
              <Button variant="secondary" :loading="loading" @click="saveDraft">保存草稿</Button>
              <Button variant="primary" :loading="loading" @click="confirmConsolidation">确认整合并提交</Button>
            </div>
            <span class="text-xs" style="color:#9C8E82;">确认后将作为本月校内月度分析的签到数据源</span>
          </div>
        </div>

        <!-- ── Step 3: Confirmed ── -->
        <div v-if="step === 'confirmed'" class="flex flex-col gap-4">
          <div class="rounded-xl border px-5 py-5 text-center" style="background:#f0fdf4; border-color:#bbf7d0;">
            <p class="font-semibold" style="color:#166534;">{{ year }}年{{ month }}月 签到数据已确认整合</p>
            <p class="text-sm mt-1.5" style="color:#15803d;">
              共 {{ records.length }} 条记录 · {{ coachOptions.length }} 位教练
            </p>
            <div class="flex justify-center gap-2 mt-3 flex-wrap">
              <span v-for="(cnt, st) in statusSummary" :key="st"
                class="text-[11px] px-3 py-1 rounded-full border"
                :style="statusStyle(st as string)">
                {{ st }} {{ cnt }}
              </span>
              <span v-if="remarkCount > 0"
                class="text-[11px] px-3 py-1 rounded-full border"
                style="color:#5B4FCF; background:#f5f3ff; border-color:#c4b5fd;">
                有备注 {{ remarkCount }}
              </span>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <Button variant="primary" @click="downloadResult">下载整合 Excel</Button>
            <Button variant="secondary" :loading="loading" @click="unconfirmConsolidation">取消确认，重新编辑</Button>
          </div>
        </div>

        <!-- ── 历史整合记录 ── -->
        <div v-if="history.length > 0 && step === 'select'" class="border-t pt-4" style="border-color:#e8e4e0;">
          <h3 class="text-sm font-medium mb-3" style="color:#3D3530;">历史整合记录</h3>
          <div class="overflow-auto rounded-xl border" style="border-color:#e8e4e0;">
            <table class="w-full text-xs">
              <thead style="background:#f5f2ef;">
                <tr>
                  <th class="px-3 py-2 text-left font-medium" style="color:#6B5F52;">年月</th>
                  <th class="px-3 py-2 text-center font-medium" style="color:#6B5F52;">记录数</th>
                  <th class="px-3 py-2 text-center font-medium" style="color:#6B5F52;">状态</th>
                  <th class="px-3 py-2 text-left font-medium" style="color:#6B5F52;">更新时间</th>
                  <th class="px-3 py-2 text-center font-medium" style="color:#6B5F52;">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="h in history" :key="h.id" class="border-t hover:bg-stone-50" style="border-color:#f0ece8;">
                  <td class="px-3 py-2 font-medium" style="color:#3D3530;">{{ h.year }}/{{ String(h.month).padStart(2, '0') }}</td>
                  <td class="px-3 py-2 text-center" style="color:#6B5F52;">{{ h.record_count }}</td>
                  <td class="px-3 py-2 text-center">
                    <span class="text-[11px] px-2 py-0.5 rounded-full font-medium border"
                      :style="h.status === 'confirmed'
                        ? 'color:#166534; background:#f0fdf4; border-color:#bbf7d0;'
                        : 'color:#92400e; background:#fffbeb; border-color:#fde68a;'">
                      {{ h.status === 'confirmed' ? '已确认' : '草稿' }}
                    </span>
                  </td>
                  <td class="px-3 py-2" style="color:#9C8E82;">{{ formatDate(h.updated_at) }}</td>
                  <td class="px-3 py-2 text-center">
                    <button class="text-xs mr-2 hover:underline" style="color:#5B8F7A;" @click="downloadHistoryItem(h.id)">下载</button>
                    <button class="text-xs hover:underline" style="color:#ef4444;" @click="deleteHistoryItem(h.id)">删除</button>
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
