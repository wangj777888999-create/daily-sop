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
type TabId = 'policy' | 'activity' | 'data' | 'qa' | 'write'
const activeTab = ref<TabId>('policy')

const tabs: { id: TabId; label: string }[] = [
  { id: 'policy', label: '政策文件' },
  { id: 'activity', label: '活动报告' },
  { id: 'data', label: '经营数据报告' },
  { id: 'qa', label: '智能问答' },
  { id: 'write', label: '辅助撰写' },
]

// Doc management tabs
const docSearchQuery = ref('')
const showUpload = ref(false)
const uploadCategory = ref<DocCategory>('policy')
const previewDocId = ref('')
const previewDocName = ref('')

// Category map for doc tabs
const tabToCategory: Record<string, DocCategory> = {
  policy: 'policy',
  activity: 'activity',
  data: 'data',
}
const categoryLabels: Record<DocCategory, string> = {
  policy: '政策文件',
  activity: '活动报告',
  data: '经营数据报告',
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
  showUpload.value = true
}

function handleUpload(file: File, category: DocCategory) {
  store.uploadDocument(file, undefined, [], category)
  showUpload.value = false
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

// ── 经营数据归档视图 ────────────────────────────────────────────────────────
interface MonthGroup {
  key: string   // "2025-04"
  year: number
  month: number
  docs: typeof store.documents
}

function detectReportType(name: string): { label: string; color: string } {
  if (name.includes('校内')) return { label: '校内月报', color: 'orange' }
  if (name.includes('校外')) return { label: '校外月报', color: 'blue' }
  if (name.includes('折扣率')) return { label: '折扣率', color: 'purple' }
  return { label: '报告', color: 'gray' }
}

const dataGroupedByMonth = computed((): MonthGroup[] => {
  const dataDocs = store.documentsByCategory('data')
  const groups: Record<string, MonthGroup> = {}
  const ungrouped: typeof store.documents = []

  for (const doc of dataDocs) {
    const m = doc.name.match(/(\d{4})年(\d{1,2})月/)
    if (m) {
      const year = parseInt(m[1])
      const month = parseInt(m[2])
      const key = `${year}-${String(month).padStart(2, '0')}`
      if (!groups[key]) groups[key] = { key, year, month, docs: [] }
      groups[key].docs.push(doc)
    } else {
      ungrouped.push(doc)
    }
  }

  const sorted = Object.values(groups).sort((a, b) => b.key.localeCompare(a.key))
  // 无法解析年月的文档放在最后一组
  if (ungrouped.length) sorted.push({ key: 'other', year: 0, month: 0, docs: ungrouped })
  return sorted
})

// Q&A tab
interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: RAGResponse['sources']
  expandedSources?: boolean
}

const qaCategory = ref<DocCategory | ''>('')
const qaDocIds = ref<string[]>([])   // 空=不限，非空=限定到这批文档
const qaMonthLabel = ref('')          // 显示用："2025年4月"
const qaInput = ref('')
const qaLoading = ref(false)
const qaMessages = ref<ChatMessage[]>([])
const qaError = ref('')

function enterMonthQA(group: MonthGroup) {
  qaDocIds.value = group.docs.map(d => d.id)
  qaMonthLabel.value = group.year ? `${group.year}年${group.month}月` : '其他报告'
  qaCategory.value = 'data'
  qaMessages.value = []
  qaError.value = ''
  activeTab.value = 'qa'
}

function clearQAScope() {
  qaDocIds.value = []
  qaMonthLabel.value = ''
}

const qaCategoryOptions: { value: DocCategory | ''; label: string }[] = [
  { value: '', label: '全部' },
  { value: 'policy', label: '政策文件' },
  { value: 'activity', label: '活动报告' },
  { value: 'data', label: '经营数据报告' },
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
      doc_ids: qaDocIds.value.length > 0 ? qaDocIds.value : undefined,
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

    <!-- 经营数据 tab — 按年月归档 -->
    <template v-if="activeTab === 'data'">
      <div class="flex items-center gap-2 mb-4">
        <span class="text-[13px] text-text-light flex-1">分析报告按月归档，生成后自动入库</span>
        <Button variant="primary" icon="📤" @click="openUpload">手动上传</Button>
      </div>

      <!-- Loading -->
      <div v-if="store.loading" class="flex flex-col gap-3">
        <div v-for="i in 3" :key="i" class="h-16 rounded-xl bg-placeholder animate-pulse" />
      </div>

      <!-- Empty -->
      <div v-else-if="dataGroupedByMonth.length === 0" class="flex-1 flex items-center justify-center">
        <div class="text-center">
          <div class="text-[36px] mb-2">📊</div>
          <p class="text-[13px] text-text-body mb-1">暂无经营数据报告</p>
          <p class="text-[11px] text-text-light">运行校内/校外月报分析后自动归档，或手动上传</p>
        </div>
      </div>

      <!-- Archive list -->
      <div v-else class="flex flex-col gap-2 overflow-y-auto">
        <div
          v-for="group in dataGroupedByMonth"
          :key="group.key"
          class="border border-border rounded-xl px-4 py-3 flex items-center gap-3 hover:border-accent/40 transition-colors"
        >
          <!-- Month label -->
          <div class="w-20 shrink-0">
            <template v-if="group.year">
              <p class="text-[13px] font-bold text-text-heading">{{ group.month }}月</p>
              <p class="text-[11px] text-text-light">{{ group.year }}年</p>
            </template>
            <p v-else class="text-[12px] text-text-light">其他</p>
          </div>

          <!-- Report badges -->
          <div class="flex flex-wrap gap-1.5 flex-1">
            <div
              v-for="doc in group.docs"
              :key="doc.id"
              class="flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border"
              :class="{
                'bg-orange-50 text-orange-600 border-orange-200': detectReportType(doc.name).color === 'orange',
                'bg-blue-50 text-blue-600 border-blue-200': detectReportType(doc.name).color === 'blue',
                'bg-purple-50 text-purple-600 border-purple-200': detectReportType(doc.name).color === 'purple',
                'bg-gray-50 text-gray-600 border-gray-200': detectReportType(doc.name).color === 'gray',
              }"
            >
              ✓ {{ detectReportType(doc.name).label }}
            </div>
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-2 shrink-0">
            <span class="text-[11px] text-text-light">{{ group.docs.length }} 份</span>
            <button
              class="px-3 py-1 text-[12px] rounded-lg bg-accent text-white hover:bg-accent/90 transition-colors font-medium"
              @click="enterMonthQA(group)"
            >
              本月问答 →
            </button>
            <button
              class="text-[11px] text-text-light hover:text-red-500 transition-colors"
              @click="group.docs.forEach(d => handleDelete(d.id))"
            >
              删除
            </button>
          </div>
        </div>
      </div>
    </template>

    <!-- Q&A tab -->
    <template v-if="activeTab === 'qa'">
      <div class="flex flex-col h-full min-h-0">
        <!-- 月份范围提示条 -->
        <div v-if="qaDocIds.length > 0" class="flex items-center gap-2 mb-2 px-3 py-2 bg-accent-light border border-accent/30 rounded-lg">
          <span class="text-[12px] text-accent font-medium">📊 {{ qaMonthLabel }} 报告（{{ qaDocIds.length }} 份）</span>
          <button class="ml-auto text-[11px] text-text-light hover:text-accent" @click="clearQAScope">✕ 清除范围</button>
        </div>

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
            @click="qaCategory = opt.value; clearQAScope()"
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
