<script setup lang="ts">
import Card from '@/ui/components/common/Card.vue'
import Button from '@/ui/components/common/Button.vue'
import type { KnowledgeDocument } from '@/types/knowledge'

defineProps<{
  document: KnowledgeDocument
}>()

const emit = defineEmits<{
  preview: [id: string]
  download: [id: string]
  delete: [id: string]
}>()

const typeColors: Record<string, [string, string]> = {
  PDF: ['#C17F3A', '#FFE8D6'],
  XLSX: ['#5B8F7A', '#D6EDE7'],
  DOCX: ['#3A7FC1', '#D6E4ED'],
  TXT: ['#6B5F52', '#E5DDD0'],
  MD: ['#7B6BAA', '#E8E2F6'],
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
</script>

<template>
  <Card :hoverable="true" class="flex flex-col gap-2 relative group">
    <div
      class="h-[58px] rounded-md flex items-center justify-center text-[13px] font-bold"
      :style="{
        backgroundColor: typeColors[document.type]?.[1] || '#eee',
        color: typeColors[document.type]?.[0] || '#999'
      }"
    >
      {{ document.type }}
    </div>
    <div class="text-[12px] font-semibold text-text-heading leading-tight truncate">
      {{ document.name }}
    </div>
    <div class="flex justify-between text-[10px] text-text-light">
      <span>{{ formatSize(document.size_bytes) }}</span>
      <span>{{ formatDate(document.created_at) }}</span>
    </div>
    <div class="flex gap-1 mt-1">
      <span
        v-for="tag in document.tags?.slice(0, 3)"
        :key="tag"
        class="text-[9px] px-1.5 py-0.5 rounded-full bg-chip text-text-light"
      >
        {{ tag }}
      </span>
    </div>

    <div class="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
      <Button size="small" variant="secondary" @click.stop="emit('preview', document.id)">查看</Button>
      <Button size="small" variant="secondary" @click.stop="emit('download', document.id)">下载</Button>
      <Button size="small" variant="secondary" @click.stop="emit('delete', document.id)">删除</Button>
    </div>
  </Card>
</template>
