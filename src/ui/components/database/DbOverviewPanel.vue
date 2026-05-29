<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { databaseApi, type ConnStatus } from '@/services/databaseApi'
import DbTableDetail from './DbTableDetail.vue'

const props = defineProps<{ connStatus: ConnStatus | null; tables: string[] }>()

// ── state ──
const rowCounts = ref<Record<string, number | null>>({})
const dbComments = ref<Record<string, string>>({})   // from DB information_schema
const aiDescs = ref<Record<string, string>>({})
const userNotes = ref<Record<string, string>>({})
const scanDone = ref(false)
const scanTotal = ref(0)
const scanDoneCount = ref(0)
const commentsLoaded = ref(false)

const searchQuery = ref('')
const activeTag = ref('all')
const viewMode = ref<'grid' | 'detail'>('grid')
const selectedTable = ref('')
const aiAllLoading = ref(false)

// ── localStorage keys ──
const dbKey = computed(() => props.connStatus?.display_name ?? 'db')
function noteKey(t: string) { return `db_table_notes_${dbKey.value}_${t}` }
function aiKey(t: string) { return `db_table_ai_${dbKey.value}_${t}` }

// ── load persisted data ──
function loadPersisted() {
  const descs: Record<string, string> = {}
  const notes: Record<string, string> = {}
  for (const t of props.tables) {
    descs[t] = localStorage.getItem(aiKey(t)) ?? ''
    notes[t] = localStorage.getItem(noteKey(t)) ?? ''
  }
  aiDescs.value = descs
  userNotes.value = notes
}

// ── scan row counts (concurrency 5) ──
async function scanRowCounts() {
  scanDone.value = false
  scanTotal.value = props.tables.length
  scanDoneCount.value = 0
  const counts: Record<string, number | null> = {}

  async function fetchOne(t: string) {
    try {
      const r = await databaseApi.getRowCount(t)
      const val = r.rows[0]?.[0]
      counts[t] = val !== null && val !== undefined ? parseInt(String(val)) : null
    } catch {
      counts[t] = null
    }
    scanDoneCount.value++
    rowCounts.value = { ...counts }
  }

  const CONCURRENCY = 5
  for (let i = 0; i < props.tables.length; i += CONCURRENCY) {
    await Promise.all(props.tables.slice(i, i + CONCURRENCY).map(fetchOne))
  }
  scanDone.value = true
}

async function loadComments() {
  commentsLoaded.value = false
  try {
    dbComments.value = await databaseApi.getTableComments()
  } catch {
    dbComments.value = {}
  } finally {
    commentsLoaded.value = true
  }
}

onMounted(async () => {
  if (props.tables.length === 0) return
  loadPersisted()
  if (props.tables.length > 0) selectedTable.value = props.tables[0]
  await Promise.all([loadComments(), scanRowCounts()])
})

// ── tag auto-classification ──
const TAG_RULES: Record<string, string[]> = {
  user: ['user', 'member', 'student', 'account', 'profile', 'coach', 'teacher', '用户', '学员', '教练'],
  order: ['order', 'pay', 'bill', 'invoice', 'purchase', 'course_pack', '订单', '购买', '支付'],
  log: ['log', 'record', 'history', 'checkin', 'sign', 'track', 'event', '记录', '日志', '签到'],
  config: ['config', 'setting', 'school', 'campus', 'dict', 'type', 'category', '配置', '校区', '字典'],
}

function autoTag(name: string): string {
  const lower = name.toLowerCase()
  for (const [tag, keywords] of Object.entries(TAG_RULES)) {
    if (keywords.some(k => lower.includes(k))) return tag
  }
  return 'other'
}

function isTmpTable(name: string) {
  return /^(fix|tmp|temp|bak|test|backup|old|copy)/i.test(name)
}

// ── filtered & sorted tables ──
const filteredTables = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return props.tables.filter(t => {
    if (activeTag.value !== 'all' && autoTag(t) !== activeTag.value) return false
    if (q && !t.toLowerCase().includes(q)) return false
    return true
  })
})

// ── stats ──
const largestTable = computed(() => {
  let best = { name: '', count: -1 }
  for (const [t, c] of Object.entries(rowCounts.value)) {
    if (c !== null && c > best.count) best = { name: t, count: c }
  }
  return best
})

const notedCount = computed(() =>
  Object.values(aiDescs.value).filter(v => !!v).length +
  Object.values(userNotes.value).filter(v => !!v).length > 0
    ? Object.keys(props.tables.reduce((acc, t) => {
        if (aiDescs.value[t] || userNotes.value[t]) acc[t] = 1
        return acc
      }, {} as Record<string, number>)).length
    : 0
)

function fmtCount(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—'
  if (n >= 10000) return (n / 10000).toFixed(1) + ' 万'
  return n.toLocaleString()
}

function tagCount(tag: string) {
  if (tag === 'all') return props.tables.length
  return props.tables.filter(t => autoTag(t) === tag).length
}

// ── AI 一键解读 ──
async function aiDescribeAll() {
  if (aiAllLoading.value) return
  aiAllLoading.value = true
  const targets = props.tables.filter(t => !aiDescs.value[t])
  for (const t of targets) {
    try {
      const cols = await databaseApi.getColumns(t)
      const res = await databaseApi.describeTable(t, cols)
      aiDescs.value = { ...aiDescs.value, [t]: res.description }
      localStorage.setItem(aiKey(t), res.description)
    } catch { /* skip */ }
  }
  aiAllLoading.value = false
}

const TAG_LABELS: Record<string, string> = {
  all: '全部', user: '👤 用户', order: '📦 订单', log: '📋 日志', config: '⚙️ 配置', other: '其他'
}
</script>

<template>
  <div>
    <!-- Stats row -->
    <div class="grid grid-cols-4 gap-3 mb-4">
      <div class="bg-card-bg border border-border rounded-xl px-4 py-3">
        <div class="text-[11px] text-text-light mb-1">当前数据库</div>
        <div class="text-[14px] font-bold text-text-heading truncate">{{ connStatus?.display_name ?? '—' }}</div>
        <div class="text-[10px] text-text-light mt-0.5 uppercase">{{ connStatus?.db_type }} · {{ connStatus?.connection_type }}</div>
      </div>
      <div class="bg-card-bg border border-border rounded-xl px-4 py-3">
        <div class="text-[11px] text-text-light mb-1">数据表总数</div>
        <div class="text-[22px] font-bold text-text-heading leading-none">{{ tables.length }}</div>
        <div class="text-[10px] text-text-light mt-1">
          {{ scanDone ? '已全部扫描' : `扫描中 ${scanDoneCount}/${scanTotal}…` }}
        </div>
      </div>
      <div class="bg-card-bg border border-border rounded-xl px-4 py-3">
        <div class="text-[11px] text-text-light mb-1">已添加备注</div>
        <div class="text-[22px] font-bold text-text-heading leading-none">{{ notedCount }}</div>
        <div class="flex items-center gap-1.5 mt-1.5">
          <div class="flex-1 h-1 bg-chip rounded-full overflow-hidden">
            <div
              class="h-full bg-accent rounded-full transition-all"
              :style="`width:${tables.length ? Math.round(notedCount / tables.length * 100) : 0}%`"
            />
          </div>
          <span class="text-[10px] text-text-light">{{ tables.length ? Math.round(notedCount / tables.length * 100) : 0 }}%</span>
        </div>
      </div>
      <div class="bg-card-bg border border-border rounded-xl px-4 py-3">
        <div class="text-[11px] text-text-light mb-1">数据量最多</div>
        <div class="text-[13px] font-bold text-text-heading truncate">{{ largestTable.name || '—' }}</div>
        <div class="text-[10px] text-text-light mt-0.5">{{ largestTable.count >= 0 ? fmtCount(largestTable.count) + ' 行' : '扫描中…' }}</div>
      </div>
    </div>

    <!-- Toolbar -->
    <div class="flex items-center gap-2 mb-4 flex-wrap">
      <input
        v-model="searchQuery"
        placeholder="🔍 搜索表名…"
        class="h-[34px] border border-border rounded-lg px-3 text-[12px] bg-card-bg text-text-body outline-none focus:border-accent transition-colors w-[200px]"
      />
      <div class="flex gap-1.5 flex-wrap">
        <button
          v-for="tag in ['all','user','order','log','config']"
          :key="tag"
          @click="activeTag = tag"
          class="px-2.5 py-1 rounded-full text-[11px] border transition-colors"
          :class="activeTag === tag
            ? 'bg-accent text-white border-accent'
            : 'bg-card-bg border-border text-text-body hover:border-accent'"
        >
          {{ TAG_LABELS[tag] }} {{ tagCount(tag) }}
        </button>
      </div>
      <div class="ml-auto flex items-center gap-2">
        <!-- comments status -->
        <span v-if="commentsLoaded && Object.keys(dbComments).length === 0" class="text-[11px] text-text-light">
          暂无数据库备注
        </span>
        <span v-else-if="commentsLoaded" class="text-[11px] text-text-light">
          {{ Object.keys(dbComments).length }} 张表有备注
        </span>
        <!-- view toggle -->
        <div class="flex border border-border rounded-lg overflow-hidden text-[11px]">
          <button
            @click="viewMode = 'grid'"
            class="px-2.5 py-1 transition-colors"
            :class="viewMode === 'grid' ? 'bg-chip text-text-body font-semibold' : 'bg-card-bg text-text-light hover:bg-chip'"
          >⊞ 卡片</button>
          <button
            @click="viewMode = 'detail'"
            class="px-2.5 py-1 border-l border-border transition-colors"
            :class="viewMode === 'detail' ? 'bg-chip text-text-body font-semibold' : 'bg-card-bg text-text-light hover:bg-chip'"
          >☰ 详情</button>
        </div>
        <button
          @click="aiDescribeAll"
          :disabled="aiAllLoading"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] bg-accent text-white hover:bg-accent/90 transition-colors disabled:opacity-60"
        >
          <span>✨</span>
          {{ aiAllLoading ? 'AI 解读中…' : 'AI 一键解读' }}
        </button>
      </div>
    </div>

    <!-- GRID VIEW -->
    <div v-if="viewMode === 'grid'">
      <div v-if="filteredTables.length === 0" class="text-center py-12 text-[13px] text-text-light">
        没有匹配的数据表
      </div>
      <div v-else class="grid grid-cols-3 gap-3 overflow-y-auto" style="max-height: 560px">
        <div
          v-for="t in filteredTables"
          :key="t"
          @click="selectedTable = t; viewMode = 'detail'"
          class="bg-card-bg border border-border rounded-xl p-3.5 cursor-pointer hover:border-accent hover:shadow-sm transition-all group"
        >
          <!-- header -->
          <div class="flex items-start gap-1.5 mb-2">
            <span class="text-[13px] mt-px">⬡</span>
            <span class="text-[12px] font-semibold text-text-heading break-all flex-1 leading-snug">{{ t }}</span>
          </div>
          <!-- meta pills -->
          <div class="flex gap-1.5 mb-2 flex-wrap">
            <span v-if="isTmpTable(t)" class="text-[10px] px-1.5 py-0.5 rounded-full bg-[#FFF0E8] border border-[#D4956A] text-[#9A5530]">⚠️ 疑似临时表</span>
            <span class="text-[10px] px-1.5 py-0.5 rounded-full bg-chip border border-border text-text-light">
              {{ rowCounts[t] !== undefined ? fmtCount(rowCounts[t]) + ' 行' : '…' }}
            </span>
          </div>
          <!-- description: DB comment > AI > user note > empty -->
          <div v-if="dbComments[t]" class="flex items-start gap-1.5 bg-[#EEF3FB] border border-[#B8CCE8] rounded-lg px-2 py-1.5 mb-2">
            <span class="text-[10px] flex-shrink-0">🗒</span>
            <span class="text-[11px] text-[#2a4a8a] leading-relaxed">{{ dbComments[t] }}</span>
          </div>
          <div v-else-if="aiDescs[t]" class="flex items-start gap-1.5 bg-[#F0F5F1] border border-[#C8DCC8] rounded-lg px-2 py-1.5 mb-2">
            <span class="text-[10px] flex-shrink-0">✨</span>
            <span class="text-[11px] text-[#3a6640] leading-relaxed">{{ aiDescs[t] }}</span>
          </div>
          <div v-else-if="userNotes[t]" class="text-[11px] text-text-light mb-2 line-clamp-2 italic">{{ userNotes[t] }}</div>
          <div v-else class="text-[11px] text-placeholder mb-2">点击查看详情 →</div>
        </div>
      </div>
    </div>

    <!-- DETAIL VIEW -->
    <div v-else class="flex gap-3">
      <!-- table list -->
      <div class="w-[240px] flex-shrink-0">
        <div class="bg-card-bg border border-border rounded-xl overflow-hidden" style="max-height:600px">
          <div class="px-3 py-2.5 border-b border-border">
            <input
              v-model="searchQuery"
              placeholder="搜索表名…"
              class="w-full h-7 text-[11px] bg-page-bg border border-border rounded-md px-2 outline-none focus:border-accent"
            />
          </div>
          <div class="overflow-y-auto" style="max-height:540px">
            <div
              v-for="t in filteredTables"
              :key="t"
              @click="selectedTable = t"
              class="flex items-center gap-2 px-3 py-2 cursor-pointer transition-colors border-b border-border/40 last:border-0"
              :class="selectedTable === t ? 'bg-[#E8F0E9] text-[#3a6640]' : 'hover:bg-page-bg text-text-body'"
            >
              <span class="text-[12px] shrink-0">⬡</span>
              <div class="flex-1 min-w-0">
                <div class="text-[11px] font-medium truncate">{{ t }}</div>
                <div v-if="dbComments[t]" class="text-[10px] text-text-light truncate mt-0.5">{{ dbComments[t] }}</div>
              </div>
              <span class="text-[10px] text-text-light flex-shrink-0">{{ fmtCount(rowCounts[t]) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- detail -->
      <div class="flex-1 min-w-0 overflow-y-auto" style="max-height:600px">
        <div v-if="!selectedTable" class="flex items-center justify-center h-40 text-[13px] text-text-light">
          点击左侧表名查看详情
        </div>
        <template v-else>
          <div class="flex items-center gap-2 mb-3">
            <span class="text-[15px] font-bold text-text-heading">⬡ {{ selectedTable }}</span>
            <span class="text-[11px] text-text-light">{{ fmtCount(rowCounts[selectedTable]) }} 行</span>
            <span v-if="isTmpTable(selectedTable)" class="text-[10px] px-1.5 py-0.5 rounded-full bg-[#FFF0E8] border border-[#D4956A] text-[#9A5530]">⚠️ 疑似临时表</span>
          </div>
          <DbTableDetail
            :table-name="selectedTable"
            :conn-status="connStatus"
            :note-storage-key="noteKey(selectedTable)"
            :ai-storage-key="aiKey(selectedTable)"
            :db-comment="dbComments[selectedTable] ?? ''"
          />
        </template>
      </div>
    </div>
  </div>
</template>
