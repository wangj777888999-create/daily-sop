<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { campusReportApi, type School, type Section } from '@/services/campusReportApi'
import SectionEditor from './SectionEditor.vue'

const props = defineProps<{ school: School }>()

const sections = ref<Section[]>([])
const selectedSection = ref<Section | null>(null)
const loading = ref(false)
const creating = ref(false)
const hoveredSectionId = ref<string | null>(null)

async function loadSections() {
  loading.value = true
  try {
    sections.value = await campusReportApi.listSections(props.school.id)
    if (sections.value.length > 0 && !selectedSection.value) {
      selectedSection.value = sections.value[0]
    }
  } finally {
    loading.value = false
  }
}

async function addSection() {
  creating.value = true
  try {
    const s = await campusReportApi.createSection(props.school.id, '新板块')
    sections.value.push(s)
    selectedSection.value = s
  } finally {
    creating.value = false
  }
}

async function removeSection(e: MouseEvent, section: Section) {
  e.stopPropagation()
  if (!confirm(`确认删除板块「${section.title}」？`)) return
  await campusReportApi.deleteSection(props.school.id, section.id)
  sections.value = sections.value.filter(s => s.id !== section.id)
  if (selectedSection.value?.id === section.id) {
    selectedSection.value = sections.value[0] ?? null
  }
}

function onSectionUpdated(updated: Section) {
  const idx = sections.value.findIndex(s => s.id === updated.id)
  if (idx >= 0) sections.value[idx] = updated
  if (selectedSection.value?.id === updated.id) {
    selectedSection.value = updated
  }
}

watch(() => props.school.id, () => {
  sections.value = []
  selectedSection.value = null
  loadSections()
})

onMounted(loadSections)
</script>

<template>
  <div class="flex h-full gap-0 border border-border rounded-xl overflow-hidden bg-card-bg">
    <!-- Section list panel -->
    <div class="w-[200px] flex-shrink-0 border-r border-border flex flex-col bg-sidebar-bg">
      <div class="px-3 pt-3 pb-2">
        <button
          @click="addSection"
          :disabled="creating"
          class="w-full flex items-center justify-center gap-1 py-1.5 rounded-md border border-dashed border-border text-[11px] text-text-light hover:border-accent hover:text-accent transition-colors disabled:opacity-50"
        >
          <span>＋</span> 新建板块
        </button>
      </div>

      <div class="flex-1 overflow-y-auto px-2 pb-3">
        <div v-if="loading" class="text-[11px] text-text-light text-center py-4">加载中…</div>
        <div v-else-if="sections.length === 0" class="text-[11px] text-text-light text-center py-6 px-2 leading-relaxed">
          暂无板块<br>点击上方按钮新建
        </div>
        <div
          v-for="section in sections"
          :key="section.id"
          @click="selectedSection = section"
          @mouseenter="hoveredSectionId = section.id"
          @mouseleave="hoveredSectionId = null"
          class="flex items-center gap-1.5 px-2.5 py-2 rounded-lg mb-1 cursor-pointer transition-colors text-[12px]"
          :class="selectedSection?.id === section.id
            ? 'bg-accent text-white font-medium'
            : 'text-text-body hover:bg-accent/10 hover:text-text-heading'"
        >
          <span class="flex-1 truncate">{{ section.title }}</span>
          <button
            v-if="hoveredSectionId === section.id && selectedSection?.id !== section.id"
            @click="removeSection($event, section)"
            class="flex-shrink-0 text-[10px] text-text-light hover:text-red-500 transition-colors"
            title="删除"
          >✕</button>
        </div>
      </div>
    </div>

    <!-- Editor area -->
    <div class="flex-1 min-w-0">
      <div v-if="!selectedSection" class="h-full flex items-center justify-center text-[12px] text-text-light">
        选择左侧板块开始编辑
      </div>
      <SectionEditor
        v-else
        :key="selectedSection.id"
        :school-id="props.school.id"
        :section="selectedSection"
        @updated="onSectionUpdated"
      />
    </div>
  </div>
</template>
