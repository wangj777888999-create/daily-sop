<script setup lang="ts">
import { useRouter } from 'vue-router'
import Card from '@/ui/components/common/Card.vue'
import Chip from '@/ui/components/common/Chip.vue'
import { tools } from '@/data/tools'

const router = useRouter()

const enabledTools = tools.filter(t => t.enabled !== false)
const getIconBg = (color: string) => color + '15'
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-5">
      <div>
        <h1 class="text-[20px] font-bold text-text-heading">工具箱</h1>
        <p class="text-[13px] text-text-light mt-0.5">实用工具集合，点击卡片使用</p>
      </div>
      <span class="text-[12px] text-text-light">工具数量: {{ enabledTools.length }}</span>
    </div>

    <div v-if="enabledTools.length === 0" class="flex flex-col items-center justify-center py-20">
      <div class="w-16 h-16 rounded-2xl bg-placeholder flex items-center justify-center text-2xl text-text-light mb-4">◈</div>
      <p class="text-[14px] text-text-body font-medium">暂无可用工具</p>
      <p class="text-[12px] text-text-light mt-1">后续添加工具只需在工具注册表中新增条目</p>
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
      <Card
        v-for="tool in enabledTools"
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
