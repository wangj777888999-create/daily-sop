<script setup lang="ts">
import { ref } from 'vue'
import Card from '@/ui/components/common/Card.vue'
import Button from '@/ui/components/common/Button.vue'
import Chip from '@/ui/components/common/Chip.vue'
import MetricCard from '@/ui/components/common/MetricCard.vue'
import RowTitle from '@/ui/components/common/RowTitle.vue'
import WBox from '@/ui/components/common/WBox.vue'

const viewMode = ref<'cards' | 'dashboard'>('cards')

const services: Array<{
  icon: string
  name: string
  desc: string
  color: string
  tag: string
}> = []

const recentTasks: Array<{
  title: string
  time: string
  color: string
}> = []

const quickActions: Array<{
  icon: string
  label: string
}> = []

const getIconBg = (_color: string) => 'transparent'
</script>

<template>
  <div>
    <div class="flex justify-end mb-4">
      <div class="flex gap-1">
        <Chip
          :active="viewMode === 'cards'"
          @click="viewMode = 'cards'"
        >
          卡片视图
        </Chip>
        <Chip
          :active="viewMode === 'dashboard'"
          @click="viewMode = 'dashboard'"
        >
          仪表盘
        </Chip>
      </div>
    </div>

    <template v-if="viewMode === 'cards'">
      <div class="flex items-center justify-between mb-5">
        <div>
          <h1 class="text-[20px] font-bold text-text-heading">早上好</h1>
          <p class="text-[13px] text-text-light mt-0.5">欢迎使用智能工作台</p>
        </div>
        <div class="flex gap-2">
          <Button variant="secondary" icon="📋">查看任务</Button>
          <Button variant="primary" icon="＋">新建分析</Button>
        </div>
      </div>

      <div class="flex gap-3 mb-5">
        <MetricCard label="本月分析次数" value="-" />
        <MetricCard label="生成报告" value="-" />
        <MetricCard label="知识库文档" value="-" />
        <MetricCard label="本周使用时长" value="-" />
      </div>

      <RowTitle label="核心功能入口" />
      <div class="grid grid-cols-3 gap-3-1/2 mt-2">
        <Card
          v-for="(service, i) in services"
          :key="i"
          :hoverable="true"
          class="flex flex-col gap-2.5"
        >
          <div class="flex items-start justify-between">
            <div
              class="w-10 h-10 rounded-[11px] flex items-center justify-center text-xl"
              :style="{ backgroundColor: getIconBg(service.color), color: service.color }"
            >
              {{ service.icon }}
            </div>
            <span
              v-if="service.tag"
              class="text-[9px] font-bold px-1.5 py-0.5 rounded-full"
              :style="{ backgroundColor: getIconBg(service.color), color: service.color }"
            >
              {{ service.tag }}
            </span>
          </div>
          <h3 class="text-[14px] font-bold text-text-heading">{{ service.name }}</h3>
          <p class="text-[11px] text-text-light leading-relaxed flex-1">{{ service.desc }}</p>
          <span class="text-[11px] font-semibold mt-auto" :style="{ color: service.color }">
            立即使用 →
          </span>
        </Card>
      </div>
    </template>

    <template v-else>
      <div class="flex gap-4 h-full">
        <div class="flex-1 flex flex-col gap-3.5">
          <div class="flex gap-2.5">
            <MetricCard label="本月分析次数" value="-" />
            <MetricCard label="报告生成" value="-" />
            <MetricCard label="知识库文档" value="-" />
          </div>

          <Card class="flex-1 flex flex-col">
            <RowTitle label="使用趋势" action="切换周期 ▾" />
            <WBox label="" class="flex-1 min-h-[160px]" />
          </Card>

          <Card>
            <RowTitle label="近期任务" action="查看全部" />
          </Card>
        </div>

        <div class="w-64 flex flex-col gap-3.5">
          <Card>
            <RowTitle label="快速入口" />
          </Card>

          <Card class="flex-1 flex flex-col">
            <RowTitle label="本周日历" />
            <WBox label="" class="w-full h-[120px] mb-2" />
            <div>
              <div class="text-[10px] text-text-light mb-1.5">今日日程</div>
            </div>
          </Card>
        </div>
      </div>
    </template>
  </div>
</template>
