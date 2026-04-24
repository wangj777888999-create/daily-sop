<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const navItems = [
  { icon: '⌂', label: '工作台首页', key: 'home', path: '/home' },
  { icon: '◈', label: 'SOP 数据分析', key: 'sop', path: '/sop' },
  { icon: '✦', label: '政策报告撰写', key: 'policy', path: '/policy' },
  { icon: '◉', label: '高级数据分析', key: 'analytics', path: '/analytics' },
  { icon: '⬡', label: '数据库连接', key: 'database', path: '/database' },
  { icon: '◗', label: '个人知识库', key: 'knowledge', path: '/knowledge' }
]

const currentKey = computed(() => {
  const item = navItems.find(n => n.path === route.path)
  return item?.key || 'home'
})

const navigateTo = (path: string) => {
  router.push(path)
}
</script>

<template>
  <aside class="w-sidebar bg-sidebar-bg border-r border-border flex flex-col">
    <div class="px-4 py-[18px] border-b border-border flex items-center gap-[10px]">
      <div class="w-8 h-8 bg-accent rounded-[9px] flex items-center justify-center text-white text-lg flex-shrink-0">
        ✦
      </div>
      <div>
        <div class="text-[13px] font-bold text-text-heading leading-tight">智能工作台</div>
        <div class="text-[10px] text-text-light">AI Workbench v2</div>
      </div>
    </div>

    <nav class="flex-1 px-2 py-[10px]">
      <div class="text-[9px] text-text-light tracking-wider px-[10px] py-[4px] pb-[6px]">主菜单</div>
      <div
        v-for="item in navItems"
        :key="item.key"
        @click="navigateTo(item.path)"
        class="flex items-center gap-2.5 px-3 py-2 rounded-md mb-1 cursor-pointer transition-colors"
        :class="currentKey === item.key
          ? 'bg-accent text-white'
          : 'text-text-body hover:bg-accent/10'"
      >
        <span class="w-4 text-center flex-shrink-0">{{ item.icon }}</span>
        <span class="text-[13px]">{{ item.label }}</span>
        <span
          v-if="currentKey === item.key"
          class="ml-auto w-1.5 h-1.5 rounded-full bg-white/60 flex-shrink-0"
        />
      </div>
    </nav>

    <div class="px-4 py-3 border-t border-border flex items-center gap-2">
      <div class="w-7 h-7 rounded-full bg-placeholder-dk flex-shrink-0" />
      <div class="flex-1 min-w-0">
        <div class="text-[12px] font-bold text-text-heading truncate">张三</div>
        <div class="text-[10px] text-text-light">管理员</div>
      </div>
      <span class="text-[13px] text-text-light cursor-pointer">⋯</span>
    </div>
  </aside>
</template>
