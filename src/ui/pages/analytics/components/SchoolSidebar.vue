<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { campusReportApi, type School } from '@/services/campusReportApi'
import { databaseApi, type QueryResult } from '@/services/databaseApi'

const props = defineProps<{ selectedSchoolId: string | null }>()
const emit = defineEmits<{ select: [school: School] }>()

// School list state
const schools = ref<School[]>([])
const loading = ref(false)

// Create modal state
const showModal = ref(false)
const dbSchools = ref<{ id: number; school_name: string }[]>([])
const dbLoading = ref(false)
const selectedDbName = ref('')
const creating = ref(false)
const createError = ref('')

// Hover state for delete button
const hoveredId = ref<string | null>(null)

async function loadSchools() {
  loading.value = true
  try {
    schools.value = await campusReportApi.listSchools()
  } finally {
    loading.value = false
  }
}

async function openModal() {
  showModal.value = true
  selectedDbName.value = ''
  createError.value = ''
  dbLoading.value = true
  try {
    const result: QueryResult = await databaseApi.query(
      'SELECT id, school_name FROM gs_school',
      200
    )
    dbSchools.value = result.rows.map(row => ({
      id: Number(row[0]),
      school_name: String(row[1] ?? ''),
    }))
  } catch (e: any) {
    createError.value = '无法从数据库加载学校列表：' + e.message
  } finally {
    dbLoading.value = false
  }
}

async function confirmCreate() {
  if (!selectedDbName.value) {
    createError.value = '请选择一所学校'
    return
  }
  creating.value = true
  createError.value = ''
  try {
    const school = await campusReportApi.createSchool(selectedDbName.value)
    schools.value.push(school)
    showModal.value = false
    emit('select', school)
  } catch (e: any) {
    createError.value = e.message
  } finally {
    creating.value = false
  }
}

async function removeSchool(e: MouseEvent, school: School) {
  e.stopPropagation()
  if (!confirm(`确认删除「${school.name}」及其所有内容？`)) return
  await campusReportApi.deleteSchool(school.id)
  schools.value = schools.value.filter(s => s.id !== school.id)
}

onMounted(loadSchools)
</script>

<template>
  <aside
    class="w-[180px] flex-shrink-0 flex flex-col border-r border-border bg-sidebar-bg"
    style="min-height: 0"
  >
    <!-- Header -->
    <div class="px-3 pt-4 pb-2">
      <div class="text-[10px] text-text-light tracking-wider uppercase mb-2">本学期学校</div>
      <button
        @click="openModal"
        class="w-full flex items-center justify-center gap-1 py-1.5 rounded-md border border-dashed border-border text-[11px] text-text-light hover:border-accent hover:text-accent transition-colors"
      >
        <span>＋</span> 新建学校
      </button>
    </div>

    <!-- School list -->
    <div class="flex-1 overflow-y-auto px-2 pb-3">
      <div v-if="loading" class="text-[11px] text-text-light text-center py-4">加载中…</div>
      <div v-else-if="schools.length === 0" class="text-[11px] text-text-light text-center py-6 px-2 leading-relaxed">
        暂无学校<br>点击上方按钮新建
      </div>
      <div
        v-for="school in schools"
        :key="school.id"
        @click="emit('select', school)"
        @mouseenter="hoveredId = school.id"
        @mouseleave="hoveredId = null"
        class="flex items-center gap-2 px-2.5 py-2 rounded-lg mb-1 cursor-pointer transition-colors text-[12px] group"
        :class="props.selectedSchoolId === school.id
          ? 'bg-accent text-white font-medium'
          : 'text-text-body hover:bg-accent/10 hover:text-text-heading'"
      >
        <span class="flex-shrink-0 text-[10px]">🏫</span>
        <span class="flex-1 truncate">{{ school.name }}</span>
        <button
          v-if="hoveredId === school.id && props.selectedSchoolId !== school.id"
          @click="removeSchool($event, school)"
          class="flex-shrink-0 text-[11px] text-text-light hover:text-red-500 transition-colors"
          title="删除"
        >✕</button>
      </div>
    </div>
  </aside>

  <!-- Create modal overlay -->
  <Teleport to="body">
    <div
      v-if="showModal"
      class="fixed inset-0 bg-black/30 flex items-center justify-center z-50"
      @click.self="showModal = false"
    >
      <div class="bg-card-bg border border-border rounded-xl shadow-xl p-6 w-[360px]">
        <div class="text-[14px] font-semibold text-text-heading mb-4">新建学校</div>

        <div class="text-[11px] text-text-light mb-1.5">从数据库选择学校</div>
        <div v-if="dbLoading" class="text-[11px] text-text-light py-2">正在加载学校列表…</div>
        <select
          v-else
          v-model="selectedDbName"
          class="w-full border border-border rounded-lg px-3 py-2 text-[12px] text-text-body bg-page-bg focus:outline-none focus:border-accent"
        >
          <option value="" disabled>请选择学校…</option>
          <option
            v-for="s in dbSchools"
            :key="s.id"
            :value="s.school_name"
          >{{ s.school_name }}</option>
        </select>

        <div v-if="createError" class="mt-2 text-[11px] text-red-500">{{ createError }}</div>

        <div class="flex gap-2 justify-end mt-4">
          <button
            @click="showModal = false"
            class="px-4 py-1.5 text-[12px] text-text-body border border-border rounded-lg hover:bg-placeholder/40 transition-colors"
          >取消</button>
          <button
            @click="confirmCreate"
            :disabled="creating || !selectedDbName"
            class="px-4 py-1.5 text-[12px] text-white bg-accent rounded-lg hover:bg-accent-dark transition-colors disabled:opacity-50"
          >{{ creating ? '创建中…' : '确认创建' }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
