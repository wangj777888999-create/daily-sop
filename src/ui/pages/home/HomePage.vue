<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Card from '@/ui/components/common/Card.vue'
import Button from '@/ui/components/common/Button.vue'
import Chip from '@/ui/components/common/Chip.vue'
import MetricCard from '@/ui/components/common/MetricCard.vue'
import RowTitle from '@/ui/components/common/RowTitle.vue'
import WBox from '@/ui/components/common/WBox.vue'
import { useKnowledgeStore } from '@/stores/knowledge'

const router = useRouter()
const kbStore = useKnowledgeStore()
const viewMode = ref<'cards' | 'dashboard'>('cards')

onMounted(async () => {
  await kbStore.loadDocuments()
})

const services = [
  { icon: '◈', name: '工具箱', desc: '实用工具集合，课时费计算、数据分析等', color: '#5B8F7A', tag: '工具', path: '/toolbox' },
  { icon: '✦', name: '政策报告撰写', desc: '基于知识库参考文档，AI 辅助撰写政策与报告', color: '#3A7FC1', tag: 'AI', path: '/policy' },
  { icon: '◗', name: '个人知识库', desc: '存储内部资料，RAG 检索增强生成', color: '#C17F3A', tag: `文档 ${kbStore.documentCount}`, path: '/knowledge' },
]

const recentTasks = [
  ...(kbStore.documents.length > 0 ? [{ title: `知识库：${kbStore.documents.length} 篇文档已索引`, time: '现在', color: '#C17F3A' }] : []),
  { title: '工具箱：课时费计算器可用', time: '现在', color: '#5B8F7A' },
]

const getIconBg = (color: string) => color + '15'
</script>

<template>
  <div>
    <div class="flex justify-end mb-4">
      <div class="flex gap-1">
        <Chip :active="viewMode === 'cards'" @click="viewMode = 'cards'">卡片视图</Chip>
        <Chip :active="viewMode === 'dashboard'" @click="viewMode = 'dashboard'">仪表盘</Chip>
      </div>
    </div>

    <template v-if="viewMode === 'cards'">
      <div class="flex items-center justify-between mb-5">
        <div>
          <h1 class="text-[20px] font-bold text-text-heading">早上好</h1>
          <p class="text-[13px] text-text-light mt-0.5">欢迎使用智能工作台</p>
        </div>
        <div class="flex gap-2">
          <Button variant="secondary" icon="📋" @click="router.push('/knowledge')">知识库</Button>
          <Button variant="primary" icon="＋" @click="router.push('/toolbox')">打开工具箱</Button>
        </div>
      </div>

      <div class="flex gap-3 mb-5">
        <MetricCard label="本月分析次数" value="3" />
        <MetricCard label="生成报告" value="0" />
        <MetricCard label="知识库文档" :value="kbStore.documentCount || '-'" />
        <MetricCard label="本周使用时长" value="-" />
      </div>

      <RowTitle label="核心功能入口" />
      <div class="grid grid-cols-3 gap-3-1/2 mt-2">
        <Card
          v-for="(service, i) in services"
          :key="i"
          :hoverable="true"
          class="flex flex-col gap-2.5 cursor-pointer"
          @click="router.push(service.path)"
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
            <MetricCard label="本月分析次数" value="3" />
            <MetricCard label="报告生成" value="0" />
            <MetricCard label="知识库文档" :value="kbStore.documentCount || '-'" />
          </div>

          <Card class="flex-1 flex flex-col">
            <RowTitle label="使用趋势" action="切换周期 ▾" />
            <WBox label="" class="flex-1 min-h-[160px]" />
          </Card>

          <Card>
            <RowTitle label="近期任务" action="查看全部" />
            <div v-for="(task, i) in recentTasks" :key="i" class="flex items-center gap-2 py-2 border-b border-border last:border-b-0">
              <div class="w-2 h-2 rounded-full flex-shrink-0" :style="{ backgroundColor: task.color }" />
              <span class="text-[12px] text-text-body">{{ task.title }}</span>
              <span class="ml-auto text-[10px] text-text-light">{{ task.time }}</span>
            </div>
          </Card>
        </div>

        <div class="w-64 flex flex-col gap-3.5">
          <Card>
            <RowTitle label="快速入口" />
            <div class="space-y-1.5">
              <Button variant="secondary" style="width: 100%; font-size: 11px" @click="router.push('/knowledge')">📂 打开知识库</Button>
              <Button variant="secondary" style="width: 100%; font-size: 11px" @click="router.push('/toolbox')">◈ 打开工具箱</Button>
              <Button variant="secondary" style="width: 100%; font-size: 11px" @click="router.push('/policy')">✍️ 撰写报告</Button>
            </div>
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
