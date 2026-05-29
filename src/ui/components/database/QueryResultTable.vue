<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import type { QueryResult } from '@/services/databaseApi'

const props = defineProps<{ result: QueryResult }>()

const PAGE_SIZE_OPTIONS = [50, 100, 200, 500]
const pageSize = ref(100)
const currentPage = ref(1)

const showExportModal = ref(false)
const exportFilename = ref('查询结果')
const filenameInput = ref<HTMLInputElement | null>(null)

const totalRows = computed(() => props.result.rows.length)
const totalPages = computed(() => Math.max(1, Math.ceil(totalRows.value / pageSize.value)))

const pagedRows = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return props.result.rows.slice(start, start + pageSize.value)
})

const pageNumbers = computed(() => {
  const total = totalPages.value
  const cur = currentPage.value
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const pages: (number | '…')[] = [1]
  if (cur > 3) pages.push('…')
  for (let p = Math.max(2, cur - 1); p <= Math.min(total - 1, cur + 1); p++) pages.push(p)
  if (cur < total - 2) pages.push('…')
  pages.push(total)
  return pages
})

function setPage(p: number | '…') {
  if (typeof p === 'number') currentPage.value = p
}

function onPageSizeChange() {
  currentPage.value = 1
}

async function openExportModal() {
  showExportModal.value = true
  await nextTick()
  filenameInput.value?.select()
}

function doExport() {
  const { columns, rows } = props.result
  const escape = (v: string | null) => `"${(v ?? '').replace(/"/g, '""')}"`
  const lines = [columns.join(','), ...rows.map(r => r.map(escape).join(','))]
  const blob = new Blob(['﻿' + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${exportFilename.value.trim() || '查询结果'}.csv`
  a.click()
  URL.revokeObjectURL(url)
  showExportModal.value = false
}
</script>

<template>
  <div>
    <!-- toolbar -->
    <div class="flex items-center gap-2 mb-2 shrink-0">
      <span class="text-[11px] text-text-light">
        共 {{ totalRows }} 行{{ result.truncated ? '（已截断至 20000 行）' : '' }}
      </span>
      <div class="ml-auto flex items-center gap-2">
        <span class="text-[10px] text-text-light">每页</span>
        <select
          v-model="pageSize"
          @change="onPageSizeChange"
          class="text-[11px] bg-chip border border-border rounded px-1.5 py-0.5 text-text-body outline-none cursor-pointer"
        >
          <option v-for="n in PAGE_SIZE_OPTIONS" :key="n" :value="n">{{ n }}</option>
        </select>
        <button
          @click="openExportModal"
          class="flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] bg-chip border border-border text-text-body hover:bg-accent-light hover:border-accent hover:text-accent transition-colors"
        >
          ↓ 导出 CSV
        </button>
      </div>
    </div>

    <!-- table -->
    <div class="overflow-auto" style="max-height: 480px; min-height: 120px">
      <table class="w-full text-[11px] border-collapse">
        <thead class="sticky top-0 z-10">
          <tr class="bg-chip">
            <th class="px-2.5 py-[6px] text-left font-semibold text-text-light border-b border-border w-10 whitespace-nowrap">#</th>
            <th
              v-for="col in result.columns"
              :key="col"
              class="px-2.5 py-[6px] text-left font-semibold text-text-body border-b border-border whitespace-nowrap"
            >{{ col }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, ri) in pagedRows"
            :key="ri"
            :class="ri % 2 === 0 ? 'bg-card-bg' : 'bg-page-bg'"
            class="hover:bg-accent-light/40 transition-colors"
          >
            <td class="px-2.5 py-1.5 border-b border-border/50 text-placeholder text-[10px] text-right">
              {{ (currentPage - 1) * pageSize + ri + 1 }}
            </td>
            <td
              v-for="(cell, ci) in row"
              :key="ci"
              class="px-2.5 py-1.5 border-b border-border/50 text-text-body max-w-[200px] truncate"
              :title="cell ?? ''"
            >
              <span v-if="cell === null" class="text-placeholder italic">NULL</span>
              <span v-else>{{ cell }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- pagination -->
    <div v-if="totalPages > 1" class="flex items-center justify-center gap-1 pt-2.5 shrink-0">
      <button
        @click="currentPage = Math.max(1, currentPage - 1)"
        :disabled="currentPage === 1"
        class="px-2 py-1 rounded text-[11px] border border-border text-text-body disabled:opacity-30 hover:bg-chip transition-colors"
      >‹</button>
      <button
        v-for="p in pageNumbers"
        :key="p"
        @click="setPage(p)"
        :disabled="p === '…'"
        class="px-2.5 py-1 rounded text-[11px] border transition-colors"
        :class="p === currentPage
          ? 'bg-accent text-white border-accent'
          : p === '…' ? 'border-transparent text-text-light cursor-default'
          : 'border-border text-text-body hover:bg-chip'"
      >{{ p }}</button>
      <button
        @click="currentPage = Math.min(totalPages, currentPage + 1)"
        :disabled="currentPage === totalPages"
        class="px-2 py-1 rounded text-[11px] border border-border text-text-body disabled:opacity-30 hover:bg-chip transition-colors"
      >›</button>
    </div>
  </div>

  <!-- export modal -->
  <Teleport to="body">
    <div
      v-if="showExportModal"
      class="fixed inset-0 z-50 flex items-center justify-center"
      style="background: rgba(61,53,48,0.35); backdrop-filter: blur(2px)"
      @click.self="showExportModal = false"
    >
      <div
        class="w-[360px] rounded-xl border border-border overflow-hidden"
        style="background: #FEFCF8; box-shadow: 0 20px 60px rgba(61,53,48,0.18), 0 4px 12px rgba(61,53,48,0.1)"
      >
        <div class="flex items-center gap-2 px-5 py-4 border-b border-border">
          <span class="text-[15px] font-bold text-text-heading">导出 CSV</span>
          <button
            class="ml-auto text-text-light hover:text-text-body w-6 h-6 flex items-center justify-center rounded hover:bg-chip"
            @click="showExportModal = false"
          >✕</button>
        </div>

        <div class="px-5 py-4">
          <div class="text-[11px] font-semibold text-text-body mb-1.5">文件名</div>
          <div class="flex items-center border border-border rounded-lg overflow-hidden focus-within:border-accent transition-colors">
            <input
              ref="filenameInput"
              v-model="exportFilename"
              class="flex-1 px-3 py-2 text-[13px] text-text-body bg-transparent outline-none"
              placeholder="输入文件名"
              @keydown.enter="doExport"
            />
            <span class="pr-3 text-[12px] text-text-light">.csv</span>
          </div>
          <div class="text-[10px] text-text-light mt-1.5">共 {{ totalRows }} 行将全部导出</div>
        </div>

        <div class="flex items-center justify-end gap-2 px-5 py-4 border-t border-border">
          <button
            class="px-4 py-1.5 rounded-lg text-[13px] border border-border text-text-body hover:bg-chip transition-colors"
            @click="showExportModal = false"
          >取消</button>
          <button
            class="px-4 py-1.5 rounded-lg text-[13px] bg-accent text-white hover:bg-accent/90 transition-colors"
            @click="doExport"
          >下载</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
