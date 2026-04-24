<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import Card from '@/ui/components/common/Card.vue'
import Button from '@/ui/components/common/Button.vue'
import Chip from '@/ui/components/common/Chip.vue'
import SearchBox from '@/ui/components/common/SearchBox.vue'
import { fetchSOPs, deleteSOP, type SOP } from '@/services/sopApi'

const router = useRouter()
const sops = ref<SOP[]>([])
const loading = ref(false)
const searchQuery = ref('')
const showDeleteConfirm = ref(false)
const sopToDelete = ref<SOP | null>(null)

const filteredSOPs = computed(() => {
  if (!searchQuery.value) return sops.value
  const query = searchQuery.value.toLowerCase()
  return sops.value.filter(sop =>
    sop.name.toLowerCase().includes(query) ||
    sop.description.toLowerCase().includes(query) ||
    sop.tags.some(tag => tag.toLowerCase().includes(query))
  )
})

onMounted(async () => {
  loading.value = true
  sops.value = await fetchSOPs()
  loading.value = false
})

function formatDate(dateStr: string) {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return '今天'
  if (diffDays === 1) return '昨天'
  if (diffDays < 7) return `${diffDays}天前`
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function confirmDelete(sop: SOP) {
  sopToDelete.value = sop
  showDeleteConfirm.value = true
}

async function handleDelete() {
  if (!sopToDelete.value) return
  const success = await deleteSOP(sopToDelete.value.id)
  if (success) {
    sops.value = sops.value.filter(s => s.id !== sopToDelete.value!.id)
  }
  showDeleteConfirm.value = false
  sopToDelete.value = null
}

function goToCreate() {
  router.push('/sop/create')
}

function goToImport() {
  router.push('/sop/import')
}

function goToExecute(sop: SOP) {
  router.push(`/sop/execute/${sop.id}`)
}

function goToEdit(sop: SOP) {
  router.push(`/sop/edit/${sop.id}`)
}
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <div>
        <h1 class="text-[20px] font-bold text-text-heading">SOP 管理</h1>
        <p class="text-[13px] text-text-light mt-0.5">管理所有标准操作流程</p>
      </div>
      <div class="flex gap-2">
        <Button variant="secondary" @click="goToImport">📥 导入代码</Button>
        <Button variant="primary" @click="goToCreate">＋ 新建 SOP</Button>
      </div>
    </div>

    <!-- Toolbar -->
    <div class="flex items-center gap-3 mb-4">
      <SearchBox v-model="searchQuery" placeholder="搜索 SOP 名称、描述或标签…" class="w-80" />
      <span class="text-[11px] text-text-light">{{ filteredSOPs.length }} 个 SOP</span>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex-1 flex items-center justify-center">
      <div class="text-[13px] text-text-light">加载中…</div>
    </div>

    <!-- Empty State -->
    <div v-else-if="filteredSOPs.length === 0 && !searchQuery" class="flex-1 flex flex-col items-center justify-center">
      <div class="text-[48px] mb-3">📋</div>
      <h3 class="text-[16px] font-bold text-text-heading mb-1">暂无 SOP</h3>
      <p class="text-[12px] text-text-light mb-4">创建你的第一个标准操作流程</p>
      <Button variant="primary" @click="goToCreate">＋ 新建 SOP</Button>
    </div>

    <!-- No Results -->
    <div v-else-if="filteredSOPs.length === 0" class="flex-1 flex flex-col items-center justify-center">
      <div class="text-[48px] mb-3">🔍</div>
      <h3 class="text-[16px] font-bold text-text-heading mb-1">未找到结果</h3>
      <p class="text-[12px] text-text-light">尝试使用其他关键词搜索</p>
    </div>

    <!-- SOP Grid -->
    <div v-else class="flex-1 overflow-y-auto">
      <div class="grid grid-cols-2 gap-3">
        <Card v-for="sop in filteredSOPs" :key="sop.id" :hoverable="true" class="flex flex-col gap-2.5">
          <!-- Header -->
          <div class="flex items-start justify-between">
            <div class="flex-1">
              <h3 class="text-[14px] font-bold text-text-heading">{{ sop.name }}</h3>
              <p class="text-[11px] text-text-light mt-0.5 line-clamp-2">{{ sop.description }}</p>
            </div>
            <div class="flex gap-1 ml-2">
              <button
                @click.stop="goToEdit(sop)"
                class="w-7 h-7 rounded-md flex items-center justify-center text-[13px] hover:bg-chip transition-colors"
                title="编辑"
              >
                ✏️
              </button>
              <button
                @click.stop="confirmDelete(sop)"
                class="w-7 h-7 rounded-md flex items-center justify-center text-[13px] hover:bg-chip transition-colors"
                title="删除"
              >
                🗑️
              </button>
            </div>
          </div>

          <!-- Tags -->
          <div class="flex flex-wrap gap-1">
            <Chip v-for="tag in sop.tags" :key="tag" :active="false">{{ tag }}</Chip>
          </div>

          <!-- Footer -->
          <div class="flex items-center justify-between mt-auto pt-2 border-t border-border">
            <div class="flex items-center gap-3">
              <span class="text-[10px] text-text-light">{{ sop.steps.length }} 个步骤</span>
              <span class="text-[10px] text-text-light">{{ formatDate(sop.updated_at) }}</span>
            </div>
            <Button variant="primary" size="small" @click="goToExecute(sop)">▶ 执行</Button>
          </div>
        </Card>
      </div>
    </div>

    <!-- Delete Confirmation Modal -->
    <div
      v-if="showDeleteConfirm"
      class="fixed inset-0 bg-black/30 flex items-center justify-center z-50"
      @click.self="showDeleteConfirm = false"
    >
      <Card class="w-80">
        <h3 class="text-[14px] font-bold text-text-heading mb-2">确认删除</h3>
        <p class="text-[12px] text-text-light mb-4">
          确定要删除 SOP「{{ sopToDelete?.name }}」吗？此操作无法撤销。
        </p>
        <div class="flex gap-2 justify-end">
          <Button variant="secondary" size="small" @click="showDeleteConfirm = false">取消</Button>
          <Button variant="primary" size="small" @click="handleDelete">删除</Button>
        </div>
      </Card>
    </div>
  </div>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
