<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { Tool } from '@/types/toolbox'

const route = useRoute()
const router = useRouter()

const tools: Tool[] = [
  {
    id: 'fee-calculator',
    name: '课时费计算器',
    description: '上传 Excel 数据，按教练×课程规则计算课时费，支持多种计费方式和补贴配置',
    icon: '◈',
    color: '#5B8F7A',
    tags: ['财务', 'Excel'],
    src: '/tools/课时费计算器.html',
    iframeHeight: 800,
  },
]

const tool = computed(() => tools.find(t => t.id === route.params.toolId))
const getIconBg = (color: string) => color + '15'
const openInNewWindow = (src: string) => window.open(src, '_blank')
</script>

<template>
  <div v-if="tool">
    <div class="flex items-center gap-3 mb-4">
      <button
        class="flex items-center gap-1.5 text-[12px] text-text-light hover:text-text-heading transition-colors px-2 py-1 rounded-md hover:bg-chip"
        @click="router.push('/toolbox')"
      >
        ← 返回工具箱
      </button>
      <div class="w-px h-4 bg-border" />
      <div
        class="w-7 h-7 rounded-lg flex items-center justify-center text-sm"
        :style="{ backgroundColor: getIconBg(tool.color), color: tool.color }"
      >
        {{ tool.icon }}
      </div>
      <span class="text-[14px] font-bold text-text-heading">{{ tool.name }}</span>
      <button
        class="ml-auto text-[11px] text-text-light hover:text-accent transition-colors px-2 py-1 rounded-md hover:bg-accent-light"
        @click="openInNewWindow(tool.src)"
      >
        ↗ 新窗口打开
      </button>
    </div>
    <div class="bg-gradient-to-b from-card-bg to-card-gradient border border-border/70 rounded-xl shadow-card overflow-hidden">
      <iframe
        :src="tool.src"
        class="w-full border-0"
        :style="{ height: (tool.iframeHeight || 800) + 'px' }"
        :title="tool.name"
      />
    </div>
  </div>
  <div v-else class="flex flex-col items-center justify-center py-20">
    <p class="text-[14px] text-text-body font-medium">工具不存在</p>
    <button
      class="mt-3 text-[12px] text-accent hover:underline"
      @click="router.push('/toolbox')"
    >
      返回工具箱
    </button>
  </div>
</template>
