<script setup lang="ts">
import { ref, computed } from 'vue'
import Button from '@/ui/components/common/Button.vue'
import Card from '@/ui/components/common/Card.vue'

type Step = 'upload-table' | 'detect' | 'summary'

interface Session {
  row_index: number
  date: string | null
  campus: string | null
  coach: string | null
  course_name: string | null
  attended_count: number
  expected_count: number | null
}

interface DetectResult {
  filename: string
  detected_count: number
  raw_count: number
  confidence_avg: number
  annotated_image_b64: string | null
  boxes: Array<{ conf: number; edge_flag: boolean }>
  filter_config: Record<string, number>
  error: string | null
}

interface SessionResult {
  session: Session
  results: DetectResult[]
  detected_total: number
  diff: number
  abnormal: boolean
}

const DIFF_THRESHOLD = 2
const API = '/api/tools/photo-checkin'

const step = ref<Step>('upload-table')
const tableFile = ref<File | null>(null)
const sessions = ref<Session[]>([])
const tableLoading = ref(false)
const errorMsg = ref('')

// per-session photo upload state
const selectedSession = ref<Session | null>(null)
const photos = ref<File[]>([])
const detecting = ref(false)

// accumulated results across all sessions
const sessionResults = ref<SessionResult[]>([])

// ── Step 1: upload & parse table ──────────────────────

function onTableSelect(event: Event) {
  const input = event.target as HTMLInputElement
  tableFile.value = input.files?.[0] ?? null
}

async function parseTable() {
  if (!tableFile.value) return
  tableLoading.value = true
  errorMsg.value = ''
  try {
    const form = new FormData()
    form.append('table_file', tableFile.value)
    const res = await fetch(`${API}/parse-sessions`, { method: 'POST', body: form })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '解析失败')
    }
    const data = await res.json()
    if (data.session_count === 0) throw new Error('未解析到任何课程行，请检查表头列名')
    sessions.value = data.sessions
    step.value = 'detect'
  } catch (e: any) {
    errorMsg.value = e.message
  } finally {
    tableLoading.value = false
  }
}

// ── Step 2: select session + upload photos ────────────

function selectSession(s: Session) {
  selectedSession.value = s
  photos.value = []
  errorMsg.value = ''
}

function onPhotoSelect(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files) photos.value = Array.from(input.files).slice(0, 10)
}

function removePhoto(i: number) {
  photos.value.splice(i, 1)
}

async function runDetect() {
  if (!selectedSession.value || !photos.value.length) return
  detecting.value = true
  errorMsg.value = ''
  try {
    const form = new FormData()
    photos.value.forEach(f => form.append('photos', f))
    form.append('row_index', String(selectedSession.value.row_index))

    const res = await fetch(`${API}/detect`, { method: 'POST', body: form })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '识别失败')
    }
    const data = await res.json()
    const detected_total = (data.results as DetectResult[])
      .filter(r => !r.error)
      .reduce((sum, r) => sum + r.detected_count, 0)
    const diff = detected_total - selectedSession.value.attended_count
    const existing = sessionResults.value.findIndex(
      sr => sr.session.row_index === selectedSession.value!.row_index
    )
    const entry: SessionResult = {
      session: selectedSession.value,
      results: data.results,
      detected_total,
      diff,
      abnormal: Math.abs(diff) > DIFF_THRESHOLD,
    }
    if (existing >= 0) sessionResults.value[existing] = entry
    else sessionResults.value.push(entry)

    selectedSession.value = null
    photos.value = []
  } catch (e: any) {
    errorMsg.value = e.message || '识别服务异常'
  } finally {
    detecting.value = false
  }
}

const detectedRowIndexes = computed(() => new Set(sessionResults.value.map(r => r.session.row_index)))
const abnormalCount = computed(() => sessionResults.value.filter(r => r.abnormal).length)

function formatSession(s: Session) {
  return [s.date, s.campus, s.coach, s.course_name].filter(Boolean).join(' · ')
}

function reset() {
  step.value = 'upload-table'
  tableFile.value = null
  sessions.value = []
  selectedSession.value = null
  photos.value = []
  sessionResults.value = []
  errorMsg.value = ''
}
</script>

<template>
  <div class="p-6 max-w-5xl mx-auto">
    <Card>
      <div class="flex flex-col gap-6">

        <!-- Header -->
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-bold text-text-heading">照片人数核对（校外）</h2>
            <p class="text-sm text-text-light mt-1">上传月度核对表，逐条上传照片，AI 自动比对差值</p>
          </div>
          <Button v-if="step !== 'upload-table'" variant="secondary" size="small" @click="reset">
            重新开始
          </Button>
        </div>

        <!-- Error -->
        <div v-if="errorMsg" class="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
          {{ errorMsg }}
        </div>

        <!-- Step indicator -->
        <div class="flex items-center gap-2 text-xs">
          <span :class="step === 'upload-table' ? 'text-accent font-semibold' : 'text-text-light'">① 上传核对表</span>
          <span class="text-border">›</span>
          <span :class="step === 'detect' ? 'text-accent font-semibold' : 'text-text-light'">② 照片识别</span>
          <span class="text-border">›</span>
          <span :class="step === 'summary' ? 'text-accent font-semibold' : 'text-text-light'">③ 汇总报告</span>
        </div>

        <!-- ── Step 1: Upload table ── -->
        <div v-if="step === 'upload-table'" class="flex flex-col gap-4">
          <label class="border-2 border-dashed border-border rounded-xl p-8 text-center cursor-pointer hover:border-accent transition-colors">
            <input type="file" accept=".xlsx,.xls" class="hidden" @change="onTableSelect" />
            <p class="text-3xl mb-2">◈</p>
            <p class="text-sm font-medium text-text-heading">上传月度核对表（Excel）</p>
            <p class="text-xs text-text-light mt-1">支持 .xlsx / .xls，需包含实到人数列</p>
          </label>
          <div v-if="tableFile" class="flex items-center gap-2 text-sm text-text-body bg-page-bg rounded-lg px-4 py-2">
            <span>已选择：</span>
            <span class="font-medium">{{ tableFile.name }}</span>
          </div>
          <Button variant="primary" :disabled="!tableFile" :loading="tableLoading" @click="parseTable">
            解析课程列表
          </Button>
        </div>

        <!-- ── Step 2: Detect ── -->
        <div v-if="step === 'detect'" class="flex flex-col gap-5">

          <!-- Progress bar -->
          <div class="flex items-center gap-3 text-sm">
            <span class="text-text-light">已核对：</span>
            <span class="font-bold text-accent">{{ detectedRowIndexes.size }}</span>
            <span class="text-text-light">/ {{ sessions.length }} 节课</span>
            <span v-if="abnormalCount > 0" class="ml-2 text-red-600 font-medium">
              {{ abnormalCount }} 处差值异常
            </span>
            <Button class="ml-auto" variant="secondary" size="small" @click="step = 'summary'">
              查看汇总报告 →
            </Button>
          </div>

          <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">

            <!-- Left: session list -->
            <div class="flex flex-col gap-2">
              <p class="text-xs font-medium text-text-light mb-1">课程列表（点击选择）</p>
              <div class="max-h-[420px] overflow-y-auto flex flex-col gap-1.5 pr-1">
                <button
                  v-for="s in sessions"
                  :key="s.row_index"
                  class="text-left border rounded-lg px-3 py-2.5 transition-colors text-sm"
                  :class="[
                    selectedSession?.row_index === s.row_index
                      ? 'border-accent bg-accent/5'
                      : 'border-border hover:border-accent/50',
                  ]"
                  @click="selectSession(s)"
                >
                  <div class="flex items-center justify-between gap-2">
                    <span class="font-medium text-text-heading truncate">{{ formatSession(s) }}</span>
                    <span v-if="detectedRowIndexes.has(s.row_index)" class="flex-shrink-0">
                      <span
                        :class="[
                          'text-xs px-1.5 py-0.5 rounded-full',
                          sessionResults.find(r => r.session.row_index === s.row_index)?.abnormal
                            ? 'bg-red-100 text-red-600'
                            : 'bg-green-100 text-green-600'
                        ]"
                      >
                        {{
                          sessionResults.find(r => r.session.row_index === s.row_index)?.abnormal
                            ? '⚠ 异常'
                            : '✓ 正常'
                        }}
                      </span>
                    </span>
                  </div>
                  <div class="flex gap-3 mt-0.5 text-xs text-text-light">
                    <span>签到 <strong class="text-text-heading">{{ s.attended_count }}</strong> 人</span>
                    <span v-if="s.expected_count != null">应到 {{ s.expected_count }} 人</span>
                    <span v-if="detectedRowIndexes.has(s.row_index)">
                      识别 <strong class="text-text-heading">{{ sessionResults.find(r => r.session.row_index === s.row_index)?.detected_total }}</strong> 人
                    </span>
                  </div>
                </button>
              </div>
            </div>

            <!-- Right: photo upload for selected session -->
            <div class="flex flex-col gap-3">
              <div v-if="!selectedSession" class="flex items-center justify-center h-32 border border-dashed border-border rounded-xl text-sm text-text-light">
                ← 左侧选择一节课
              </div>
              <template v-else>
                <div class="bg-page-bg rounded-lg px-4 py-3 text-sm">
                  <p class="font-medium text-text-heading">{{ formatSession(selectedSession) }}</p>
                  <p class="text-xs text-text-light mt-0.5">签到 {{ selectedSession.attended_count }} 人</p>
                </div>

                <label class="border-2 border-dashed border-border rounded-xl p-5 text-center cursor-pointer hover:border-accent transition-colors">
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp,image/heic"
                    multiple
                    class="hidden"
                    @change="onPhotoSelect"
                  />
                  <p class="text-sm font-medium text-text-heading">选择该节课照片</p>
                  <p class="text-xs text-text-light mt-1">最多 10 张，JPG/PNG/WebP/HEIC</p>
                </label>

                <div v-if="photos.length > 0" class="flex flex-wrap gap-1.5">
                  <div
                    v-for="(f, i) in photos"
                    :key="i"
                    class="flex items-center gap-1.5 bg-page-bg rounded-lg px-2.5 py-1 text-xs"
                  >
                    <span class="max-w-[140px] truncate text-text-body">{{ f.name }}</span>
                    <button class="text-red-400 hover:text-red-600 font-bold" @click="removePhoto(i)">✕</button>
                  </div>
                </div>

                <Button
                  variant="primary"
                  :disabled="!photos.length"
                  :loading="detecting"
                  @click="runDetect"
                >
                  开始识别
                </Button>
              </template>
            </div>
          </div>
        </div>

        <!-- ── Step 3: Summary ── -->
        <div v-if="step === 'summary'" class="flex flex-col gap-4">
          <div class="flex items-center justify-between">
            <h3 class="text-sm font-bold text-text-heading">核对汇总</h3>
            <Button variant="secondary" size="small" @click="step = 'detect'">← 返回继续核对</Button>
          </div>

          <div v-if="sessionResults.length === 0" class="text-sm text-text-light py-8 text-center">
            暂无核对记录，请先在第②步上传照片
          </div>

          <div v-else class="overflow-x-auto">
            <table class="w-full text-xs">
              <thead class="bg-page-bg">
                <tr>
                  <th class="px-3 py-2 text-left text-text-light font-medium">课程信息</th>
                  <th class="px-3 py-2 text-center text-text-light font-medium">签到人数</th>
                  <th class="px-3 py-2 text-center text-text-light font-medium">照片识别</th>
                  <th class="px-3 py-2 text-center text-text-light font-medium">差值</th>
                  <th class="px-3 py-2 text-center text-text-light font-medium">照片数</th>
                  <th class="px-3 py-2 text-left text-text-light font-medium">状态</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="sr in sessionResults"
                  :key="sr.session.row_index"
                  class="border-t border-border"
                  :class="sr.abnormal ? 'bg-red-50' : ''"
                >
                  <td class="px-3 py-2 text-text-body max-w-[200px]">
                    <p class="font-medium truncate">{{ formatSession(sr.session) }}</p>
                  </td>
                  <td class="px-3 py-2 text-center text-text-heading font-bold">{{ sr.session.attended_count }}</td>
                  <td class="px-3 py-2 text-center text-text-heading font-bold">{{ sr.detected_total }}</td>
                  <td class="px-3 py-2 text-center font-bold" :class="sr.abnormal ? 'text-red-600' : 'text-green-600'">
                    {{ sr.diff > 0 ? '+' : '' }}{{ sr.diff }}
                  </td>
                  <td class="px-3 py-2 text-center text-text-light">{{ sr.results.length }}</td>
                  <td class="px-3 py-2">
                    <span :class="[
                      'px-2 py-0.5 rounded-full text-xs',
                      sr.abnormal ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                    ]">
                      {{ sr.abnormal ? `⚠ 差值超 ±${DIFF_THRESHOLD}` : '✓ 正常' }}
                    </span>
                  </td>
                </tr>
              </tbody>
              <tfoot class="border-t-2 border-border bg-page-bg">
                <tr>
                  <td class="px-3 py-2 text-text-light font-medium">合计（{{ sessionResults.length }} 节）</td>
                  <td class="px-3 py-2 text-center font-bold text-text-heading">
                    {{ sessionResults.reduce((s, r) => s + r.session.attended_count, 0) }}
                  </td>
                  <td class="px-3 py-2 text-center font-bold text-text-heading">
                    {{ sessionResults.reduce((s, r) => s + r.detected_total, 0) }}
                  </td>
                  <td class="px-3 py-2 text-center font-bold" :class="abnormalCount > 0 ? 'text-red-600' : 'text-green-600'">
                    {{ sessionResults.reduce((s, r) => s + r.diff, 0) > 0 ? '+' : '' }}{{ sessionResults.reduce((s, r) => s + r.diff, 0) }}
                  </td>
                  <td colspan="2" class="px-3 py-2 text-xs text-text-light">
                    {{ abnormalCount > 0 ? `${abnormalCount} 处差值异常，建议人工复核` : '全部正常' }}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>

          <!-- Annotated images for abnormal sessions -->
          <div v-if="sessionResults.some(r => r.abnormal)" class="flex flex-col gap-4 mt-2">
            <p class="text-sm font-medium text-red-600">异常节课照片明细</p>
            <div v-for="sr in sessionResults.filter(r => r.abnormal)" :key="sr.session.row_index" class="border border-red-200 rounded-xl overflow-hidden">
              <div class="px-4 py-2 bg-red-50 text-sm font-medium text-red-700">
                {{ formatSession(sr.session) }} — 签到 {{ sr.session.attended_count }} 人 / 识别 {{ sr.detected_total }} 人（差 {{ sr.diff > 0 ? '+' : '' }}{{ sr.diff }}）
              </div>
              <div class="grid grid-cols-2 md:grid-cols-3 gap-2 p-3">
                <div v-for="(r, i) in sr.results" :key="i">
                  <img
                    v-if="r.annotated_image_b64"
                    :src="'data:image/jpeg;base64,' + r.annotated_image_b64"
                    class="w-full rounded"
                    :alt="r.filename"
                  />
                  <p class="text-xs text-text-light mt-0.5 truncate">{{ r.filename }} ({{ r.detected_count }}人)</p>
                </div>
              </div>
            </div>
          </div>
        </div>

      </div>
    </Card>
  </div>
</template>
