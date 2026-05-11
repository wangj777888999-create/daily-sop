<script setup lang="ts">
import { ref, watch } from 'vue'
import Card from '@/ui/components/common/Card.vue'
import Button from '@/ui/components/common/Button.vue'
import { getDocumentContent, getDocumentDownloadUrl } from '@/services/knowledgeApi'
import type { ParsedDocument } from '@/types/knowledge'

const props = defineProps<{
  docId: string
  docName: string
}>()

const emit = defineEmits<{
  close: []
}>()

const content = ref<ParsedDocument | null>(null)
const loading = ref(false)

watch(() => props.docId, (newId) => {
  if (newId) loadContent()
}, { immediate: true })

async function loadContent() {
  loading.value = true
  try {
    content.value = await getDocumentContent(props.docId)
  } catch (e) {
    console.error('Failed to load document content:', e)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 bg-black/20 flex items-center justify-center z-50" @click.self="emit('close')">
    <Card class="w-[680px] max-h-[80vh] flex flex-col">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-[15px] font-bold text-text-heading truncate flex-1">{{ docName }}</h3>
        <div class="flex gap-2">
          <a :href="getDocumentDownloadUrl(docId)" target="_blank">
            <Button variant="secondary" size="small">下载</Button>
          </a>
          <Button variant="secondary" size="small" @click="emit('close')">关闭</Button>
        </div>
      </div>

      <div class="flex-1 overflow-y-auto text-[12px] text-text-body leading-relaxed space-y-2">
        <div v-if="loading" class="text-center py-4 text-text-light">加载中...</div>
        <template v-else-if="content">
          <div v-for="(chunk, i) in content.chunks" :key="i">
            <h4 v-if="chunk.chunk_type === 'heading'" class="font-bold mt-3 mb-1" :class="{
              'text-[15px]': chunk.level === 1,
              'text-[13px]': chunk.level === 2,
              'text-[12px]': chunk.level >= 3,
            }">
              {{ chunk.text }}
            </h4>
            <p v-else-if="chunk.chunk_type === 'paragraph'" class="mb-1">
              {{ chunk.text }}
            </p>
            <pre v-else-if="chunk.chunk_type === 'table'" class="text-[10px] bg-page-bg p-2 rounded overflow-x-auto mb-1">{{ chunk.text }}</pre>
            <p v-else class="mb-1 text-text-light">{{ chunk.text }}</p>
          </div>
        </template>
        <div v-else class="text-center py-4 text-text-light">无法加载文档内容</div>
      </div>
    </Card>
  </div>
</template>
