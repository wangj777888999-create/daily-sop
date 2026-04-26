<script setup lang="ts">
import { ref, onMounted, computed, onUnmounted } from 'vue'
import { useRouter, useRoute, onBeforeRouteLeave } from 'vue-router'
import Card from '@/ui/components/common/Card.vue'
import Button from '@/ui/components/common/Button.vue'
import Chip from '@/ui/components/common/Chip.vue'
import RowTitle from '@/ui/components/common/RowTitle.vue'
import ExecutionConfig from '@/ui/components/sop/ExecutionConfig.vue'
import { fetchSOPs, getExecutionStatus, downloadExecutionResult, type SOP, type ExecutionResult } from '@/services/sopApi'

const router = useRouter()
const route = useRoute()

const sops = ref<SOP[]>([])
const selectedSOPId = ref<string>('')
const uploadedFiles = ref<File[]>([])
const execution = ref<ExecutionResult | null>(null)
const isExecuting = ref(false)
const isPolling = ref(false)
const pollInterval = ref<number | null>(null)
const showExecutionConfig = ref(false)

const selectedSOP = computed(() => {
  return sops.value.find(s => s.id === selectedSOPId.value)
})

const canExecute = computed(() => {
  return selectedSOPId.value && !isExecuting.value
})

const hasResult = computed(() => {
  return execution.value && (execution.value.status === 'success' || execution.value.status === 'failed')
})

onMounted(async () => {
  sops.value = await fetchSOPs()

  // Check if SOP ID is provided in route
  if (route.params.sopId) {
    selectedSOPId.value = route.params.sopId as string
  }
})

onUnmounted(() => {
  stopPolling()
})

// Q3: 路由跳转时也清理轮询，防 keep-alive 泄漏
onBeforeRouteLeave(() => {
  stopPolling()
})

function handleExecute() {
  showExecutionConfig.value = true
}

function handleExecutionComplete(execId: string) {
  startPolling(execId)
}

function handleFileUpload(event: Event) {
  const target = event.target as HTMLInputElement
  const files = target.files
  if (!files) return

  uploadedFiles.value = Array.from(files)
}

function removeFile(index: number) {
  uploadedFiles.value.splice(index, 1)
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function startPolling(execId: string) {
  stopPolling()
  isPolling.value = true

  pollInterval.value = window.setInterval(async () => {
    const status = await getExecutionStatus(execId)
    if (status) {
      execution.value = status
      if (status.status === 'success' || status.status === 'failed') {
        stopPolling()
      }
    }
  }, 2000)
}

function stopPolling() {
  isPolling.value = false
  if (pollInterval.value) {
    clearInterval(pollInterval.value)
    pollInterval.value = null
  }
}

async function handleDownload() {
  if (!execution.value?.id) return

  const blob = await downloadExecutionResult(execution.value.id)
  if (blob) {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `sop-result-${execution.value.id}.zip`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }
}

function goBack() {
  router.push('/sop')
}

function goToCreate() {
  router.push('/sop/create')
}

function getStatusColor(status: string): string {
  switch (status) {
    case 'success': return '#5B8F7A'
    case 'failed': return '#C17F3A'
    case 'running': return '#3A7FC1'
    default: return '#9C8E82'
  }
}

function getStatusLabel(status: string): string {
  switch (status) {
    case 'success': return '已完成'
    case 'failed': return '失败'
    case 'running': return '执行中'
    case 'pending': return '等待中'
    default: return '未知'
  }
}

// 由 status 派生进度百分比（后端不传 progress 字段）
function getProgressPercent(status: string): number {
  switch (status) {
    case 'success': return 100
    case 'failed': return 100
    case 'running': return 50
    case 'pending': return 10
    default: return 0
  }
}
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <div>
        <h1 class="text-[20px] font-bold text-text-heading">执行 SOP</h1>
        <p class="text-[13px] text-text-light mt-0.5">选择 SOP 并上传数据文件开始执行</p>
      </div>
      <Button variant="secondary" @click="goBack">← 返回</Button>
    </div>

    <!-- Main Content -->
    <div class="flex gap-4 flex-1 min-h-0">
      <!-- Left: Configuration -->
      <Card class="w-80 flex-shrink-0 flex flex-col">
        <RowTitle label="执行配置" />

        <!-- SOP Selection -->
        <div class="mb-4">
          <label class="text-[11px] text-text-light mb-1 block">选择 SOP</label>
          <select
            v-model="selectedSOPId"
            class="w-full bg-page-bg border border-border rounded-md px-3 py-1.5 text-[12px] text-text-body outline-none focus:border-accent focus:shadow-input-focus"
          >
            <option value="">请选择 SOP…</option>
            <option v-for="sop in sops" :key="sop.id" :value="sop.id">
              {{ sop.name }}
            </option>
          </select>
        </div>

        <!-- Selected SOP Info -->
        <div v-if="selectedSOP" class="mb-4 p-3 bg-page-bg border border-border rounded-lg">
          <h4 class="text-[12px] font-bold text-text-heading mb-1">{{ selectedSOP.name }}</h4>
          <p class="text-[11px] text-text-light line-clamp-2">{{ selectedSOP.description }}</p>
          <div class="flex flex-wrap gap-1 mt-2">
            <Chip v-for="tag in selectedSOP.tags" :key="tag">{{ tag }}</Chip>
          </div>
          <div class="text-[10px] text-text-light mt-2">
            {{ selectedSOP.steps.length }} 个步骤
          </div>
        </div>

        <!-- File Upload -->
        <div class="mb-4">
          <label class="text-[11px] text-text-light mb-1 block">上传数据文件</label>
          <label
            class="flex flex-col items-center justify-center h-28 border-2 border-dashed border-border rounded-lg cursor-pointer hover:border-accent transition-colors"
          >
            <div class="text-[24px] mb-1">📁</div>
            <div class="text-[11px] text-text-light">点击选择文件或拖拽到此处</div>
            <div class="text-[10px] text-text-light mt-1">支持 Excel、CSV、TXT</div>
            <input
              type="file"
              multiple
              accept=".xlsx,.xls,.csv"
              class="hidden"
              @change="handleFileUpload"
            />
          </label>
        </div>

        <!-- Uploaded Files -->
        <div v-if="uploadedFiles.length > 0" class="mb-4">
          <label class="text-[11px] text-text-light mb-1 block">已上传</label>
          <div class="space-y-1">
            <div
              v-for="(file, index) in uploadedFiles"
              :key="index"
              class="flex items-center justify-between bg-page-bg border border-border rounded-md px-2 py-1.5"
            >
              <div class="flex items-center gap-2">
                <span class="text-[11px]">📄</span>
                <span class="text-[11px] text-text-body truncate max-w-[120px]">{{ file.name }}</span>
                <span class="text-[10px] text-text-light">{{ formatFileSize(file.size) }}</span>
              </div>
              <button
                @click="removeFile(index)"
                class="text-[11px] text-text-light hover:text-red-500"
              >
                ×
              </button>
            </div>
          </div>
        </div>

        <!-- Empty State -->
        <div v-if="sops.length === 0" class="flex-1 flex flex-col items-center justify-center">
          <div class="text-[48px] mb-3">📋</div>
          <h3 class="text-[14px] font-bold text-text-heading mb-1">暂无 SOP</h3>
          <p class="text-[11px] text-text-light mb-3">请先创建 SOP</p>
          <Button variant="primary" size="small" @click="goToCreate">＋ 新建 SOP</Button>
        </div>
      </Card>

      <!-- Right: Execution -->
      <Card class="flex-1 flex flex-col min-w-0">
        <RowTitle label="执行结果" />

        <!-- Execution Status -->
        <div v-if="!execution" class="flex-1 flex flex-col items-center justify-center">
          <div class="text-[48px] mb-3">▶️</div>
          <h3 class="text-[14px] font-bold text-text-heading mb-1">准备就绪</h3>
          <p class="text-[11px] text-text-light">选择 SOP 并上传文件后点击执行</p>
        </div>

        <div v-else class="flex-1 flex flex-col">
          <!-- Status Card -->
          <div
            class="p-4 rounded-lg mb-4"
            :style="{
              backgroundColor: getStatusColor(execution.status) + '15',
              borderColor: getStatusColor(execution.status) + '40'
            }"
          >
            <div class="flex items-center justify-between mb-2">
              <div class="flex items-center gap-2">
                <div
                  v-if="execution.status === 'running'"
                  class="w-4 h-4 border-2 border-t-transparent rounded-full animate-spin"
                  :style="{ borderColor: getStatusColor(execution.status) }"
                />
                <span
                  class="text-[13px] font-bold"
                  :style="{ color: getStatusColor(execution.status) }"
                >
                  {{ getStatusLabel(execution.status) }}
                </span>
              </div>
              <span class="text-[11px] text-text-light">
                {{ getProgressPercent(execution.status) }}%
              </span>
            </div>

            <!-- Progress Bar -->
            <div class="h-2 bg-chip rounded-full overflow-hidden">
              <div
                class="h-full rounded-full transition-all duration-300"
                :style="{
                  width: getProgressPercent(execution.status) + '%',
                  backgroundColor: getStatusColor(execution.status)
                }"
              />
            </div>

            <div v-if="execution.error" class="text-[11px] text-red-500 mt-2">
              {{ execution.error }}
            </div>
          </div>

          <!-- Result Section -->
          <div v-if="hasResult" class="flex-1 flex flex-col">
            <RowTitle label="执行结果" />

            <div v-if="execution.status === 'success'" class="flex-1">
              <div class="bg-page-bg border border-border rounded-lg p-4 mb-4">
                <div class="text-[12px] text-text-body">
                  执行成功！结果已生成。
                </div>
              </div>

              <!-- Download Button -->
              <div class="flex gap-2">
                <Button variant="primary" @click="handleDownload">
                  📥 下载结果
                </Button>
                <Button variant="secondary" @click="handleExecute">
                  🔄 重新执行
                </Button>
              </div>
            </div>

            <div v-else-if="execution.status === 'failed'" class="flex-1">
              <div class="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
                <div class="text-[12px] text-red-600">
                  {{ execution.error || '执行失败，请检查 SOP 配置和数据文件' }}
                </div>
              </div>

              <Button variant="secondary" @click="handleExecute">
                🔄 重新执行
              </Button>
            </div>
          </div>

          <!-- Steps Progress -->
          <div v-if="execution.status === 'running' && selectedSOP" class="mt-4">
            <RowTitle label="执行步骤" />
            <div class="space-y-2">
              <div
                v-for="(step, index) in selectedSOP.steps"
                :key="step.id"
                class="flex items-center gap-2 text-[11px]"
              >
                <div
                  class="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold"
                  :style="{
                    backgroundColor: '#E5DDD0',
                    color: '#9C8E82'
                  }"
                >
                  {{ index + 1 }}
                </div>
                <span class="text-text-body">{{ step.description }}</span>
              </div>
            </div>
          </div>
        </div>
      </Card>
    </div>

    <!-- Footer Actions -->
    <div class="flex justify-end gap-2.5 mt-4 pt-4 border-t border-border">
      <Button variant="secondary" @click="goBack">取消</Button>
      <Button
        variant="primary"
        :disabled="!canExecute"
        @click="handleExecute"
      >
        {{ isExecuting ? '执行中…' : '▶ 执行 SOP' }}
      </Button>
    </div>

    <!-- Execution Config Modal -->
    <ExecutionConfig
      v-if="showExecutionConfig && selectedSOP"
      :sop-id="selectedSOP.id"
      :data-sources="selectedSOP.dataSources || []"
      @close="showExecutionConfig = false"
      @executed="handleExecutionComplete"
    />
  </div>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.animate-spin {
  animation: spin 1s linear infinite;
}
</style>
