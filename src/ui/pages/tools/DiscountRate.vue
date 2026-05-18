<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import Button from '@/ui/components/common/Button.vue'
import Card from '@/ui/components/common/Card.vue'

type Step = 'upload' | 'preview' | 'result'

interface Level1Row {
  课程名称: string
  最多人那次课: string
  已到: number
  旷课: number
  请假: number
  '最大排课人数(F)': number
  '申请人数(G)': string
  计算分母: number
  计算课次: number
  教练: string
  全月应到: number
  实到人数: number
  到课率: number | null
}

interface Level2Row {
  教练: string
  全月应到: number
  实到人数: number
  '教练折扣率(%)': number | null
}

const step = ref<Step>('upload')
const file = ref<File | { stored: true; name: string } | null>(null)
const loading = ref(false)
const errorMsg = ref('')

const year = ref(new Date().getFullYear())
const month = ref(new Date().getMonth() || 12)
const monthOptions = Array.from({ length: 12 }, (_, i) => ({ value: i + 1, label: `${i + 1}月` }))

const storedStatus = ref<Record<string, boolean>>({})
const hasStoredSkjl = computed(() => storedStatus.value['skjl'])

async function loadStoredStatus() {
  try {
    const res = await fetch(`/api/tools/monthly-data/status/${year.value}/${month.value}`)
    if (!res.ok) return
    const data = await res.json()
    const map: Record<string, boolean> = {}
    for (const [k, v] of Object.entries(data.files as Record<string, { uploaded: boolean }>)) {
      map[k] = v.uploaded
    }
    storedStatus.value = map
  } catch {}
}

function useStoredData() {
  file.value = { stored: true as const, name: '[已存储] 上课记录' }
}

const isFile = (f: unknown): f is File => f instanceof File

onMounted(loadStoredStatus)
watch([year, month], () => {
  storedStatus.value = {}
  loadStoredStatus()
})

// 配置
const excludeKeywords = ref('假期班/私教/乒乓球')
const excludeDates = ref<string[]>([])
const thresholdBasketball = ref(8)
const thresholdFootball = ref(10)

// 预览数据
const availableDates = ref<string[]>([])
const rawCount = ref(0)
const filteredCount = ref(0)
const level1 = ref<Level1Row[]>([])
const level2 = ref<Level2Row[]>([])

// 结果
const analysisResult = ref<any>(null)
const history = ref<any[]>([])
const saveMsg = ref('')

const API = '/api/tools/discount-rate'

function onFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const f = input.files?.[0]
  if (f) file.value = f
}

// ── 前端分母计算（与后端逻辑一致） ──
function computeDenominator(applyNum: string, F: number, courseName: string): number {
  const val = applyNum.trim()
  if (val === '新' || val === '新开' || val === '') {
    if (courseName.includes('篮球') && F >= thresholdBasketball.value) return F
    if (courseName.includes('足球') && F >= thresholdFootball.value) return F
    return 0
  }
  const G = parseInt(val)
  if (isNaN(G)) return F
  return Math.max(F, G)
}

// ── 前端重算 Level 1 + Level 2（编辑申请人数/教练时实时联动） ──
function recalcLocal() {
  for (const row of level1.value) {
    row.计算分母 = computeDenominator(
      row['申请人数(G)'],
      row['最大排课人数(F)'],
      row.课程名称,
    )
    row.全月应到 = row.计算分母 * row.计算课次
    row.到课率 = row.全月应到 > 0 ? round2(row.实到人数 / row.全月应到 * 100) : null
  }
  // Level 2: 按教练汇总
  const coachMap = new Map<string, { 全月应到: number; 实到人数: number }>()
  for (const row of level1.value) {
    if (!row.教练) continue
    const key = row.教练
    if (!coachMap.has(key)) coachMap.set(key, { 全月应到: 0, 实到人数: 0 })
    const d = coachMap.get(key)!
    d.全月应到 += row.全月应到
    d.实到人数 += row.实到人数
  }
  level2.value = Array.from(coachMap.entries()).map(([coach, d]) => ({
    教练: coach,
    全月应到: d.全月应到,
    实到人数: d.实到人数,
    '教练折扣率(%)': d.全月应到 > 0 ? round2(d.实到人数 / d.全月应到 * 100) : null,
  })).sort((a, b) => b.全月应到 - a.全月应到)
}

function round2(n: number): number {
  return Math.round(n * 100) / 100
}

// ── 构建 course_edits ──
function buildCourseEdits(): Record<string, { 申请人数: string; 教练: string }> {
  const edits: Record<string, { 申请人数: string; 教练: string }> = {}
  for (const row of level1.value) {
    edits[row.课程名称] = {
      申请人数: row['申请人数(G)'],
      教练: row.教练,
    }
  }
  return edits
}

// ── API 调用 ──
async function doPreview() {
  if (!file.value && !hasStoredSkjl.value) return
  loading.value = true
  errorMsg.value = ''
  try {
    const fd = new FormData()
    fd.append('year', String(year.value))
    fd.append('month', String(month.value))
    if (file.value instanceof File) fd.append('file', file.value)
    fd.append('exclude_keywords', excludeKeywords.value)
    fd.append('exclude_dates', JSON.stringify(excludeDates.value))
    fd.append('threshold_basketball', String(thresholdBasketball.value))
    fd.append('threshold_football', String(thresholdFootball.value))
    fd.append('course_edits', JSON.stringify(buildCourseEdits()))
    const res = await fetch(`${API}/preview`, { method: 'POST', body: fd })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '预览失败')
    }
    const data = await res.json()
    rawCount.value = data.raw_count
    filteredCount.value = data.filtered_count
    availableDates.value = data.available_dates || []
    level1.value = data.level1 || []
    level2.value = data.level2 || []
    step.value = 'preview'
  } catch (e: any) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

async function doGenerate() {
  loading.value = true
  errorMsg.value = ''
  try {
    const fd = new FormData()
    fd.append('year', String(year.value))
    fd.append('month', String(month.value))
    if (file.value instanceof File) fd.append('file', file.value)
    fd.append('exclude_keywords', excludeKeywords.value)
    fd.append('exclude_dates', JSON.stringify(excludeDates.value))
    fd.append('threshold_basketball', String(thresholdBasketball.value))
    fd.append('threshold_football', String(thresholdFootball.value))
    fd.append('course_edits', JSON.stringify(buildCourseEdits()))
    const res = await fetch(`${API}/generate`, { method: 'POST', body: fd })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '生成失败')
    }
    analysisResult.value = await res.json()
    step.value = 'result'
    loadHistory()
  } catch (e: any) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

function downloadResult() {
  if (!analysisResult.value) return
  window.open(`${API}/download/${analysisResult.value.id}`, '_blank')
}

function downloadHistory(id: number) {
  window.open(`${API}/download/${id}`, '_blank')
}

async function deleteHistory(id: number) {
  if (!confirm('确定删除该分析记录？')) return
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

// ── 保存/加载课程配置 ──
async function saveConfigs() {
  saveMsg.value = ''
  try {
    const configs = buildCourseEdits()
    const res = await fetch(`${API}/configs`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(configs),
    })
    if (!res.ok) throw new Error('保存失败')
    const data = await res.json()
    saveMsg.value = `已保存 ${data.count} 条课程配置`
    setTimeout(() => { saveMsg.value = '' }, 3000)
  } catch (e: any) {
    saveMsg.value = '保存失败: ' + e.message
  }
}

function reset() {
  step.value = 'upload'
  file.value = null
  errorMsg.value = ''
  level1.value = []
  level2.value = []
  availableDates.value = []
  analysisResult.value = null
  loadStoredStatus()
}

function formatDate(d: string) {
  return d?.replace('T', ' ').slice(0, 19) || '-'
}

function toggleDate(date: string) {
  const idx = excludeDates.value.indexOf(date)
  if (idx >= 0) excludeDates.value.splice(idx, 1)
  else excludeDates.value.push(date)
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
            <h2 class="text-lg font-bold text-text-heading">课时费折扣率计算</h2>
            <p class="text-sm text-text-light mt-1">按课程/教练汇总到课数据，可配置筛选规则，自动计算折扣率</p>
          </div>
          <Button v-if="step !== 'upload'" variant="secondary" size="small" @click="reset">
            重新上传
          </Button>
        </div>

        <!-- Error -->
        <div v-if="errorMsg" class="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
          {{ errorMsg }}
        </div>

        <!-- Step 1: Upload + Config -->
        <div v-if="step === 'upload'" class="flex flex-col gap-5">
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

          <!-- Stored data banner -->
          <div
            v-if="hasStoredSkjl && !isFile(file)"
            class="flex items-center justify-between bg-green-50 border border-green-200 rounded-lg px-4 py-2.5 text-sm"
          >
            <span class="text-green-700">✓ 已找到 {{ year }}年{{ month }}月 的存储数据（上课记录）</span>
            <button
              class="text-xs text-accent hover:text-accent-dark font-medium ml-4 whitespace-nowrap"
              @click="useStoredData"
            >使用存储数据 →</button>
          </div>

          <!-- File upload -->
          <label class="border border-dashed border-border rounded-xl p-6 text-center cursor-pointer hover:border-accent transition-colors">
            <input type="file" accept=".xlsx,.xls" class="hidden" @change="onFileSelect" />
            <div v-if="!file">
              <p class="text-xl mb-1">◈</p>
              <p class="text-sm font-medium text-text-heading">上传上课数据 Excel</p>
              <p class="text-xs text-text-light mt-1">包含学员名称、课程名称、上课信息、状态、创建时间</p>
            </div>
            <div v-else>
              <p class="text-sm font-medium text-green-600">✓ {{ file.name }}</p>
              <p v-if="isFile(file)" class="text-xs text-text-light mt-1">{{ (file.size / 1024).toFixed(1) }} KB</p>
              <p v-else class="text-xs text-text-light mt-1">已存储</p>
            </div>
          </label>

          <!-- Config -->
          <div class="grid grid-cols-3 gap-4">
            <div>
              <label class="text-xs text-text-light mb-1 block">课程名称剔除关键字</label>
              <input
                v-model="excludeKeywords"
                class="w-full border border-border rounded-lg px-3 py-2 text-sm bg-page-bg focus:outline-none focus:border-accent"
                placeholder="关键字用 / 分隔"
              />
              <p class="text-xs text-text-light mt-1">默认：假期班/私教/乒乓球</p>
            </div>
            <div>
              <label class="text-xs text-text-light mb-1 block">篮球新班门槛</label>
              <input
                v-model.number="thresholdBasketball"
                type="number"
                class="w-full border border-border rounded-lg px-3 py-2 text-sm bg-page-bg focus:outline-none focus:border-accent"
              />
              <p class="text-xs text-text-light mt-1">最大排课人数 ≥ 此值才计入</p>
            </div>
            <div>
              <label class="text-xs text-text-light mb-1 block">足球新班门槛</label>
              <input
                v-model.number="thresholdFootball"
                type="number"
                class="w-full border border-border rounded-lg px-3 py-2 text-sm bg-page-bg focus:outline-none focus:border-accent"
              />
              <p class="text-xs text-text-light mt-1">最大排课人数 ≥ 此值才计入</p>
            </div>
          </div>

          <Button variant="primary" :loading="loading" :disabled="!file && !hasStoredSkjl" @click="doPreview">
            预览数据
          </Button>
        </div>

        <!-- Step 2: Preview + Edit -->
        <div v-if="step === 'preview'" class="flex flex-col gap-5">
          <!-- Data summary -->
          <div class="grid grid-cols-2 gap-4 text-center">
            <div class="bg-page-bg rounded-lg p-3">
              <p class="text-2xl font-bold text-text-heading">{{ rawCount }}</p>
              <p class="text-xs text-text-light">原始记录数</p>
            </div>
            <div class="bg-page-bg rounded-lg p-3">
              <p class="text-2xl font-bold text-text-heading">{{ filteredCount }}</p>
              <p class="text-xs text-text-light">过滤后记录数</p>
            </div>
          </div>

          <!-- Date filter -->
          <div v-if="availableDates.length > 0">
            <p class="text-sm font-medium text-text-heading mb-2">排除日期（点击勾选，重新预览后生效）</p>
            <div class="flex flex-wrap gap-2">
              <label
                v-for="d in availableDates"
                :key="d"
                class="flex items-center gap-1 text-xs px-2 py-1 rounded cursor-pointer transition-colors"
                :class="excludeDates.includes(d) ? 'bg-red-100 text-red-700' : 'bg-page-bg text-text-body hover:bg-chip'"
              >
                <input type="checkbox" class="hidden" :checked="excludeDates.includes(d)" @change="toggleDate(d)" />
                <span>{{ d }}</span>
                <span v-if="excludeDates.includes(d)" class="text-red-400 ml-0.5">✕</span>
              </label>
            </div>
          </div>

          <div v-if="filteredCount === 0" class="bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3 text-sm text-yellow-700">
            过滤后无数据，请检查筛选条件。
          </div>

          <!-- Level 1 Table -->
          <div v-if="level1.length > 0">
            <h3 class="text-sm font-medium text-text-heading mb-2">班级汇总表（可编辑申请人数和教练）</h3>
            <div class="overflow-auto rounded-lg border border-border">
              <table class="w-full text-xs whitespace-nowrap">
                <thead class="bg-page-bg sticky top-0">
                  <tr>
                    <th class="px-3 py-2 text-left font-medium text-text-light">课程名称</th>
                    <th class="px-3 py-2 text-center font-medium text-text-light">最多人那次课</th>
                    <th class="px-3 py-2 text-center font-medium text-text-light">已到</th>
                    <th class="px-3 py-2 text-center font-medium text-text-light">旷课</th>
                    <th class="px-3 py-2 text-center font-medium text-text-light">请假</th>
                    <th class="px-3 py-2 text-center font-medium text-text-light">最大排课人数(F)</th>
                    <th class="px-3 py-2 text-center font-medium text-text-light">申请人数(G)</th>
                    <th class="px-3 py-2 text-center font-medium text-text-light">计算分母</th>
                    <th class="px-3 py-2 text-center font-medium text-text-light">计算课次</th>
                    <th class="px-3 py-2 text-center font-medium text-text-light">教练</th>
                    <th class="px-3 py-2 text-center font-medium text-text-light">全月应到</th>
                    <th class="px-3 py-2 text-center font-medium text-text-light">实到人数</th>
                    <th class="px-3 py-2 text-center font-medium text-text-light">到课率(%)</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="row in level1"
                    :key="row.课程名称"
                    class="border-t border-border hover:bg-page-bg"
                  >
                    <td class="px-3 py-2 font-medium text-text-heading">{{ row.课程名称 }}</td>
                    <td class="px-3 py-2 text-center text-text-light">{{ row.最多人那次课 }}</td>
                    <td class="px-3 py-2 text-center">{{ row.已到 }}</td>
                    <td class="px-3 py-2 text-center">{{ row.旷课 }}</td>
                    <td class="px-3 py-2 text-center">{{ row.请假 }}</td>
                    <td class="px-3 py-2 text-center font-medium">{{ row['最大排课人数(F)'] }}</td>
                    <td class="px-3 py-2 text-center">
                      <input
                        v-model="row['申请人数(G)']"
                        class="w-20 border border-border rounded px-2 py-1 text-xs text-center bg-page-bg focus:outline-none focus:border-accent"
                        placeholder="数字/新/新开"
                        @input="recalcLocal"
                      />
                    </td>
                    <td class="px-3 py-2 text-center" :class="row.计算分母 === 0 ? 'text-red-500' : ''">
                      {{ row.计算分母 }}
                    </td>
                    <td class="px-3 py-2 text-center">{{ row.计算课次 }}</td>
                    <td class="px-3 py-2 text-center">
                      <input
                        v-model="row.教练"
                        class="w-20 border border-border rounded px-2 py-1 text-xs text-center bg-page-bg focus:outline-none focus:border-accent"
                        placeholder="教练名"
                        @input="recalcLocal"
                      />
                    </td>
                    <td class="px-3 py-2 text-center font-medium">{{ row.全月应到 }}</td>
                    <td class="px-3 py-2 text-center">{{ row.实到人数 }}</td>
                    <td class="px-3 py-2 text-center font-medium">
                      {{ row.到课率 !== null ? row.到课率.toFixed(2) + '%' : '—' }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Level 2 Table -->
          <div v-if="level2.length > 0">
            <h3 class="text-sm font-medium text-text-heading mb-2">教练汇总表（自动计算）</h3>
            <div class="overflow-auto rounded-lg border border-border">
              <table class="w-full text-xs">
                <thead class="bg-page-bg">
                  <tr>
                    <th class="px-3 py-2 text-left font-medium text-text-light">教练</th>
                    <th class="px-3 py-2 text-center font-medium text-text-light">全月应到</th>
                    <th class="px-3 py-2 text-center font-medium text-text-light">实到人数</th>
                    <th class="px-3 py-2 text-center font-medium text-text-light">教练折扣率(%)</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="row in level2"
                    :key="row.教练"
                    class="border-t border-border hover:bg-page-bg"
                  >
                    <td class="px-3 py-2 font-medium text-text-heading">{{ row.教练 }}</td>
                    <td class="px-3 py-2 text-center font-medium">{{ row.全月应到 }}</td>
                    <td class="px-3 py-2 text-center">{{ row.实到人数 }}</td>
                    <td class="px-3 py-2 text-center font-bold text-accent">
                      {{ row['教练折扣率(%)'] !== null ? row['教练折扣率(%)'].toFixed(2) + '%' : '—' }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-3">
            <Button variant="primary" :loading="loading" :disabled="filteredCount === 0" @click="doGenerate">
              生成报表
            </Button>
            <Button variant="secondary" :loading="loading" :disabled="filteredCount === 0" @click="doPreview">
              重新预览
            </Button>
            <Button variant="secondary" :disabled="level1.length === 0" @click="saveConfigs">
              保存申请人数和教练配置
            </Button>
            <span v-if="saveMsg" class="text-xs text-green-600">{{ saveMsg }}</span>
          </div>
        </div>

        <!-- Step 3: Result -->
        <div v-if="step === 'result' && analysisResult" class="flex flex-col gap-4">
          <div class="bg-green-50 border border-green-200 rounded-lg px-4 py-3">
            <p class="text-sm text-green-700 font-medium">课时费折扣率报表生成完成</p>
            <div class="grid grid-cols-4 gap-4 mt-2 text-center">
              <div>
                <p class="text-lg font-bold text-green-800">{{ analysisResult.summary?.raw_count || 0 }}</p>
                <p class="text-xs text-green-600">原始记录</p>
              </div>
              <div>
                <p class="text-lg font-bold text-green-800">{{ analysisResult.summary?.course_count || 0 }}</p>
                <p class="text-xs text-green-600">课程班级</p>
              </div>
              <div>
                <p class="text-lg font-bold text-green-800">{{ analysisResult.summary?.coach_count || 0 }}</p>
                <p class="text-xs text-green-600">教练数</p>
              </div>
              <div>
                <p class="text-lg font-bold text-green-800">{{ analysisResult.summary?.filtered_count || 0 }}</p>
                <p class="text-xs text-green-600">过滤后记录</p>
              </div>
            </div>
          </div>

          <Button variant="primary" @click="downloadResult">
            下载折扣率报表 Excel
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
                  <th class="px-3 py-2 text-center font-medium text-text-light">班级数</th>
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
                    <button class="text-accent hover:underline mr-2" @click="downloadHistory(b.id)">下载</button>
                    <button class="text-red-400 hover:text-red-600 hover:underline" @click="deleteHistory(b.id)">删除</button>
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
