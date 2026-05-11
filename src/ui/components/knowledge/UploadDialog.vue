<script setup lang="ts">
import { ref } from 'vue'
import Card from '@/ui/components/common/Card.vue'
import Button from '@/ui/components/common/Button.vue'

const emit = defineEmits<{
  upload: [file: File, folderId: string, tags: string[]]
  close: []
}>()

const dragOver = ref(false)
const file = ref<File | null>(null)
const folderId = ref('')
const tagsInput = ref('')

const allowedTypes = ['.pdf', '.docx', '.xlsx', '.xls', '.txt', '.md']

function onDragOver(e: DragEvent) {
  e.preventDefault()
  dragOver.value = true
}

function onDragLeave() {
  dragOver.value = false
}

function onDrop(e: DragEvent) {
  e.preventDefault()
  dragOver.value = false
  const files = e.dataTransfer?.files
  if (files?.length) {
    validateAndSet(files[0])
  }
}

function onFileInput(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.length) {
    validateAndSet(input.files[0])
  }
}

function validateAndSet(f: File) {
  const ext = '.' + f.name.split('.').pop()?.toLowerCase()
  if (!allowedTypes.includes(ext)) {
    alert(`不支持的文件类型: ${ext}。支持: ${allowedTypes.join(', ')}`)
    return
  }
  if (f.size > 100 * 1024 * 1024) {
    alert('文件大小超过 100MB 限制')
    return
  }
  file.value = f
}

function handleUpload() {
  if (!file.value) return
  const tags = tagsInput.value.split(',').map(t => t.trim()).filter(Boolean)
  emit('upload', file.value, folderId.value, tags)
}

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
</script>

<template>
  <div class="fixed inset-0 bg-black/20 flex items-center justify-center z-50" @click.self="emit('close')">
    <Card class="w-[420px] max-h-[80vh] overflow-y-auto">
      <h3 class="text-[15px] font-bold text-text-heading mb-3">上传文档到知识库</h3>

      <div
        class="border-2 border-dashed rounded-xl p-6 text-center cursor-pointer mb-3 transition-colors"
        :class="dragOver ? 'border-accent bg-accent-light' : 'border-border hover:border-accent'"
        @dragover="onDragOver"
        @dragleave="onDragLeave"
        @drop="onDrop"
        @click="($refs.fileInput as HTMLInputElement)?.click()"
      >
        <input
          ref="fileInput"
          type="file"
          :accept="allowedTypes.join(',')"
          class="hidden"
          @change="onFileInput"
        />
        <div class="text-[28px] mb-1">📄</div>
        <div class="text-[13px] text-text-body mb-1" v-if="!file">拖拽文件到此处，或点击选择</div>
        <div class="text-[13px] font-semibold text-accent" v-else>
          {{ file.name }} ({{ formatSize(file.size) }})
        </div>
        <div class="text-[10px] text-text-light">支持 PDF、DOCX、XLSX、TXT、MD，最大 100MB</div>
      </div>

      <div class="mb-2">
        <label class="text-[11px] text-text-light mb-1 block">标签（逗号分隔）</label>
        <input
          v-model="tagsInput"
          type="text"
          placeholder="如：政策, 2024, 教育"
          class="w-full bg-page-bg border border-border rounded-md px-2.5 py-1.5 text-[12px] text-text-body outline-none focus:border-accent"
        />
      </div>

      <div class="flex gap-2 justify-end mt-3">
        <Button variant="secondary" size="small" @click="emit('close')">取消</Button>
        <Button variant="primary" size="small" @click="handleUpload" :disabled="!file">上传</Button>
      </div>
    </Card>
  </div>
</template>
