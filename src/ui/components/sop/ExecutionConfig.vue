<script setup lang="ts">
import { ref, computed } from 'vue'
import Button from '@/ui/components/common/Button.vue'
import { executeSOP } from '@/services/sopApi'
import type { DataSource } from '@/services/sopApi'

const props = defineProps<{
  sopId: string
  dataSources: DataSource[]
}>()

const emit = defineEmits<{
  close: []
  executed: [executionId: string]
}>()

// 文件映射
const mappings = ref<Record<string, File>>({})
const outputPath = ref('')

// 输入数据源
const inputSources = computed(() =>
  props.dataSources.filter(ds => ds.operation === 'read')
)

// 输出数据源
const outputSource = computed(() =>
  props.dataSources.find(ds => ds.operation === 'write')
)

// 检查是否可以执行
const canExecute = computed(() => {
  return inputSources.value.every(ds => mappings.value[ds.id])
})

// 处理文件选择
function handleFileSelect(dataSourceId: string, event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files && input.files[0]) {
    mappings.value[dataSourceId] = input.files[0]
  }
}

// 执行
async function handleExecute() {
  const files = Object.values(mappings.value)
  const result = await executeSOP(props.sopId, files)
  if (result) {
    emit('executed', result.id)
    emit('close')
  }
}
</script>

<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
    <div class="bg-cardBg rounded-xl w-full max-w-lg mx-4 shadow-xl max-h-[90vh] flex flex-col">
      <!-- Header -->
      <div class="px-5 py-4 border-b border-border flex-shrink-0">
        <h2 class="text-[16px] font-bold text-text-heading">执行配置</h2>
        <p class="text-[11px] text-text-light mt-0.5">请为每个数据源提供文件</p>
      </div>

      <!-- Content -->
      <div class="px-5 py-4 overflow-y-auto flex-1">
        <!-- Input Sources -->
        <div v-if="inputSources.length" class="mb-4">
          <h3 class="text-[12px] font-bold text-text-heading mb-2">📥 输入文件</h3>
          <div class="space-y-3">
            <div
              v-for="ds in inputSources"
              :key="ds.id"
              class="bg-page-bg border border-border rounded-lg p-3"
            >
              <div class="flex items-center justify-between mb-2">
                <span class="text-[11px] font-medium">{{ ds.name }}</span>
                <span class="text-[10px] text-text-light">变量: {{ ds.variableName }}</span>
              </div>
              <label class="block cursor-pointer">
                <span class="text-[10px] text-accent hover:underline">选择文件...</span>
                <input
                  type="file"
                  class="hidden"
                  :accept="ds.variableName.includes('csv') ? '.csv' : '.xlsx,.xls'"
                  @change="(e) => handleFileSelect(ds.id, e)"
                />
              </label>
              <div v-if="mappings[ds.id]" class="mt-1 text-[10px] text-accent">
                ✓ {{ mappings[ds.id].name }}
              </div>
            </div>
          </div>
        </div>

        <!-- Output Source -->
        <div v-if="outputSource">
          <h3 class="text-[12px] font-bold text-text-heading mb-2">📤 输出文件</h3>
          <div class="bg-page-bg border border-border rounded-lg p-3">
            <div class="text-[11px] font-medium mb-2">{{ outputSource.name }}</div>
            <input
              v-model="outputPath"
              type="text"
              placeholder="选择保存位置..."
              class="w-full bg-chip border border-border rounded px-3 py-1.5 text-[11px]"
            />
          </div>
        </div>

        <!-- No data sources message -->
        <div v-if="!inputSources.length && !outputSource" class="text-center text-text-light py-4">
          此 SOP 不需要配置数据源
        </div>
      </div>

      <!-- Footer -->
      <div class="px-5 py-4 border-t border-border flex justify-end gap-2 flex-shrink-0">
        <Button variant="secondary" @click="$emit('close')">取消</Button>
        <Button variant="primary" :disabled="!canExecute" @click="handleExecute">
          开始执行
        </Button>
      </div>
    </div>
  </div>
</template>
