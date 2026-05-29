<script setup lang="ts">
import { ref, watch } from 'vue'
import { databaseApi } from '@/services/databaseApi'
import type { QueryResult } from '@/services/databaseApi'
import Button from '@/ui/components/common/Button.vue'

// ── 月份工具 ──────────────────────────────────────────────────
function monthStr(y: number, m: number) {
  return `${y}-${String(m).padStart(2, '0')}`
}
function getLastDay(y: number, m: number): string {
  const last = new Date(y, m, 0).getDate()
  return `${monthStr(y, m)}-${String(last).padStart(2, '0')}`
}
function replaceSqlMonth(sql: string, y: number, m: number): string {
  const ms = monthStr(y, m)
  let result = sql.replace(/'(\d{4}-\d{2})'/g, `'${ms}'`)
  result = result.replace(
    /BETWEEN\s+'(\d{4}-\d{2}-\d{2})'\s+AND\s+'(\d{4}-\d{2}-\d{2})'/gi,
    `BETWEEN '${ms}-01' AND '${getLastDay(y, m)}'`
  )
  return result
}

// ── 默认 SQL ──────────────────────────────────────────────────
const DEFAULT_SQL = `SELECT t.*,
       concat(t.start_time, '-', t.end_time) AS course_time_interval,
       gu.name AS coach_name
FROM (
    SELECT
        IF(gsp0.course_type ='school', '学校学员', '球馆学员') AS student_type,
        gs.student_name AS student_name,
        IFNULL(gss.school_name, gsdium.stadium_name) AS order_type,
        if(gsp1.property_type = 'course_pack', gsp1.course_name, NULL) AS course_pack_name,
        if(gsp1.property_type = 'course_pack', gsp1.original_amount, gsp0.original_amount) AS original_amount,
        if(gsp1.property_type = 'course_pack', gsp1.reduction_amount, gsp0.reduction_amount) AS reduction_amount,
        if(gsp1.property_type = 'course_pack', gsp1.pay_amount, gsp0.pay_amount) AS pay_amount,
        if(gsp1.property_type = 'course_pack', gsp1.refunded_amount, gsp0.refunded_amount) AS refunded_amount,
        if(gsp1.property_type = 'course_pack', gsp1.service_amount, gsp0.service_amount) AS service_amount,
        IF(gc.class_id IS NOT NULL, gc.class_id, gsc.id) AS course_id,
        IF(gc.class_id IS NOT NULL, gc.\`name\`, gsc.\`name\`) AS course_name,
        gscn.unit_price,
        gsp0.purchased_num,
        gsp0.give_num,
        (
            SELECT COUNT(1)
            FROM gs_student_property_detail AS lid
            WHERE lid.del_flag = 0
              AND lid.student_property_id = gsp0.id
              AND lid.detail_type = 'out'
              AND lid.business_type = 'course_use'
              AND lid.id <= detail.id
        ) AS used_num,
        (
            SELECT sum(amount)
            FROM gs_student_property_detail AS lid
            WHERE lid.del_flag = 0
              AND lid.student_property_id = gsp0.id
              AND lid.detail_type = 'out'
              AND lid.business_type = 'course_use'
              AND lid.id <= detail.id
        ) AS used_amount,
        detail.amount,
        IF(gsp0.\`status\` = 1, gsp0.surplus_num, 0) AS surplus_num,
        gs_coach_timetable_student.course_type,
        if(gs_coach_timetable_student.course_type = "gs_class", gct.class_date, gsct.class_date) AS class_date,
        if(gs_coach_timetable_student.course_type = "gs_class", gct.start_time, gsct.start_time) AS start_time,
        if(gs_coach_timetable_student.course_type = "gs_class", gct.end_time, gsct.end_time) AS end_time,
        if(gs_coach_timetable_student.course_type = "gs_class", gct.coach_id, gsct.coach_id) AS coach_id
    FROM
        gs_student_property AS gsp
        JOIN gs_student_property AS gsp0 ON gsp.id = gsp0.id
        JOIN gs_student AS gs ON gs.student_id = gsp.student_id
        LEFT JOIN gs_class AS gc ON gc.class_id = gsp.course_id AND gsp.course_type ='school'
        LEFT JOIN gs_school AS gss ON gss.id = gc.school_id
        LEFT JOIN gs_stadium_course AS gsc ON gsc.id = gsp.course_id AND gsp.course_type ='stadium'
        LEFT JOIN gs_stadium gsdium ON gsc.stadium_id = gsdium.stadium_id
        LEFT JOIN gs_student_property gsp1 ON gsp.root_p_id = gsp1.id
        LEFT JOIN gs_student_property_detail AS detail ON detail.student_property_id = gsp.id AND detail.detail_type = 'out' AND detail.business_type = 'course_use' AND detail.del_flag = 0
        LEFT JOIN gs_coach_timetable_student ON gs_coach_timetable_student.id = detail.business_id
        LEFT JOIN gs_stadium_course_timetable AS gsct ON gsct.id = gs_coach_timetable_student.coach_timetable_id AND gs_coach_timetable_student.course_type = 'gs_stadium'
        LEFT JOIN gs_coach_timetable AS gct ON gct.id = gs_coach_timetable_student.coach_timetable_id AND gs_coach_timetable_student.course_type = 'gs_class'
        LEFT JOIN gs_student_course_num gscn ON gscn.id = gs_coach_timetable_student.course_num_id
    WHERE
        gsp.property_type = 'course'
        AND gsp.del_flag = 0
        AND detail.detail_type = 'out'
        AND gsp0.course_type != 'school'
) AS t
LEFT JOIN gs_user AS gu ON gu.user_id = t.coach_id
WHERE t.class_date BETWEEN '2026-04-01' AND '2026-04-30'
ORDER BY t.class_date DESC, t.student_name ASC`

// ── 状态 ──────────────────────────────────────────────────────
const year = ref(new Date().getMonth() === 0 ? new Date().getFullYear() - 1 : new Date().getFullYear())
const month = ref(new Date().getMonth() === 0 ? 12 : new Date().getMonth())

const sql = ref(replaceSqlMonth(DEFAULT_SQL, year.value, month.value))
const sqlEditing = ref(false)
const sqlDraft = ref('')

const loading = ref(false)
const errorMsg = ref('')
const result = ref<QueryResult | null>(null)

const monthOptions = Array.from({ length: 12 }, (_, i) => ({ value: i + 1, label: `${i + 1}月` }))
const yearOptions = [2024, 2025, 2026, 2027].map(y => ({ value: y, label: `${y}年` }))

// 月份变化时自动同步 SQL 日期
watch([year, month], ([y, m]) => {
  sql.value = replaceSqlMonth(sql.value, y, m)
  if (sqlEditing.value) sqlDraft.value = replaceSqlMonth(sqlDraft.value, y, m)
})

function openEdit() { sqlDraft.value = sql.value; sqlEditing.value = true }
function saveEdit() { sql.value = sqlDraft.value; sqlEditing.value = false }
function cancelEdit() { sqlEditing.value = false }

// ── 查询 ──────────────────────────────────────────────────────
async function runQuery() {
  loading.value = true
  errorMsg.value = ''
  result.value = null
  try {
    result.value = await databaseApi.query(sql.value, 50000)
  } catch (e: any) {
    errorMsg.value = e.message || '查询失败'
  } finally {
    loading.value = false
  }
}

// ── 导出 CSV ──────────────────────────────────────────────────
function exportCsv() {
  if (!result.value) return
  const { columns, rows } = result.value
  const escape = (v: string | null) => {
    if (v === null || v === undefined) return ''
    const s = String(v)
    return s.includes(',') || s.includes('"') || s.includes('\n')
      ? `"${s.replace(/"/g, '""')}"`
      : s
  }
  const lines = [
    columns.map(escape).join(','),
    ...rows.map(r => r.map(escape).join(','))
  ]
  const blob = new Blob(['﻿' + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `球馆财务明细_${monthStr(year.value, month.value)}.csv`
  a.click()
  URL.revokeObjectURL(a.href)
}
</script>

<template>
  <div class="min-h-screen bg-pageBg p-6 space-y-5">

    <!-- 标题 -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-xl font-semibold text-text-heading">球馆财务明细报表</h1>
        <p class="text-sm text-text-light mt-0.5">按月查询球馆学员上课与财务全量数据，以 SQL 字段为准</p>
      </div>
      <Button
        v-if="result"
        variant="secondary"
        size="small"
        @click="exportCsv"
      >
        ↓ 导出 CSV
      </Button>
    </div>

    <!-- 月份选择 + 查询 -->
    <div class="bg-white rounded-xl border border-border p-5 space-y-4">
      <div class="flex items-center gap-3 flex-wrap">
        <span class="text-sm font-medium text-text-heading">选择月份</span>
        <select
          v-model="year"
          class="border border-border rounded-lg px-3 py-1.5 text-sm text-text-heading bg-white focus:outline-none focus:ring-2 focus:ring-accent/30"
        >
          <option v-for="y in yearOptions" :key="y.value" :value="y.value">{{ y.label }}</option>
        </select>
        <select
          v-model="month"
          class="border border-border rounded-lg px-3 py-1.5 text-sm text-text-heading bg-white focus:outline-none focus:ring-2 focus:ring-accent/30"
        >
          <option v-for="m in monthOptions" :key="m.value" :value="m.value">{{ m.label }}</option>
        </select>
        <span class="text-xs text-text-light">切换月份，SQL 日期自动同步</span>
      </div>

      <!-- SQL 卡片 -->
      <div class="border border-border rounded-lg overflow-hidden">
        <div class="flex items-center justify-between px-4 py-2.5 bg-chip/40">
          <div class="flex items-center gap-2">
            <span class="text-xs font-semibold bg-accent text-white px-2 py-0.5 rounded-full">SQL</span>
            <span class="text-sm font-medium text-text-heading">查询语句</span>
            <span class="text-xs text-text-light">· 查询 {{ year }}-{{ String(month).padStart(2,'0') }} 月数据</span>
          </div>
          <template v-if="!sqlEditing">
            <button
              class="text-xs text-accent hover:underline font-medium"
              @click="openEdit"
            >编辑</button>
          </template>
          <template v-else>
            <div class="flex gap-2">
              <button class="text-xs text-text-light hover:text-text-heading" @click="cancelEdit">取消</button>
              <button class="text-xs text-accent font-semibold hover:underline" @click="saveEdit">保存</button>
            </div>
          </template>
        </div>
        <div v-if="sqlEditing" class="p-3">
          <textarea
            v-model="sqlDraft"
            rows="12"
            class="w-full font-mono text-xs text-text-heading bg-white border border-border rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-accent/30 resize-y"
          />
        </div>
      </div>

      <!-- 查询按钮 -->
      <div class="flex items-center gap-3">
        <Button :disabled="loading" @click="runQuery">
          {{ loading ? '查询中…' : '▶ 执行查询' }}
        </Button>
        <span v-if="result" class="text-xs text-text-light">
          共 <span class="font-semibold text-text-heading">{{ result.row_count.toLocaleString() }}</span> 条记录
          <span v-if="result.truncated" class="text-amber-600 ml-1">（已截断，最多 50000 条）</span>
        </span>
      </div>

      <!-- 错误 -->
      <div v-if="errorMsg" class="text-sm text-red-500 bg-red-50 rounded-lg px-4 py-3">{{ errorMsg }}</div>
    </div>

    <!-- 结果表格 -->
    <div v-if="result && result.columns.length" class="bg-white rounded-xl border border-border overflow-hidden">
      <div class="flex items-center justify-between px-5 py-3 border-b border-border bg-chip/20">
        <span class="text-sm font-semibold text-text-heading">
          查询结果 · {{ result.columns.length }} 列 · {{ result.row_count.toLocaleString() }} 行
        </span>
      </div>
      <div class="overflow-auto max-h-[60vh]">
        <table class="w-full text-xs border-collapse min-w-max">
          <thead class="sticky top-0 z-10">
            <tr class="bg-chip/60">
              <th
                v-for="col in result.columns"
                :key="col"
                class="px-3 py-2 text-left font-semibold text-text-body whitespace-nowrap border-b border-border"
              >{{ col }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, ri) in result.rows"
              :key="ri"
              class="hover:bg-chip/30 transition-colors"
              :class="ri % 2 === 0 ? 'bg-white' : 'bg-pageBg/50'"
            >
              <td
                v-for="(cell, ci) in row"
                :key="ci"
                class="px-3 py-1.5 text-text-heading whitespace-nowrap border-b border-border/50 max-w-[200px] truncate"
                :title="cell ?? ''"
              >{{ cell ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

  </div>
</template>
