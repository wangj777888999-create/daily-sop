<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import Card from '@/ui/components/common/Card.vue'
import Chip from '@/ui/components/common/Chip.vue'
import type { ToolCategory } from '@/types/toolbox'
import { tools } from '@/data/tools'

const router = useRouter()

type Tab = '全部' | ToolCategory
const TABS: Tab[] = ['全部', '校内', '校外', '通用']
const activeTab = ref<Tab>('全部')

const enabledTools = tools.filter(t => t.enabled !== false)

const filteredTools = computed(() =>
  activeTab.value === '全部'
    ? enabledTools
    : enabledTools.filter(t => t.category === activeTab.value)
)

const countByTab = (tab: Tab) =>
  tab === '全部' ? enabledTools.length : enabledTools.filter(t => t.category === tab).length

const getIconBg = (color: string) => color + '15'
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-5">
      <div>
        <h1 class="text-[20px] font-bold text-text-heading">工具箱</h1>
        <p class="text-[13px] text-text-light mt-0.5">实用工具集合，点击卡片使用</p>
      </div>
      <span class="text-[12px] text-text-light">共 {{ enabledTools.length }} 个工具</span>
    </div>

    <!-- Category tabs -->
    <div class="flex gap-1 mb-5 border-b border-border">
      <button
        v-for="tab in TABS"
        :key="tab"
        class="px-4 py-2 text-[13px] font-medium transition-colors relative"
        :class="activeTab === tab
          ? 'text-accent after:absolute after:bottom-[-1px] after:left-0 after:right-0 after:h-[2px] after:bg-accent after:rounded-t'
          : 'text-text-light hover:text-text-body'"
        @click="activeTab = tab"
      >
        {{ tab }}
        <span class="ml-1 text-[11px] opacity-60">{{ countByTab(tab) }}</span>
      </button>
    </div>

    <div v-if="filteredTools.length === 0" class="flex flex-col items-center justify-center py-20">
      <div class="w-16 h-16 rounded-2xl bg-placeholder flex items-center justify-center text-2xl text-text-light mb-4">◈</div>
      <p class="text-[14px] text-text-body font-medium">该分类暂无工具</p>
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
      <Card
        v-for="tool in filteredTools"
        :key="tool.id"
        :hoverable="true"
        class="flex flex-col gap-2.5 cursor-pointer"
        @click="router.push(`/toolbox/${tool.id}`)"
      >
        <div class="flex items-start justify-between">
          <div
            class="w-10 h-10 rounded-[11px] flex items-center justify-center text-xl"
            :style="{ backgroundColor: getIconBg(tool.color), color: tool.color }"
          >
            {{ tool.icon }}
          </div>
          <span v-if="tool.category" class="text-[10px] px-2 py-0.5 rounded-full bg-page-bg text-text-light">
            {{ tool.category }}
          </span>
        </div>
        <h3 class="text-[14px] font-bold text-text-heading">{{ tool.name }}</h3>
        <p class="text-[11px] text-text-light leading-relaxed flex-1">{{ tool.description }}</p>
        <div class="flex gap-1 flex-wrap">
          <Chip v-for="tag in tool.tags" :key="tag">{{ tag }}</Chip>
        </div>
        <span class="text-[11px] font-semibold mt-auto" :style="{ color: tool.color }">
          点击使用 →
        </span>
      </Card>
    </div>
  </div>
</template>
