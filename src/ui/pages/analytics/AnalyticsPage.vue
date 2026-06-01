<script setup lang="ts">
import { ref } from 'vue'
import SchoolSidebar from './components/SchoolSidebar.vue'
import ContentTab from './components/ContentTab.vue'
import ChartsTab from './components/ChartsTab.vue'
import type { School } from '@/services/campusReportApi'

const selectedSchool = ref<School | null>(null)
const activeTab = ref<'content' | 'charts'>('content')

function onSchoolSelect(school: School) {
  selectedSchool.value = school
  activeTab.value = 'content'
}
</script>

<template>
  <div class="flex h-full gap-0 -m-4">
    <!-- Left: school list -->
    <SchoolSidebar
      :selected-school-id="selectedSchool?.id ?? null"
      @select="onSchoolSelect"
    />

    <!-- Right: workspace -->
    <div class="flex-1 flex flex-col min-w-0 p-4">
      <!-- Empty state -->
      <template v-if="!selectedSchool">
        <div class="flex-1 flex flex-col items-center justify-center text-center">
          <div class="text-4xl mb-3">🏫</div>
          <div class="text-[14px] font-semibold text-text-heading mb-1">选择一所学校开始</div>
          <div class="text-[12px] text-text-light">从左侧选择学校，或新建本学期的学校</div>
        </div>
      </template>

      <!-- Workspace -->
      <template v-else>
        <!-- Tab bar -->
        <div class="flex gap-1 mb-4 border-b border-border pb-2">
          <button
            v-for="tab in [{ key: 'content', label: '内容素材' }, { key: 'charts', label: '数据图表' }]"
            :key="tab.key"
            @click="activeTab = tab.key as 'content' | 'charts'"
            class="px-4 py-1.5 text-[12px] font-medium rounded-md transition-colors"
            :class="activeTab === tab.key
              ? 'bg-accent text-white'
              : 'text-text-body hover:text-text-heading hover:bg-accent/10'"
          >
            {{ tab.label }}
          </button>
        </div>

        <!-- Tab content -->
        <ContentTab
          v-if="activeTab === 'content'"
          :school="selectedSchool"
          class="flex-1 min-h-0"
        />
        <ChartsTab
          v-else
          :school="selectedSchool"
          class="flex-1 min-h-0"
        />
      </template>
    </div>
  </div>
</template>
