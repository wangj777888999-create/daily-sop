<script setup lang="ts">
import { ref } from 'vue'
import Card from '@/ui/components/common/Card.vue'
import Button from '@/ui/components/common/Button.vue'
import type { DocCategory } from '@/types/knowledge'

interface Props {
  defaultCategory?: DocCategory
  uploading?: boolean
  uploadProgress?: string   // e.g. "2 / 5"
  error?: string
}

const props = withDefaults(defineProps<Props>(), {
  defaultCategory: 'policy',
  uploading: false,
  uploadProgress: '',
  error: '',
})

const emit = defineEmits<{
  upload: [files: File[], category: DocCategory]
  close: []
}>()

const dragOver = ref(false)
const files = ref<File[]>([])
const selectedCategory = ref<DocCategory>(props.defaultCategory)

const categories: { value: DocCategory; label: string }[] = [
  { value: 'policy', label: '政策文件' },
  { value: 'activity', label: '活动报告' },
  { value: 'data', label: '经营数据报告' },
]

const allowedTypes = ['.pdf', '.docx', '.xlsx', '.xls', '.txt', '.md']

function onDragOver(e: DragEvent) {
  e.preventDefault()
  dragOver.value = true
}
function onDragLeave() { dragOver.value = false }

function onDrop(e: DragEvent) {
  e.preventDefault()
  dragOver.value = false
  if (e.dataTransfer?.files) addFiles(Array.from(e.dataTransfer.files))
}

function onFileInput(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.length) addFiles(Array.from(input.files))
  input.value = ''
}

function addFiles(incoming: File[]) {
  for (const f of incoming) {
    const ext = '.' + f.name.split('.').pop()?.toLowerCase()
    if (!allowedTypes.includes(ext)) {
      alert(`不支持的文件类型: ${f.name}（${ext}）`)
      continue
    }
    if (f.size > 100 * 1024 * 1024) {
      alert(`${f.name} 超过 100MB 限制`)
      continue
    }
    if (!files.value.find(existing => existing.name === f.name)) {
      files.value.push(f)
    }
  }
}

function removeFile(index: number) {
  files.value.splice(index, 1)
}

function handleUpload() {
  if (!files.value.length) return
  emit('upload', [...files.value], selectedCategory.value)
}

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
</script>

<template>
  <div class="fixed inset-0 bg-black/20 flex items-center justify-center z-50" @click.self="emit('close')">
    <Card class="w-[460px] max-h-[85vh] overflow-y-auto">
      <h3 class="text-[15px] font-bold text-text-heading mb-3">上传文档到知识库</h3>

      <!-- Drop zone -->
      <div
        class="border-2 border-dashed rounded-xl p-5 text-center cursor-pointer mb-3 transition-colors"
        :class="dragOver ? 'border-accent bg-accent-light' : 'border-border hover:border-accent'"
        @dragover="onDragOver"
        @dragleave="onDragLeave"
        @drop="onDrop"
        @click="($refs.fileInput as HTMLInputElement)?.click()"
      >
        <input
          ref="fileInput"
          type="file"
          multiple
          :accept="allowedTypes.join(',')"
          class="hidden"
          @change="onFileInput"
        />
        <div class="text-[26px] mb-1">📂</div>
        <div class="text-[13px] text-text-body mb-0.5">拖拽文件到此处，或点击选择</div>
        <div class="text-[10px] text-text-light">支持多选 · PDF、DOCX、XLSX、TXT、MD · 每个最大 100MB</div>
      </div>

      <!-- File list -->
      <div v-if="files.length" class="mb-3 flex flex-col gap-1.5 max-h-[180px] overflow-y-auto">
        <div
          v-for="(f, i) in files"
          :key="f.name"
          class="flex items-center gap-2 px-3 py-2 bg-page-bg rounded-lg border border-border text-[12px]"
        >
          <span class="text-base">📄</span>
          <span class="flex-1 truncate text-text-body">{{ f.name }}</span>
          <span class="text-text-light shrink-0">{{ formatSize(f.size) }}</span>
          <button
            class="text-text-light hover:text-red-500 transition-colors shrink-0 ml-1"
            :disabled="props.uploading"
            @click.stop="removeFile(i)"
          >✕</button>
        </div>
      </div>

      <!-- Category -->
      <div class="mb-2">
        <label class="text-[11px] text-text-light mb-1 block">文档分类</label>
        <div class="flex gap-2">
          <button
            v-for="cat in categories"
            :key="cat.value"
            class="flex-1 py-1.5 text-[12px] rounded-md border transition-colors"
            :class="selectedCategory === cat.value
              ? 'border-accent bg-accent-light text-accent font-medium'
              : 'border-border text-text-body hover:border-accent'"
            @click="selectedCategory = cat.value"
          >
            {{ cat.label }}
          </button>
        </div>
      </div>

      <!-- Error -->
      <div v-if="props.error" class="mt-2 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-[12px] text-red-600">
        {{ props.error }}
      </div>

      <!-- Progress -->
      <div v-if="props.uploading" class="mt-2 px-3 py-2 bg-accent-light border border-accent/20 rounded-lg text-[12px] text-accent">
        <span v-if="props.uploadProgress">⏳ 正在上传 {{ props.uploadProgress }}，请稍候…</span>
        <span v-else>⏳ 正在解析并建立索引，首次上传需加载语言模型，约需 20-60 秒…</span>
      </div>

      <div class="flex items-center gap-2 justify-end mt-3">
        <span v-if="files.length && !props.uploading" class="text-[11px] text-text-light mr-auto">
          已选 {{ files.length }} 个文件
        </span>
        <Button variant="secondary" size="small" @click="emit('close')" :disabled="props.uploading">取消</Button>
        <Button variant="primary" size="small" @click="handleUpload" :disabled="!files.length || props.uploading">
          {{ props.uploading ? '上传中...' : `上传${files.length > 1 ? ` (${files.length})` : ''}` }}
        </Button>
      </div>
    </Card>
  </div>
</template>
