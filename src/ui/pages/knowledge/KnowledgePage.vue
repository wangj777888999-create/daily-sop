<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Card from '@/ui/components/common/Card.vue'
import Button from '@/ui/components/common/Button.vue'
import SearchBox from '@/ui/components/common/SearchBox.vue'
import DocumentCard from '@/ui/components/knowledge/DocumentCard.vue'
import UploadDialog from '@/ui/components/knowledge/UploadDialog.vue'
import DocumentPreview from '@/ui/components/knowledge/DocumentPreview.vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import { getDocumentDownloadUrl, generateContent } from '@/services/knowledgeApi'
import type { DocCategory, RAGResponse } from '@/types/knowledge'

const store = useKnowledgeStore()

// Tab management
type TabId = 'policy' | 'activity' | 'qa' | 'write'
const activeTab = ref<TabId>('policy')

const tabs: { id: TabId; label: string }[] = [
  { id: 'policy', label: '政策文件' },
  { id: 'activity', label: '活动报告' },
  { id: 'qa', label: '智能问答' },
  { id: 'write', label: '辅助撰写' },
]

// Doc management tabs
const docSearchQuery = ref('')
const showUpload = ref(false)
const uploadCategory = ref<DocCategory>('policy')
const uploading = ref(false)
const uploadProgress = ref('')
const uploadError = ref('')
const previewDocId = ref('')
const previewDocName = ref('')

// Category map for doc tabs
const tabToCategory: Record<string, DocCategory> = {
  policy: 'policy',
  activity: 'activity',
}
const categoryLabels: Record<string, string> = {
  policy: '政策文件',
  activity: '活动报告',
}

function currentDocCategory(): DocCategory | null {
  return tabToCategory[activeTab.value] ?? null
}

const currentDocs = computed(() => {
  const cat = currentDocCategory()
  const all = store.documentsByCategory(cat)
  const q = docSearchQuery.value.trim().toLowerCase()
  if (!q) return all
  return all.filter(d => d.name.toLowerCase().includes(q) || d.tags?.some(t => t.toLowerCase().includes(q)))
})

function openUpload() {
  const cat = currentDocCategory()
  uploadCategory.value = cat ?? 'policy'
  uploadError.value = ''
  showUpload.value = true
}

async function handleUpload(files: File[], category: DocCategory) {
  uploading.value = true
  uploadError.value = ''
  uploadProgress.value = ''
  const errors: string[] = []
  try {
    for (let i = 0; i < files.length; i++) {
      uploadProgress.value = `${i + 1} / ${files.length}：${files[i].name}`
      try {
        await store.uploadDocument(files[i], undefined, [], category)
      } catch (e: any) {
        errors.push(`${files[i].name}：${e?.message || '失败'}`)
      }
    }
    if (errors.length === 0) {
      showUpload.value = false
    } else {
      uploadError.value = errors.join('\n')
    }
  } finally {
    uploading.value = false
    uploadProgress.value = ''
  }
}

function handlePreview(docId: string) {
  const doc = store.documents.find(d => d.id === docId)
  if (doc) {
    previewDocId.value = doc.id
    previewDocName.value = doc.name
  }
}

function handleDownload(docId: string) {
  window.open(getDocumentDownloadUrl(docId), '_blank')
}

function handleDelete(docId: string) {
  if (confirm('确定删除此文档？')) {
    store.deleteDocument(docId)
  }
}

// Q&A tab
interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: RAGResponse['sources']
  expandedSources?: boolean
}

const qaCategory = ref<DocCategory | ''>('')
const qaInput = ref('')
const qaLoading = ref(false)
const qaMessages = ref<ChatMessage[]>([])
const qaError = ref('')

const qaCategoryOptions: { value: DocCategory | ''; label: string }[] = [
  { value: '', label: '全部' },
  { value: 'policy', label: '政策文件' },
  { value: 'activity', label: '活动报告' },
]

async function sendQA() {
  const prompt = qaInput.value.trim()
  if (!prompt || qaLoading.value) return
  qaMessages.value.push({ role: 'user', content: prompt })
  qaInput.value = ''
  qaLoading.value = true
  qaError.value = ''
  try {
    const res = await generateContent({
      prompt,
      style: 'general',
      top_k: 5,
      category: qaCategory.value || undefined,
    })
    qaMessages.value.push({
      role: 'assistant',
      content: res.generated_text,
      sources: res.sources,
      expandedSources: false,
    })
  } catch (e: any) {
    qaError.value = e?.message || '生成失败，请重试'
  } finally {
    qaLoading.value = false
  }
}

function qaKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendQA()
  }
}

// Write tab
const writeCategory = ref<DocCategory | ''>('')
const writeStyle = ref<'policy' | 'report' | 'general'>('general')
const writePrompt = ref('')
const writeLoading = ref(false)
const writeResult = ref('')
const writeSources = ref<RAGResponse['sources']>([])
const writeError = ref('')
const writeCopied = ref(false)

const writeCategoryOptions = qaCategoryOptions
const writeStyleOptions: { value: 'policy' | 'report' | 'general'; label: string }[] = [
  { value: 'policy', label: '政策风格' },
  { value: 'report', label: '报告风格' },
  { value: 'general', label: '通用' },
]

async function generateDraft() {
  const prompt = writePrompt.value.trim()
  if (!prompt || writeLoading.value) return
  writeLoading.value = true
  writeError.value = ''
  writeResult.value = ''
  writeSources.value = []
  try {
    const res = await generateContent({
      prompt,
      style: writeStyle.value,
      top_k: 5,
      category: writeCategory.value || undefined,
    })
    writeResult.value = res.generated_text
    writeSources.value = res.sources
  } catch (e: any) {
    writeError.value = e?.message || '生成失败，请重试'
  } finally {
    writeLoading.value = false
  }
}

async function copyResult() {
  if (!writeResult.value) return
  await navigator.clipboard.writeText(writeResult.value)
  writeCopied.value = true
  setTimeout(() => { writeCopied.value = false }, 2000)
}

onMounted(async () => {
  await Promise.all([store.loadDocuments(), store.loadFolders(), store.loadTags()])
})
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Tab bar -->
    <div class="flex items-center border-b border-border mb-4 gap-0">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="px-4 py-2 text-[13px] font-medium transition-colors whitespace-nowrap"
        :class="activeTab === tab.id
          ? 'border-b-2 border-accent text-accent'
          : 'text-text-light hover:text-text-body border-b-2 border-transparent'"
        @click="activeTab = tab.id"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- Policy / Activity tabs -->
    <template v-if="activeTab === 'policy' || activeTab === 'activity'">
      <div class="flex items-center gap-2 mb-4">
        <SearchBox v-model="docSearchQuery" :placeholder="`搜索${categoryLabels[tabToCategory[activeTab]]}...`" class="flex-1" />
        <Button variant="primary" icon="📤" @click="openUpload">上传文档</Button>
      </div>
      <div v-if="store.loading" class="grid grid-cols-3 gap-2.5">
        <Card v-for="i in 6" :key="i" class="h-[120px] animate-pulse">
          <div class="h-[58px] rounded-md bg-placeholder mb-2" />
          <div class="h-3 w-3/4 bg-placeholder rounded mb-1" />
          <div class="h-2 w-1/2 bg-placeholder rounded" />
        </Card>
      </div>
      <div v-else-if="currentDocs.length === 0" class="flex-1 flex items-center justify-center">
        <div class="text-center">
          <div class="text-[36px] mb-2">📂</div>
          <p class="text-[13px] text-text-body mb-1">暂无{{ categoryLabels[tabToCategory[activeTab]] }}</p>
          <p class="text-[11px] text-text-light mb-3">点击上传按钮添加文档</p>
          <Button variant="primary" @click="openUpload">📤 上传文档</Button>
        </div>
      </div>
      <div v-else class="grid grid-cols-3 gap-2.5">
        <DocumentCard v-for="doc in currentDocs" :key="doc.id" :document="doc"
          @preview="handlePreview" @download="handleDownload" @delete="handleDelete" />
      </div>
    </template>

    <!-- Q&A tab -->
    <template v-if="activeTab === 'qa'">
      <div class="flex flex-col h-full min-h-0">
        <!-- Category selector -->
        <div class="flex items-center gap-2 mb-3">
          <span class="text-[12px] text-text-light">检索范围：</span>
          <button
            v-for="opt in qaCategoryOptions"
            :key="opt.value"
            class="px-3 py-1 text-[12px] rounded-full border transition-colors"
            :class="qaCategory === opt.value
              ? 'border-accent bg-accent-light text-accent font-medium'
              : 'border-border text-text-body hover:border-accent'"
            @click="qaCategory = opt.value"
          >
            {{ opt.label }}
          </button>
        </div>

        <!-- Messages -->
        <div class="flex-1 overflow-y-auto flex flex-col gap-3 mb-3 min-h-0">
          <div v-if="qaMessages.length === 0" class="flex-1 flex items-center justify-center text-center">
            <div>
              <div class="text-[32px] mb-2">💬</div>
              <p class="text-[13px] text-text-body mb-1">向知识库提问</p>
              <p class="text-[11px] text-text-light">可以选择检索范围后输入问题</p>
            </div>
          </div>

          <template v-for="(msg, idx) in qaMessages" :key="idx">
            <!-- User message -->
            <div v-if="msg.role === 'user'" class="flex justify-end">
              <div class="max-w-[70%] bg-accent text-white rounded-xl px-4 py-2.5 text-[13px] leading-relaxed">
                {{ msg.content }}
              </div>
            </div>

            <!-- Assistant message -->
            <div v-else class="flex flex-col gap-1.5">
              <div class="max-w-[85%] bg-page-bg rounded-xl px-4 py-3 text-[13px] text-text-body leading-relaxed border border-border whitespace-pre-wrap">
                {{ msg.content }}
              </div>
              <!-- Sources -->
              <div v-if="msg.sources && msg.sources.length > 0" class="ml-2">
                <button
                  class="text-[11px] text-text-light hover:text-accent transition-colors"
                  @click="msg.expandedSources = !msg.expandedSources"
                >
                  {{ msg.expandedSources ? '▲' : '▶' }} 参考来源（{{ msg.sources.length }}）
                </button>
                <div v-if="msg.expandedSources" class="mt-1.5 flex flex-col gap-1.5">
                  <div
                    v-for="(src, si) in msg.sources"
                    :key="si"
                    class="bg-card-bg border border-border rounded-lg px-3 py-2 text-[11px]"
                  >
                    <div class="font-medium text-text-heading mb-0.5">{{ src.doc_name }}</div>
                    <div class="text-text-light mb-1" v-if="src.location">{{ src.location }}</div>
                    <div class="text-text-body leading-relaxed" v-if="src.content">{{ src.content }}</div>
                  </div>
                </div>
              </div>
            </div>
          </template>

          <!-- Loading indicator -->
          <div v-if="qaLoading" class="flex items-center gap-2 text-[12px] text-text-light">
            <div class="w-2 h-2 rounded-full bg-accent animate-bounce" style="animation-delay: 0ms" />
            <div class="w-2 h-2 rounded-full bg-accent animate-bounce" style="animation-delay: 150ms" />
            <div class="w-2 h-2 rounded-full bg-accent animate-bounce" style="animation-delay: 300ms" />
          </div>

          <!-- Error -->
          <div v-if="qaError" class="text-[12px] text-red-500 px-2">{{ qaError }}</div>
        </div>

        <!-- Input -->
        <div class="flex items-end gap-2 border border-border rounded-xl px-3 py-2 bg-card-bg">
          <textarea
            v-model="qaInput"
            placeholder="输入问题，按 Enter 发送（Shift+Enter 换行）..."
            rows="2"
            class="flex-1 text-[13px] text-text-body bg-transparent outline-none resize-none"
            @keydown="qaKeydown"
          />
          <Button variant="primary" size="small" :disabled="!qaInput.trim() || qaLoading" @click="sendQA">发送</Button>
        </div>
      </div>
    </template>

    <!-- Write tab -->
    <template v-if="activeTab === 'write'">
      <div class="flex gap-4 flex-1 min-h-0">
        <!-- Left panel 40% -->
        <div class="w-[40%] flex flex-col gap-3">
          <div>
            <label class="text-[11px] text-text-light mb-1 block">参考分类</label>
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="opt in writeCategoryOptions"
                :key="opt.value"
                class="px-3 py-1 text-[12px] rounded-full border transition-colors"
                :class="writeCategory === opt.value
                  ? 'border-accent bg-accent-light text-accent font-medium'
                  : 'border-border text-text-body hover:border-accent'"
                @click="writeCategory = opt.value"
              >
                {{ opt.label }}
              </button>
            </div>
          </div>

          <div>
            <label class="text-[11px] text-text-light mb-1 block">写作风格</label>
            <div class="flex gap-1.5">
              <button
                v-for="opt in writeStyleOptions"
                :key="opt.value"
                class="flex-1 py-1.5 text-[12px] rounded-md border transition-colors"
                :class="writeStyle === opt.value
                  ? 'border-accent bg-accent-light text-accent font-medium'
                  : 'border-border text-text-body hover:border-accent'"
                @click="writeStyle = opt.value"
              >
                {{ opt.label }}
              </button>
            </div>
          </div>

          <div class="flex-1 flex flex-col">
            <label class="text-[11px] text-text-light mb-1 block">内容需求</label>
            <textarea
              v-model="writePrompt"
              placeholder="描述你想写的段落内容和要求..."
              class="flex-1 w-full bg-page-bg border border-border rounded-lg px-3 py-2.5 text-[13px] text-text-body outline-none focus:border-accent resize-none min-h-[160px]"
            />
          </div>

          <Button
            variant="primary"
            class="w-full justify-center"
            :disabled="!writePrompt.trim() || writeLoading"
            @click="generateDraft"
          >
            {{ writeLoading ? '生成中...' : '生成草稿' }}
          </Button>

          <div v-if="writeError" class="text-[12px] text-red-500">{{ writeError }}</div>
        </div>

        <!-- Right panel 60% -->
        <div class="flex-1 flex flex-col gap-2 min-h-0">
          <div class="flex items-center justify-between">
            <span class="text-[13px] font-semibold text-text-heading">生成结果</span>
            <Button
              v-if="writeResult"
              variant="secondary"
              size="small"
              @click="copyResult"
            >
              {{ writeCopied ? '已复制 ✓' : '复制' }}
            </Button>
          </div>

          <div class="flex-1 overflow-y-auto">
            <!-- Placeholder -->
            <div
              v-if="!writeResult && !writeLoading"
              class="h-full flex items-center justify-center text-center border-2 border-dashed border-border rounded-xl"
            >
              <div>
                <div class="text-[32px] mb-2">✍️</div>
                <p class="text-[13px] text-text-light">填写需求后点击「生成草稿」</p>
              </div>
            </div>

            <!-- Loading -->
            <div v-else-if="writeLoading" class="h-full flex items-center justify-center">
              <div class="text-center">
                <div class="flex gap-1.5 justify-center mb-2">
                  <div class="w-2 h-2 rounded-full bg-accent animate-bounce" style="animation-delay: 0ms" />
                  <div class="w-2 h-2 rounded-full bg-accent animate-bounce" style="animation-delay: 150ms" />
                  <div class="w-2 h-2 rounded-full bg-accent animate-bounce" style="animation-delay: 300ms" />
                </div>
                <p class="text-[12px] text-text-light">正在生成...</p>
              </div>
            </div>

            <!-- Result -->
            <div v-else class="flex flex-col gap-3">
              <pre class="whitespace-pre-wrap text-[13px] text-text-body leading-relaxed bg-page-bg border border-border rounded-xl px-4 py-3">{{ writeResult }}</pre>

              <!-- Sources -->
              <div v-if="writeSources.length > 0">
                <p class="text-[11px] text-text-light mb-1.5">参考来源</p>
                <div class="flex flex-col gap-1.5">
                  <div
                    v-for="(src, si) in writeSources"
                    :key="si"
                    class="bg-card-bg border border-border rounded-lg px-3 py-2 text-[11px]"
                  >
                    <div class="font-medium text-text-heading mb-0.5">{{ src.doc_name }}</div>
                    <div class="text-text-light" v-if="src.location">{{ src.location }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>

  <!-- Upload Dialog -->
  <UploadDialog
    v-if="showUpload"
    :default-category="uploadCategory"
    :uploading="uploading"
    :upload-progress="uploadProgress"
    :error="uploadError"
    @upload="handleUpload"
    @close="showUpload = false"
  />

  <!-- Document Preview -->
  <DocumentPreview
    v-if="previewDocId"
    :doc-id="previewDocId"
    :doc-name="previewDocName"
    @close="previewDocId = ''"
  />
</template>
