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
}

const STATUS_OPTIONS = ['在岗', '补签', '未签到', '请假']

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

// Add makeup form
const showAddForm = ref(false)
const addFormCoach = ref('')
const newRecord = ref<Record<string, any>>({})

const groupedByCoach = computed(() => {
  const groups: Record<string, CheckinRecord[]> = {}
  for (const r of records.value) {
    const key = r.coach_name || '未知教练'
    if (!groups[key]) groups[key] = []
    groups[key].push(r)
  }
  return groups
})

const monthOptions = Array.from({ length: 12 }, (_, i) => ({
  value: i + 1,
  label: `${i + 1}月`,
}))

function statusClass(status: string) {
  if (status === '在岗') return 'text-green-700 bg-green-50 border-green-200'
  if (status === '补签') return 'text-blue-700 bg-blue-50 border-blue-200'
  if (status === '未签到') return 'text-red-700 bg-red-50 border-red-200'
  if (status === '请假') return 'text-yellow-700 bg-yellow-50 border-yellow-200'
  return 'text-text-body bg-white border-border'
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
    records.value = data.records

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

function updateStatus(record: CheckinRecord, newStatus: string) {
  record.sign_status = newStatus
}

function deleteRecord(rowId: number) {
  records.value = records.value.filter(r => r._row_id !== rowId)
}

function openAddForm(coachName: string) {
  addFormCoach.value = coachName
  // Try to find existing info for this coach to pre-fill
  const existing = records.value.find(r => r.coach_name === coachName)
  newRecord.value = {
    check_date: `${year.value}-${String(month.value).padStart(2, '0')}-`,
    department: existing?.department || '',
    school_name: existing?.school_name || '',
    course_type: existing?.course_type || '',
    course_name: '',
    coach_name: coachName,
    course_date: '',
    start_time: '',
    end_time: '',
    sign_in_time: '',
    sign_out_time: '',
    sign_status: '补签',
    actual_count: 0,
    expected_count: 0,
    confirmed_revenue: 0,
  }
  showAddForm.value = true
}

let nextRowId = 10000
function addRecord() {
  if (!newRecord.value.coach_name || !newRecord.value.check_date) {
    errorMsg.value = '教练姓名和签到日期为必填项'
    return
  }
  records.value.push({ ...newRecord.value, _row_id: nextRowId++ } as CheckinRecord)
  showAddForm.value = false
  errorMsg.value = ''
}

async function saveDraft() {
  loading.value = true
  errorMsg.value = ''
  successMsg.value = ''
  try {
    const cleanRecords = records.value.map(r => {
      const { _row_id, ...rest } = r
      return rest
    })
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
    // Save first
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
}

function formatDate(s: string) {
  return s ? s.slice(0, 10) : '-'
}

loadHistory()
</script>

<template>
  <div class="p-6 max-w-6xl mx-auto">
    <Card>
      <div class="flex flex-col gap-6">
        <!-- Header -->
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-bold text-text-heading">签到数据整合</h2>
            <p class="text-sm text-text-light mt-1">月度签到数据校对、补签、确认，作为月度分析的数据源</p>
          </div>
          <Button v-if="step !== 'select'" variant="secondary" size="small" @click="reset">
            重新选择
          </Button>
        </div>

        <!-- Messages -->
        <div v-if="errorMsg" class="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
          {{ errorMsg }}
        </div>
        <div v-if="successMsg" class="bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-sm text-green-700">
          {{ successMsg }}
        </div>

        <!-- Step 1: Select month -->
        <div v-if="step === 'select'" class="flex flex-col gap-4">
          <div class="flex items-center gap-3">
            <label class="text-sm text-text-body">选择月份：</label>
            <select v-model="year" class="border border-border rounded-lg px-3 py-1.5 text-sm">
              <option :value="2025">2025年</option>
              <option :value="2026">2026年</option>
            </select>
            <select v-model="month" class="border border-border rounded-lg px-3 py-1.5 text-sm">
              <option v-for="opt in monthOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </div>
          <Button variant="primary" :loading="loading" @click="loadRecords">
            加载签到数据
          </Button>
        </div>

        <!-- Step 2: Edit -->
        <div v-if="step === 'edit'" class="flex flex-col gap-4">
          <!-- Stats bar -->
          <div class="flex items-center justify-between bg-page-bg rounded-lg px-4 py-2.5">
            <span class="text-sm font-medium" style="color:#3D3530;">
              {{ year }}年{{ month }}月 · 共 {{ records.length }} 条记录 · {{ Object.keys(groupedByCoach).length }} 位教练
            </span>
            <div class="flex items-center gap-2">
              <span v-if="consolidationStatus === 'draft'" class="text-xs px-2 py-0.5 rounded-full bg-yellow-50 text-yellow-700 border border-yellow-200">草稿</span>
              <span v-if="consolidationStatus === 'confirmed'" class="text-xs px-2 py-0.5 rounded-full bg-green-50 text-green-700 border border-green-200">已确认</span>
            </div>
          </div>

          <!-- Column header row (fixed, outside scroll) -->
          <div class="grid gap-2 px-4 py-1.5 rounded-lg bg-sidebar-bg text-xs font-semibold" style="color:#6B5F52; grid-template-columns: 100px 90px 1fr 1fr 100px 60px;">
            <span>签到日期</span>
            <span>部门</span>
            <span>学校</span>
            <span>课程</span>
            <span class="text-center">签到状态</span>
            <span class="text-center">操作</span>
          </div>

          <!-- Coach groups -->
          <div class="flex flex-col gap-2 max-h-[58vh] overflow-y-auto pr-0.5">
            <div v-for="(group, coachName) in groupedByCoach" :key="coachName" class="rounded-xl border border-border overflow-hidden">
              <!-- Coach header -->
              <div class="flex items-center justify-between px-4 py-2 bg-page-bg border-b border-border sticky top-0 z-10">
                <span class="text-sm font-semibold" style="color:#3D3530;">
                  {{ coachName }}
                  <span class="text-xs font-normal ml-1" style="color:#9C8E82;">{{ group.length }} 条</span>
                </span>
                <button
                  class="text-xs px-2.5 py-1 rounded-lg border transition-colors"
                  style="color:#5B8F7A; border-color:#5B8F7A40; background:#5B8F7A0d;"
                  @click="openAddForm(coachName as string)"
                >+ 补签</button>
              </div>

              <!-- Records -->
              <div
                v-for="record in group"
                :key="record._row_id"
                class="grid gap-2 px-4 py-2.5 border-b border-border/50 last:border-b-0 hover:bg-page-bg/60 transition-colors items-center"
                style="grid-template-columns: 100px 90px 1fr 1fr 100px 60px;"
              >
                <span class="text-xs" style="color:#3D3530;">{{ record.check_date || '—' }}</span>
                <span class="text-xs truncate" style="color:#6B5F52;" :title="record.department">{{ record.department || '—' }}</span>
                <span class="text-xs truncate" style="color:#6B5F52;" :title="record.school_name">{{ record.school_name || '—' }}</span>
                <span class="text-xs truncate" style="color:#6B5F52;" :title="record.course_name">{{ record.course_name || '—' }}</span>
                <div class="flex justify-center">
                  <select
                    :value="record.sign_status"
                    @change="updateStatus(record, ($event.target as HTMLSelectElement).value)"
                    class="text-xs border rounded-lg px-2 py-0.5 w-full max-w-[96px] cursor-pointer"
                    :class="statusClass(record.sign_status)"
                  >
                    <option v-for="opt in STATUS_OPTIONS" :key="opt" :value="opt">{{ opt }}</option>
                  </select>
                </div>
                <div class="flex justify-center">
                  <button class="text-xs hover:text-red-600 transition-colors" style="color:#C17F3A;" @click="deleteRecord(record._row_id)">删除</button>
                </div>
              </div>
            </div>
          </div>

          <!-- Action bar -->
          <div class="flex items-center gap-3 pt-2">
            <Button variant="secondary" :loading="loading" @click="saveDraft">保存草稿</Button>
            <Button variant="primary" :loading="loading" @click="confirmConsolidation">确认整合</Button>
          </div>
        </div>

        <!-- Step 3: Confirmed -->
        <div v-if="step === 'confirmed'" class="flex flex-col gap-4">
          <div class="bg-green-50 border border-green-200 rounded-lg px-4 py-4 text-center">
            <p class="text-green-700 font-medium">{{ year }}年{{ month }}月 签到数据已确认整合</p>
            <p class="text-sm text-green-600 mt-1">共 {{ records.length }} 条记录，校内月度分析将使用此数据</p>
          </div>
          <div class="flex items-center gap-3">
            <Button variant="primary" @click="downloadResult">下载整合 Excel</Button>
            <Button variant="secondary" @click="unconfirmConsolidation">取消确认，重新编辑</Button>
          </div>
        </div>

        <!-- Add makeup modal -->
        <div v-if="showAddForm" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50" @click.self="showAddForm = false">
          <div class="bg-white rounded-xl p-6 w-full max-w-md shadow-xl">
            <h3 class="text-sm font-bold text-text-heading mb-4">添加补签记录 — {{ addFormCoach }}</h3>
            <div class="flex flex-col gap-3">
              <div class="flex items-center gap-2">
                <label class="text-xs text-text-light w-20 text-right">签到日期 *</label>
                <input v-model="newRecord.check_date" type="date" class="border border-border rounded px-2 py-1 text-sm flex-1" />
              </div>
              <div class="flex items-center gap-2">
                <label class="text-xs text-text-light w-20 text-right">部门</label>
                <input v-model="newRecord.department" class="border border-border rounded px-2 py-1 text-sm flex-1" />
              </div>
              <div class="flex items-center gap-2">
                <label class="text-xs text-text-light w-20 text-right">学校 *</label>
                <input v-model="newRecord.school_name" class="border border-border rounded px-2 py-1 text-sm flex-1" />
              </div>
              <div class="flex items-center gap-2">
                <label class="text-xs text-text-light w-20 text-right">课程名称</label>
                <input v-model="newRecord.course_name" class="border border-border rounded px-2 py-1 text-sm flex-1" />
              </div>
              <div class="flex items-center gap-2">
                <label class="text-xs text-text-light w-20 text-right">课程日期</label>
                <input v-model="newRecord.course_date" type="date" class="border border-border rounded px-2 py-1 text-sm flex-1" />
              </div>
              <div class="flex items-center gap-2">
                <label class="text-xs text-text-light w-20 text-right">开始时间</label>
                <input v-model="newRecord.start_time" type="time" class="border border-border rounded px-2 py-1 text-sm flex-1" />
              </div>
              <div class="flex items-center gap-2">
                <label class="text-xs text-text-light w-20 text-right">结束时间</label>
                <input v-model="newRecord.end_time" type="time" class="border border-border rounded px-2 py-1 text-sm flex-1" />
              </div>
            </div>
            <div class="flex items-center gap-3 mt-5">
              <Button variant="primary" size="small" @click="addRecord">确认添加</Button>
              <Button variant="secondary" size="small" @click="showAddForm = false">取消</Button>
            </div>
          </div>
        </div>

        <!-- History -->
        <div v-if="history.length > 0 && step === 'select'" class="border-t border-border pt-4">
          <h3 class="text-sm font-medium text-text-heading mb-3">历史整合记录</h3>
          <div class="overflow-auto">
            <table class="w-full text-xs">
              <thead class="bg-page-bg">
                <tr>
                  <th class="px-3 py-2 text-left font-medium text-text-light">年月</th>
                  <th class="px-3 py-2 text-center font-medium text-text-light">记录数</th>
                  <th class="px-3 py-2 text-center font-medium text-text-light">状态</th>
                  <th class="px-3 py-2 text-left font-medium text-text-light">更新时间</th>
                  <th class="px-3 py-2 text-center font-medium text-text-light">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="h in history" :key="h.id" class="border-t border-border hover:bg-page-bg">
                  <td class="px-3 py-2 font-medium text-text-heading">{{ h.year }}/{{ String(h.month).padStart(2, '0') }}</td>
                  <td class="px-3 py-2 text-center">{{ h.record_count }}</td>
                  <td class="px-3 py-2 text-center">
                    <span class="text-[11px] px-2 py-0.5 rounded-full font-medium"
                      :class="h.status === 'confirmed' ? 'bg-green-50 text-green-600' : 'bg-yellow-50 text-yellow-600'">
                      {{ h.status === 'confirmed' ? '已确认' : '草稿' }}
                    </span>
                  </td>
                  <td class="px-3 py-2">{{ formatDate(h.updated_at) }}</td>
                  <td class="px-3 py-2 text-center">
                    <button class="text-accent hover:underline text-xs mr-2" @click="downloadHistoryItem(h.id)">下载</button>
                    <button class="text-red-500 hover:underline text-xs" @click="deleteHistoryItem(h.id)">删除</button>
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
