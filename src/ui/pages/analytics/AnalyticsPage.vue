<script setup lang="ts">
import { ref } from 'vue'
import Card from '@/ui/components/common/Card.vue'
import Button from '@/ui/components/common/Button.vue'
import Chip from '@/ui/components/common/Chip.vue'
import MetricCard from '@/ui/components/common/MetricCard.vue'
import RowTitle from '@/ui/components/common/RowTitle.vue'
import WBox from '@/ui/components/common/WBox.vue'

const viewMode = ref<'charts' | 'chat'>('charts')

const metrics: Array<{
  label: string
  value: string
  delta?: number
}> = []

const charts: Array<{
  title: string
  subtitle: string
}> = []

const chatMessages: Array<{
  role: string
  content: string
}> = []

const quickLabels: string[] = []
</script>

<template>
  <div class="flex flex-col h-full">
    <div class="flex items-center gap-2 mb-3.5">
      <Button variant="secondary" icon="📂">加载数据集</Button>
      <div class="ml-auto flex gap-1.5">
        <Button variant="secondary" size="small">🔄 刷新</Button>
        <Button variant="primary" size="small" icon="📤">导出报告</Button>
      </div>
    </div>

    <div class="flex gap-2.5 mb-3.5">
      <MetricCard
        v-for="m in metrics"
        :key="m.label"
        :label="m.label"
        :value="m.value"
        :delta="m.delta"
      />
    </div>

    <div class="flex gap-2 mb-3">
      <Chip :active="viewMode === 'charts'" @click="viewMode = 'charts'">图表仪表盘</Chip>
      <Chip :active="viewMode === 'chat'" @click="viewMode = 'chat'">对话模式</Chip>
    </div>

    <template v-if="viewMode === 'charts'">
      <div class="grid grid-cols-2 gap-3.5 flex-1 min-h-0">
        <Card v-for="chart in charts" :key="chart.title" class="flex flex-col">
          <RowTitle :label="chart.title" action="配置图表 ⚙" />
          <WBox :label="chart.subtitle" class="flex-1 min-h-[120px]" />
        </Card>
      </div>
    </template>

    <template v-else>
      <div class="flex gap-3.5 flex-1 min-h-0">
        <div class="w-[300px] flex-shrink-0 flex flex-col gap-3">
          <Card>
            <RowTitle label="数据源" />
            <WBox label="拖拽上传\nExcel / CSV / JSON" class="w-full h-[76px] mb-2" />
            <div class="flex gap-1.5">
              <Button size="small" variant="secondary">数据库</Button>
              <Button size="small" variant="secondary" @click="$router.push('/knowledge')">知识库</Button>
            </div>
          </Card>

          <Card class="flex-1">
            <RowTitle label="数据概览" />
          </Card>
        </div>

        <Card class="flex-1 flex flex-col min-h-0">
          <RowTitle label="分析结果" />
          <div class="flex-1 overflow-y-auto space-y-2.5">
            <template v-for="(msg, i) in chatMessages" :key="i">
              <div
                v-if="msg.role === 'user'"
                class="bg-page-bg border border-border rounded-lg px-2.5 py-2 text-[11px] text-text-light"
              >
                {{ msg.content }}
              </div>
              <div
                v-else
                class="bg-accent-light border border-accent rounded-lg px-[11px] py-2 text-[11px] text-text-body"
              >
                {{ msg.content }}
              </div>
            </template>
          </div>

          <div class="mt-3">
            <div class="flex gap-2 mb-1.5">
              <div class="flex-1 bg-page-bg border border-border rounded-lg px-3 py-2 text-[12px] text-text-light">
                用自然语言提问，例如："找出增长最快的产品线"
              </div>
              <Button variant="primary">分析</Button>
            </div>
            <div class="flex gap-1 flex-wrap">
              <Chip v-for="l in quickLabels" :key="l" style="font-size: 10px">{{ l }}</Chip>
            </div>
          </div>
        </Card>
      </div>
    </template>
  </div>
</template>
