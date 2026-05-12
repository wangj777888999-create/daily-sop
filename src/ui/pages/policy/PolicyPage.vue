<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Card from '@/ui/components/common/Card.vue'
import Button from '@/ui/components/common/Button.vue'
import Chip from '@/ui/components/common/Chip.vue'
import RowTitle from '@/ui/components/common/RowTitle.vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import type { SearchResult } from '@/types/knowledge'

const kbStore = useKnowledgeStore()
const kbSearchQuery = ref('')
const selectedRefs = ref<SearchResult[]>([])
const generatedContent = ref('')
const editorContent = ref('')
const generating = ref(false)

onMounted(async () => {
  await kbStore.loadDocuments()
})

const outline = computed(() => {
  if (!generatedContent.value) return []
  return generatedContent.value
    .split('\n')
    .filter(line => line.trim().startsWith('#') || line.trim().match(/^第[一二三四五六七八九十]/))
    .map((line, i) => ({
      id: i,
      text: line.replace(/^#+\s*/, '').trim(),
      indent: line.startsWith('##') ? 1 : 0,
      active: i === 0,
    }))
})

async function handleKBSearch() {
  if (kbSearchQuery.value.trim()) {
    await kbStore.search(kbSearchQuery.value.trim())
  }
}

function addReference(result: SearchResult) {
  if (!selectedRefs.value.find(r => r.doc_id === result.doc_id && r.heading_path === result.heading_path)) {
    selectedRefs.value.push(result)
  }
}

function removeReference(index: number) {
  selectedRefs.value.splice(index, 1)
}

async function handleGenerate() {
  if (!editorContent.value.trim()) return
  generating.value = true
  try {
    const uniqueIds = [...new Set(selectedRefs.value.map(r => r.doc_id))]
    const response = await kbStore.generateContent(editorContent.value, uniqueIds, 'policy')
    generatedContent.value = response.generated_text
  } catch (e) {
    console.error('Generation failed:', e)
  } finally {
    generating.value = false
  }
}

const wordCount = computed(() => generatedContent.value.length)
const sectionCount = computed(() => outline.value.length)

async function copyMarkdown() {
  if (!generatedContent.value) return
  await navigator.clipboard.writeText(generatedContent.value)
}
</script>

<template>
  <div class="flex gap-3.5 h-full">
    <Card class="w-[230px] flex-shrink-0 flex flex-col">
      <RowTitle label="文档大纲" />
      <div class="flex-1 overflow-y-auto">
        <div
          v-for="item in outline"
          :key="item.id"
          class="px-2 py-1.5 rounded-md mb-0.5 cursor-pointer text-[12px] transition-colors"
          :class="[
            item.active
              ? 'bg-accent-light text-accent border-l-2 border-accent'
              : 'text-text-body hover:bg-page-bg',
            item.indent ? 'ml-4' : ''
          ]"
          :style="{ paddingLeft: `${8 + (item.indent || 0) * 16}px` }"
        >
          {{ item.text }}
        </div>
        <div v-if="outline.length === 0" class="text-[11px] text-text-light px-2 py-4 text-center">
          生成内容后将自动提取大纲
        </div>
      </div>
      <div class="mt-auto pt-2.5 border-t border-border">
        <Button variant="secondary" style="width: 100%; justify-content: center; font-size: 11px">
          ＋ 添加章节
        </Button>
      </div>
    </Card>

    <div class="flex-1 flex flex-col min-w-0">
      <div class="bg-card-bg border border-border border-b-none rounded-t-lg px-3 py-2 flex items-center gap-1.5 flex-wrap">
        <Chip v-for="t in ['B', 'I', 'U']" :key="t" style="font-size: 10px">{{ t }}</Chip>
        <div class="w-px h-4 bg-border mx-0.5" />
        <Chip v-for="t in ['H1', 'H2']" :key="t" style="font-size: 10px">{{ t }}</Chip>
        <div class="w-px h-4 bg-border mx-0.5" />
        <Chip v-for="t in ['列表', '引用']" :key="t" style="font-size: 10px">{{ t }}</Chip>
        <div class="w-px h-4 bg-border mx-0.5" />
        <Chip style="font-size: 10px">插图</Chip>
        <Chip accent style="font-size: 10px" @click="handleGenerate">AI生成</Chip>
      </div>

      <Card class="flex-1 rounded-t-none overflow-hidden flex flex-col">
        <textarea
          v-if="!generatedContent"
          v-model="editorContent"
          placeholder="在此输入要生成的内容描述，例如：撰写一份校园安全管理政策，包含总则、安全管理职责、安全教育与培训、应急管理、附则等章节..."
          class="flex-1 w-full text-[13px] text-text-body bg-transparent outline-none resize-none p-3 leading-relaxed"
        />
        <div v-else class="flex-1 overflow-y-auto p-3">
          <div class="text-[13px] text-text-body leading-relaxed whitespace-pre-wrap">{{ generatedContent }}</div>
        </div>
        <div v-if="generating" class="px-3 pb-2 text-[11px] text-text-light">
          AI 正在生成内容...
        </div>
        <div v-if="!generatedContent && !editorContent" class="flex-1 flex items-center justify-center">
          <p class="text-[11px] text-text-light">输入生成描述后点击 AI生成 按钮</p>
        </div>
      </Card>
    </div>

    <div class="w-[210px] flex-shrink-0 flex flex-col gap-2.5">
      <Card>
        <RowTitle label="文档信息" />
        <div class="space-y-1.5 text-[11px]">
          <div class="flex justify-between py-1 border-b border-border last:border-b-0">
            <span class="text-text-light">字数</span>
            <span class="text-text-body">{{ wordCount }}</span>
          </div>
          <div class="flex justify-between py-1 border-b border-border last:border-b-0">
            <span class="text-text-light">章节数</span>
            <span class="text-text-body">{{ sectionCount }}</span>
          </div>
          <div class="flex justify-between py-1 border-b border-border last:border-b-0">
            <span class="text-text-light">参考文档</span>
            <span class="text-text-body">{{ selectedRefs.length }}</span>
          </div>
          <div class="flex justify-between py-1 border-b border-border last:border-b-0">
            <span class="text-text-light">状态</span>
            <span class="text-text-body">{{ generatedContent ? '已生成' : '编辑中' }}</span>
          </div>
        </div>
      </Card>

      <Card>
        <RowTitle label="导出" />
        <div class="space-y-1.5">
          <Button variant="secondary" style="width: 100%; justify-content: center; font-size: 11px">导出 Word (.docx)</Button>
          <Button variant="secondary" style="width: 100%; justify-content: center; font-size: 11px">导出 PDF</Button>
          <Button variant="secondary" style="width: 100%; justify-content: center; font-size: 11px" @click="copyMarkdown">复制全文 Markdown</Button>
        </div>
      </Card>

      <Card class="flex-1 flex flex-col">
        <RowTitle label="参考资料" />
        <div class="flex items-center gap-1 mb-2">
          <input
            v-model="kbSearchQuery"
            type="text"
            placeholder="搜索知识库…"
            class="flex-1 bg-page-bg border border-border rounded-md px-2 py-1 text-[11px] text-text-body outline-none"
            @keyup.enter="handleKBSearch"
          />
          <Button variant="primary" size="small" @click="handleKBSearch">搜</Button>
        </div>

        <div class="flex-1 overflow-y-auto space-y-1.5">
          <div v-if="kbStore.searchResults.length > 0" class="text-[10px] text-text-light mb-1">
            搜索结果：
          </div>
          <div
            v-for="r in kbStore.searchResults.slice(0, 5)"
            :key="r.doc_id + r.heading_path"
            class="text-[10px] p-1.5 rounded bg-page-bg cursor-pointer hover:bg-accent-light"
            @click="addReference(r)"
          >
            <div class="font-semibold text-text-heading truncate">{{ r.doc_name }}</div>
            <div class="text-text-light truncate">{{ r.chunk_text.slice(0, 60) }}...</div>
            <div class="text-accent text-[9px]">相关度 {{ (r.score * 100).toFixed(0) }}%</div>
          </div>

          <div v-if="selectedRefs.length > 0" class="mt-2">
            <div class="text-[10px] text-text-light mb-1">已选参考（{{ selectedRefs.length }}）：</div>
            <div v-for="(ref, i) in selectedRefs" :key="i" class="text-[10px] p-1 bg-accent-light rounded mb-1 flex justify-between items-start">
              <div class="truncate flex-1">
                <div class="font-semibold">{{ ref.doc_name }}</div>
                <div class="text-text-light truncate">{{ ref.chunk_text.slice(0, 40) }}...</div>
              </div>
              <span class="cursor-pointer text-text-light ml-1 flex-shrink-0" @click="removeReference(i)">✕</span>
            </div>
            <Button
              variant="primary"
              size="small"
              style="width: 100%; margin-top: 4px; font-size: 10px"
              @click="handleGenerate"
              :disabled="!editorContent.trim()"
            >
              {{ generating ? '生成中...' : '以选中文档为参考生成' }}
            </Button>
          </div>

          <div v-if="kbStore.documents.length === 0 && selectedRefs.length === 0" class="text-[11px] text-text-light text-center py-4">
            知识库为空，请先<router-link to="/knowledge" class="text-accent underline">上传文档</router-link>
          </div>
          <div v-else-if="!kbStore.searchQuery && selectedRefs.length === 0" class="text-[11px] text-text-light text-center py-4">
            搜索知识库中的文档作为参考
          </div>
        </div>
      </Card>
    </div>
  </div>
</template>
