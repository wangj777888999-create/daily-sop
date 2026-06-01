<script setup lang="ts">
import type { School } from '@/services/campusReportApi'
defineProps<{ school: School }>()
</script>

<template>
  <div class="h-full flex flex-col">
    <div class="grid grid-cols-2 gap-3.5 flex-1 min-h-0">
      <div
        v-for="chart in [
          { title: '性别分布', icon: '◑', note: '饼图' },
          { title: '月度上课人次', icon: '▦', note: '柱状图' },
          { title: '月度到课率', icon: '╱', note: '折线图' },
          { title: '教练上课情况', icon: '▤', note: '横向柱状图' },
        ]"
        :key="chart.title"
        class="bg-card-bg border border-border rounded-xl p-4 flex flex-col"
      >
        <div class="flex items-center justify-between mb-3">
          <div class="text-[13px] font-medium text-text-heading">{{ chart.title }}</div>
          <span class="text-[10px] text-text-light border border-border rounded px-1.5 py-0.5">{{ chart.note }}</span>
        </div>
        <div class="flex-1 flex flex-col items-center justify-center gap-2 text-center border border-dashed border-border rounded-lg bg-page-bg">
          <span class="text-3xl text-placeholder-dk">{{ chart.icon }}</span>
          <div class="text-[11px] text-text-light">SQL 待配置</div>
          <div class="text-[10px] text-text-light/70">确定查询语句后此图表将自动渲染</div>
        </div>
      </div>
    </div>
  </div>
</template>
