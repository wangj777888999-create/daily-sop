<script setup lang="ts">
import Card from '@/ui/components/common/Card.vue'
import Button from '@/ui/components/common/Button.vue'
import type { SearchResult } from '@/types/knowledge'

const props = defineProps<{
  result: SearchResult
}>()

const emit = defineEmits<{
  view: [docId: string]
  cite: [result: SearchResult]
}>()

const typeColors: Record<string, [string, string]> = {
  PDF: ['#C17F3A', '#FFE8D6'],
  XLSX: ['#5B8F7A', '#D6EDE7'],
  DOCX: ['#3A7FC1', '#D6E4ED'],
  TXT: ['#6B5F52', '#E5DDD0'],
  MD: ['#7B6BAA', '#E8E2F6'],
}

function scorePercent(): string {
  return (props.result.score * 100).toFixed(0) + '%'
}
</script>

<template>
  <Card :hoverable="true" class="flex gap-3 items-start">
    <div
      class="w-[38px] h-[38px] rounded-lg flex items-center justify-center text-[10px] font-bold flex-shrink-0"
      :style="{
        backgroundColor: typeColors[result.doc_type]?.[1] || '#eee',
        color: typeColors[result.doc_type]?.[0] || '#999'
      }"
    >
      {{ result.doc_type }}
    </div>
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2 mb-1">
        <span class="text-[13px] font-bold text-text-heading truncate">{{ result.doc_name }}</span>
        <span class="text-[10px] px-1.5 py-0.5 rounded-full bg-accent-light text-accent flex-shrink-0">
          相关度 {{ scorePercent() }}
        </span>
      </div>
      <div v-if="result.heading_path" class="text-[10px] text-text-light mb-1">
        {{ result.heading_path }}
      </div>
      <p class="text-[11px] text-text-light leading-relaxed line-clamp-3">{{ result.chunk_text }}</p>
    </div>
    <div class="flex gap-1 flex-shrink-0">
      <Button size="small" variant="secondary" @click="emit('view', result.doc_id)">查看</Button>
      <Button size="small" variant="primary" @click="emit('cite', result)">引用</Button>
    </div>
  </Card>
</template>
