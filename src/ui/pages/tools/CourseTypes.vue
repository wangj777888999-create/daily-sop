<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Button from '@/ui/components/common/Button.vue'
import Card from '@/ui/components/common/Card.vue'

interface CourseRecord {
  课程名称: string
  类型: string
}

const records = ref<CourseRecord[]>([])
const typeOptions = ref<string[]>([])
const searchQuery = ref('')
const loading = ref(false)
const errorMsg = ref('')
const successMsg = ref('')

// Add dialog
const showAddDialog = ref(false)
const newName = ref('')
const newType = ref('')

// Import
const importInput = ref<HTMLInputElement | null>(null)

const API = '/api/tools/course-types'

const filteredRecords = computed(() => {
  if (!searchQuery.value) return records.value
  const q = searchQuery.value.toLowerCase()
  return records.value.filter(
    r => r.课程名称.toLowerCase().includes(q) || r.类型.toLowerCase().includes(q)
  )
})

const typeStats = computed(() => {
  const stats: Record<string, number> = {}
  for (const r of records.value) {
    stats[r.类型] = (stats[r.类型] || 0) + 1
  }
  return Object.entries(stats).sort((a, b) => b[1] - a[1])
})

async function loadData() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await fetch(API)
    if (!res.ok) throw new Error('加载失败')
    const data = await res.json()
    records.value = data.records
    typeOptions.value = data.type_options
  } catch (e: any) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

async function updateType(index: number, newTypeVal: string) {
  const oldType = records.value[index].类型
  records.value[index].类型 = newTypeVal // optimistic update
  try {
    const fd = new FormData()
    fd.append('course_type', newTypeVal)
    const res = await fetch(`${API}/${index}`, { method: 'PUT', body: fd })
    if (!res.ok) {
      records.value[index].类型 = oldType // rollback
      const err = await res.json()
      throw new Error(err.detail || '修改失败')
    }
    showFlash('类型已更新')
  } catch (e: any) {
    errorMsg.value = e.message
  }
}

async function addRecord() {
  if (!newName.value.trim() || !newType.value) return
  try {
    const fd = new FormData()
    fd.append('course_name', newName.value.trim())
    fd.append('course_type', newType.value)
    const res = await fetch(API, { method: 'POST', body: fd })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '新增失败')
    }
    showAddDialog.value = false
    newName.value = ''
    newType.value = ''
    await loadData()
    showFlash('新增成功')
  } catch (e: any) {
    errorMsg.value = e.message
  }
}

async function deleteRecord(index: number) {
  const name = records.value[index].课程名称
  if (!confirm(`确认删除「${name}」？`)) return
  try {
    const res = await fetch(`${API}/${index}`, { method: 'DELETE' })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '删除失败')
    }
    await loadData()
    showFlash('已删除')
  } catch (e: any) {
    errorMsg.value = e.message
  }
}

async function onImport(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    const fd = new FormData()
    fd.append('file', file)
    const res = await fetch(`${API}/import`, { method: 'POST', body: fd })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '导入失败')
    }
    const result = await res.json()
    await loadData()
    showFlash(`导入完成：新增 ${result.imported} 条，跳过 ${result.skipped} 条（重复），总计 ${result.total} 条`)
  } catch (e: any) {
    errorMsg.value = e.message
  }
  input.value = '' // reset for re-upload
}

function doExport() {
  window.open(`${API}/export`, '_blank')
}

function showFlash(msg: string) {
  successMsg.value = msg
  setTimeout(() => { successMsg.value = '' }, 3000)
}

onMounted(loadData)
</script>

<template>
  <div class="p-6 max-w-5xl mx-auto">
    <Card>
      <div class="flex flex-col gap-5">
        <!-- Header -->
        <div>
          <h2 class="text-lg font-bold text-text-heading">课程类型划分</h2>
          <p class="text-sm text-text-light mt-1">管理课程名称与类型的对应关系，月度分析自动加载</p>
        </div>

        <!-- Messages -->
        <div v-if="errorMsg" class="bg-red-50 border border-red-200 rounded-lg px-4 py-2.5 text-sm text-red-700 flex items-center justify-between">
          {{ errorMsg }}
          <button class="text-red-400 hover:text-red-600" @click="errorMsg = ''">&times;</button>
        </div>
        <div v-if="successMsg" class="bg-green-50 border border-green-200 rounded-lg px-4 py-2.5 text-sm text-green-700">
          {{ successMsg }}
        </div>

        <!-- Toolbar -->
        <div class="flex items-center justify-between gap-3 flex-wrap">
          <div class="flex items-center gap-2">
            <Button variant="primary" size="small" @click="showAddDialog = true; newName = ''; newType = typeOptions[0] || ''">
              + 新增
            </Button>
            <label class="cursor-pointer">
              <input type="file" accept=".xlsx,.xls" class="hidden" @change="onImport" ref="importInput" />
              <span class="inline-flex items-center gap-1 cursor-pointer font-medium select-none transition-all duration-150 active:scale-[0.97] active:brightness-95 bg-chip text-text-body border border-border hover:bg-placeholder/50 hover:shadow-sm px-3 py-1 text-[11px] rounded-md">
                导入 Excel
              </span>
            </label>
            <Button variant="secondary" size="small" @click="doExport">
              导出 Excel
            </Button>
          </div>
          <div class="flex items-center gap-2 text-sm text-text-light">
            <span>共 {{ records.length }} 条</span>
            <input
              v-model="searchQuery"
              type="text"
              placeholder="搜索课程名称或类型..."
              class="border border-border rounded-md px-3 py-1 text-[11px] w-56 focus:outline-none focus:border-accent"
            />
          </div>
        </div>

        <!-- Table -->
        <div class="border border-border rounded-xl overflow-hidden">
          <div class="overflow-auto max-h-[60vh]">
            <table class="w-full text-sm">
              <thead class="bg-page-bg sticky top-0">
                <tr>
                  <th class="px-4 py-2.5 text-left font-medium text-text-light w-12">#</th>
                  <th class="px-4 py-2.5 text-left font-medium text-text-light">课程名称</th>
                  <th class="px-4 py-2.5 text-left font-medium text-text-light w-36">类型</th>
                  <th class="px-4 py-2.5 text-center font-medium text-text-light w-20">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(r, i) in filteredRecords"
                  :key="i"
                  class="border-t border-border hover:bg-page-bg/50 transition-colors"
                >
                  <td class="px-4 py-2 text-text-light">{{ i + 1 }}</td>
                  <td class="px-4 py-2 text-text-body">{{ r.课程名称 }}</td>
                  <td class="px-4 py-2">
                    <select
                      :value="r.类型"
                      @change="updateType(records.findIndex(x => x.课程名称 === r.课程名称), ($event.target as HTMLSelectElement).value)"
                      class="border border-border rounded-md px-2 py-1 text-sm bg-white focus:outline-none focus:border-accent w-full"
                    >
                      <option v-for="t in typeOptions" :key="t" :value="t">{{ t }}</option>
                    </select>
                  </td>
                  <td class="px-4 py-2 text-center">
                    <button
                      class="text-red-400 hover:text-red-600 text-xs"
                      @click="deleteRecord(records.findIndex(x => x.课程名称 === r.课程名称))"
                    >
                      删除
                    </button>
                  </td>
                </tr>
                <tr v-if="filteredRecords.length === 0">
                  <td colspan="4" class="px-4 py-8 text-center text-text-light">
                    {{ searchQuery ? '无匹配结果' : '暂无数据' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Type stats -->
        <div class="flex flex-wrap gap-2">
          <span
            v-for="[type, count] in typeStats"
            :key="type"
            class="text-xs bg-page-bg text-text-body px-2.5 py-1 rounded-full"
          >
            {{ type }} ({{ count }})
          </span>
        </div>
      </div>
    </Card>

    <!-- Add Dialog -->
    <div v-if="showAddDialog" class="fixed inset-0 bg-black/30 flex items-center justify-center z-50" @click.self="showAddDialog = false">
      <div class="bg-white rounded-2xl shadow-xl p-6 w-96 flex flex-col gap-4">
        <h3 class="text-base font-bold text-text-heading">新增课程类型</h3>
        <div class="flex flex-col gap-3">
          <div>
            <label class="text-xs text-text-light mb-1 block">课程名称</label>
            <input
              v-model="newName"
              type="text"
              placeholder="请输入完整课程名称"
              class="border border-border rounded-lg px-3 py-2 text-sm w-full focus:outline-none focus:border-accent"
              @keyup.enter="addRecord"
            />
          </div>
          <div>
            <label class="text-xs text-text-light mb-1 block">类型</label>
            <select
              v-model="newType"
              class="border border-border rounded-lg px-3 py-2 text-sm w-full focus:outline-none focus:border-accent"
            >
              <option v-for="t in typeOptions" :key="t" :value="t">{{ t }}</option>
            </select>
          </div>
        </div>
        <div class="flex justify-end gap-2">
          <Button variant="secondary" size="small" @click="showAddDialog = false">取消</Button>
          <Button variant="primary" size="small" :disabled="!newName.trim() || !newType" @click="addRecord">确认</Button>
        </div>
      </div>
    </div>
  </div>
</template>
