<script setup lang="ts">
import Sidebar from './Sidebar.vue'
import TopBar from './TopBar.vue'
import { useRoute } from 'vue-router'
import { computed } from 'vue'

const route = useRoute()

const pageTitle = computed(() => {
  const titles: Record<string, string[]> = {
    '/home': ['工作台', '首页'],
    '/sop': ['工作台', 'SOP 分析'],
    '/policy': ['工作台', '政策报告'],
    '/analytics': ['工作台', '高级数据分析'],
    '/database': ['工作台', '数据库连接'],
    '/knowledge': ['工作台', '个人知识库']
  }
  return titles[route.path] || ['工作台', '首页']
})
</script>

<template>
  <div class="flex h-screen w-screen overflow-hidden bg-page-bg">
    <Sidebar class="flex-shrink-0" />
    <div class="flex flex-col flex-1 min-w-0">
      <TopBar :breadcrumbs="pageTitle" class="flex-shrink-0" />
      <main class="flex-1 p-xl overflow-y-auto">
        <slot />
      </main>
    </div>
  </div>
</template>
