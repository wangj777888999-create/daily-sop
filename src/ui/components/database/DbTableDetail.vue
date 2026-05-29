<script setup lang="ts">
import { ref, watch } from 'vue'
import { databaseApi, type TableColumn, type ConnStatus } from '@/services/databaseApi'

const props = defineProps<{
  tableName: string
  connStatus: ConnStatus | null
  noteStorageKey: string
  aiStorageKey: string
  dbComment?: string   // native DB table comment
}>()

type ColumnWithComment = TableColumn & { comment: string }

const columns = ref<ColumnWithComment[]>([])
const sampleRows = ref<{ columns: string[]; rows: (string | null)[][] } | null>(null)
const aiDesc = ref('')
const note = ref('')
const colsLoading = ref(false)
const sampleLoading = ref(false)
const aiLoading = ref(false)
const noteSaved = ref(false)

watch(() => props.tableName, async (name) => {
  if (!name) return
  columns.value = []
  sampleRows.value = null

  // load note & ai from localStorage
  note.value = localStorage.getItem(props.noteStorageKey) ?? ''
  aiDesc.value = localStorage.getItem(props.aiStorageKey) ?? ''

  // load columns with comments
  colsLoading.value = true
  try {
    columns.value = await databaseApi.getColumnsWithComments(name)
  } catch {
    // fallback to basic columns without comment
    try {
      const basic = await databaseApi.getColumns(name)
      columns.value = basic.map(c => ({ ...c, comment: '' }))
    } catch { columns.value = [] }
  } finally { colsLoading.value = false }

  // load sample
  sampleLoading.value = true
  try {
    const r = await databaseApi.getSampleRows(name)
    sampleRows.value = { columns: r.columns, rows: r.rows }
  } catch { sampleRows.value = null }
  finally { sampleLoading.value = false }
}, { immediate: true })

async function generateAI() {
  if (aiLoading.value || !columns.value.length) return
  aiLoading.value = true
  try {
    const res = await databaseApi.describeTable(props.tableName, columns.value)
    aiDesc.value = res.description
    localStorage.setItem(props.aiStorageKey, res.description)
  } catch (e: any) {
    aiDesc.value = '生成失败：' + (e?.message || '未知错误')
  } finally {
    aiLoading.value = false
  }
}

function saveNote() {
  localStorage.setItem(props.noteStorageKey, note.value)
  noteSaved.value = true
  setTimeout(() => { noteSaved.value = false }, 1500)
}
</script>

<template>
  <div class="flex flex-col gap-3">
    <!-- AI description -->
    <div class="bg-card-bg border border-border rounded-xl p-4">
      <div class="text-[13px] font-bold text-text-heading mb-2.5">表说明</div>

      <!-- DB native comment (highest priority) -->
      <div v-if="dbComment" class="flex items-start gap-2 bg-[#EEF3FB] border border-[#B8CCE8] rounded-lg px-3 py-2.5 mb-2.5">
        <span class="text-[12px] flex-shrink-0">🗒</span>
        <div>
          <div class="text-[10px] text-[#5a70a0] font-semibold mb-0.5">数据库备注</div>
          <div class="text-[12px] text-[#2a4a8a] leading-relaxed">{{ dbComment }}</div>
        </div>
      </div>

      <!-- AI desc -->
      <div v-if="aiDesc" class="flex items-start gap-2 bg-[#F0F5F1] border border-[#C8DCC8] rounded-lg px-3 py-2.5 mb-2">
        <span class="text-[12px] flex-shrink-0">✨</span>
        <div>
          <div class="text-[10px] text-[#4a7050] font-semibold mb-0.5">AI 解读</div>
          <div class="text-[12px] text-[#3a6640] leading-relaxed">{{ aiDesc }}</div>
        </div>
      </div>
      <div v-else-if="!dbComment" class="text-[12px] text-text-light mb-2">暂无 AI 解读</div>
      <button
        @click="generateAI"
        :disabled="aiLoading || colsLoading"
        class="text-[11px] px-3 py-1.5 rounded-lg border border-border bg-chip text-text-body hover:bg-accent-light hover:border-accent hover:text-accent transition-colors disabled:opacity-40"
      >
        {{ aiLoading ? '生成中…' : aiDesc ? '重新生成' : '生成解读' }}
      </button>
    </div>

    <!-- Column structure -->
    <div class="bg-card-bg border border-border rounded-xl p-4">
      <div class="text-[13px] font-bold text-text-heading mb-2.5">字段结构</div>
      <div v-if="colsLoading" class="space-y-1.5">
        <div v-for="i in 5" :key="i" class="h-6 rounded bg-chip animate-pulse" />
      </div>
      <div v-else-if="columns.length === 0" class="text-[12px] text-text-light">无字段数据</div>
      <div v-else>
        <div class="grid text-[10px] font-semibold text-text-light px-1 mb-1" style="grid-template-columns: 14px 1fr 130px 50px 1fr">
          <span></span><span>字段名</span><span>类型</span><span>NN</span><span>备注</span>
        </div>
        <div
          v-for="col in columns"
          :key="col.name"
          class="grid items-center py-1.5 border-b border-border/50 last:border-0 px-1"
          style="grid-template-columns: 14px 1fr 130px 50px 1fr"
        >
          <span class="text-[10px]" :class="col.pk ? 'text-amber-500' : 'text-transparent'">{{ col.pk ? '🔑' : '—' }}</span>
          <span class="text-[12px] font-mono" :class="col.pk ? 'font-semibold text-text-heading' : 'text-text-body'">{{ col.name }}</span>
          <span class="text-[10px] text-text-light">{{ col.type }}</span>
          <span class="text-[10px]" :class="col.notnull ? 'text-text-body' : 'text-placeholder'">{{ col.notnull ? '●' : '—' }}</span>
          <span class="text-[11px] text-text-light truncate" :title="col.comment">{{ col.comment || '' }}</span>
        </div>
      </div>
    </div>

    <!-- Sample data -->
    <div class="bg-card-bg border border-border rounded-xl p-4">
      <div class="text-[13px] font-bold text-text-heading mb-2.5">
        📊 样本数据
        <span class="text-[11px] font-normal text-text-light ml-1">前 5 行</span>
      </div>
      <div v-if="sampleLoading" class="h-20 flex items-center justify-center text-[12px] text-text-light">加载中…</div>
      <div v-else-if="!sampleRows || sampleRows.rows.length === 0" class="text-[12px] text-text-light">暂无数据</div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-[11px] border-collapse">
          <thead>
            <tr class="bg-chip">
              <th
                v-for="col in sampleRows.columns"
                :key="col"
                class="px-2.5 py-1.5 text-left font-semibold text-text-body border-b border-border whitespace-nowrap"
              >{{ col }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, ri) in sampleRows.rows"
              :key="ri"
              :class="ri % 2 === 0 ? 'bg-card-bg' : 'bg-page-bg'"
              class="hover:bg-accent-light/30"
            >
              <td
                v-for="(cell, ci) in row"
                :key="ci"
                class="px-2.5 py-1.5 border-b border-border/40 text-text-body max-w-[160px] truncate"
                :title="cell ?? ''"
              >
                <span v-if="cell === null" class="text-placeholder italic text-[10px]">NULL</span>
                <span v-else>{{ cell }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- My note -->
    <div class="bg-card-bg border border-border rounded-xl p-4">
      <div class="text-[13px] font-bold text-text-heading mb-2.5">📝 我的备注</div>
      <textarea
        v-model="note"
        rows="3"
        placeholder="记录你对这张表的理解，方便日后查阅…"
        class="w-full bg-page-bg border border-border rounded-lg px-3 py-2 text-[12px] text-text-body outline-none resize-none focus:border-accent transition-colors"
      />
      <div class="flex justify-end mt-2">
        <button
          @click="saveNote"
          class="text-[11px] px-3 py-1.5 rounded-lg bg-accent text-white hover:bg-accent/90 transition-colors"
        >
          {{ noteSaved ? '已保存 ✓' : '保存备注' }}
        </button>
      </div>
    </div>
  </div>
</template>
