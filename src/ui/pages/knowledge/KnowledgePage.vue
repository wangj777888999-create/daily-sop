<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Card from '@/ui/components/common/Card.vue'
import Button from '@/ui/components/common/Button.vue'
import Chip from '@/ui/components/common/Chip.vue'
import RowTitle from '@/ui/components/common/RowTitle.vue'
import SearchBox from '@/ui/components/common/SearchBox.vue'
import DocumentCard from '@/ui/components/knowledge/DocumentCard.vue'
import UploadDialog from '@/ui/components/knowledge/UploadDialog.vue'
import SearchResultCard from '@/ui/components/knowledge/SearchResultCard.vue'
import DocumentPreview from '@/ui/components/knowledge/DocumentPreview.vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import { getDocumentDownloadUrl } from '@/services/knowledgeApi'

const store = useKnowledgeStore()

const searchQuery = ref('')
const searchText = ref('')
const showUpload = ref(false)
const previewDocId = ref('')
const previewDocName = ref('')
const activeTag = ref('')

onMounted(async () => {
  await Promise.all([store.loadDocuments(), store.loadFolders(), store.loadTags()])
})

const selectedFolderName = computed(() => {
  if (!store.currentFolderId) return '全部文档'
  return store.folders.find(f => f.id === store.currentFolderId)?.name || '全部文档'
})

const fileCount = computed(() => store.documentsInCurrentFolder.length)

function handleSearch() {
  const q = store.viewMode === 'search' ? searchText.value : searchQuery.value
  if (q.trim()) {
    store.search(q.trim())
  }
}

function handleSearchKeyup(e: KeyboardEvent) {
  if (e.key === 'Enter') handleSearch()
}

function handleUpload(file: File, folderId: string, tags: string[]) {
  store.uploadDocument(file, folderId || undefined, tags)
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

function handleNewFolder() {
  const name = prompt('输入文件夹名称：')
  if (name?.trim()) {
    store.createFolder(name.trim())
  }
}

const typeColors: Record<string, [string, string]> = {
  PDF: ['#C17F3A', '#FFE8D6'],
  XLSX: ['#5B8F7A', '#D6EDE7'],
  DOCX: ['#3A7FC1', '#D6E4ED'],
  TXT: ['#6B5F52', '#E5DDD0'],
  MD: ['#7B6BAA', '#E8E2F6'],
}

const fileTypes = ['PDF', 'DOCX', 'XLSX', 'TXT', 'MD']
</script>

<template>
  <div class="flex flex-col h-full">
    <div class="flex items-center gap-2 mb-3.5">
      <SearchBox v-model="searchQuery" placeholder="🔍 语义搜索知识库…" class="flex-1" @keyup.enter="handleSearchKeyup" />
      <Button variant="primary" icon="📤" @click="showUpload = true">上传文档</Button>
      <Button variant="secondary" @click="handleNewFolder">新建文件夹</Button>
    </div>

    <div class="flex gap-2 mb-3">
      <Chip :active="store.viewMode === 'browser'" @click="store.viewMode = 'browser'">文件浏览器</Chip>
      <Chip :active="store.viewMode === 'search'" @click="store.viewMode = 'search'">搜索优先</Chip>
    </div>

    <!-- File Browser Mode -->
    <template v-if="store.viewMode === 'browser'">
      <div class="flex gap-3.5 flex-1 min-h-0">
        <Card class="w-[216px] flex-shrink-0 flex flex-col">
          <RowTitle label="文件夹" />
          <div class="flex-1 overflow-y-auto">
            <div
              class="flex items-center gap-2 px-2.5 py-1.5 rounded-md mb-0.5 cursor-pointer text-[12px]"
              :class="!store.currentFolderId
                ? 'bg-accent-light text-accent border border-accent'
                : 'text-text-body hover:bg-page-bg'"
              @click="store.setFolder(null)"
            >
              <span>📁</span>
              <span class="flex-1">全部文档</span>
              <span class="text-[10px] text-text-light">{{ store.documents.length }}</span>
            </div>
            <div
              v-for="folder in store.folders"
              :key="folder.id"
              class="flex items-center gap-2 px-2.5 py-1.5 rounded-md mb-0.5 cursor-pointer text-[12px]"
              :class="store.currentFolderId === folder.id
                ? 'bg-accent-light text-accent border border-accent'
                : 'text-text-body hover:bg-page-bg'"
              @click="store.setFolder(folder.id)"
            >
              <span>📁</span>
              <span class="flex-1">{{ folder.name }}</span>
            </div>
          </div>

          <div class="mt-3 pt-2.5 border-t border-border">
            <div class="text-[10px] text-text-light mb-1.5">标签筛选</div>
            <div class="flex flex-wrap gap-1">
              <Chip
                v-for="t in store.allTags"
                :key="t"
                :active="activeTag === t"
                style="font-size: 10px"
                @click="activeTag = activeTag === t ? '' : t"
              >
                {{ t }}
              </Chip>
            </div>
          </div>
        </Card>

        <div class="flex-1 flex flex-col min-w-0">
          <div class="flex items-center gap-2 mb-3">
            <span class="text-[13px] font-bold text-text-heading">{{ selectedFolderName }}</span>
            <span class="text-[11px] text-text-light">{{ fileCount }} 个文件</span>
            <div class="ml-auto flex gap-1.5">
              <Chip :active="!store.gridView" style="font-size: 11px" @click="store.gridView = false">≡ 列表</Chip>
              <Chip :active="store.gridView" accent style="font-size: 11px" @click="store.gridView = true">⊞ 网格</Chip>
            </div>
          </div>

          <!-- Loading state -->
          <div v-if="store.loading" class="grid grid-cols-3 gap-2.5">
            <Card v-for="i in 6" :key="i" class="h-[120px] animate-pulse">
              <div class="h-[58px] rounded-md bg-placeholder mb-2" />
              <div class="h-3 w-3/4 bg-placeholder rounded mb-1" />
              <div class="h-2 w-1/2 bg-placeholder rounded" />
            </Card>
          </div>

          <!-- Empty state -->
          <div v-else-if="fileCount === 0" class="flex-1 flex items-center justify-center">
            <div class="text-center">
              <div class="text-[36px] mb-2">📂</div>
              <p class="text-[13px] text-text-body mb-1">知识库为空</p>
              <p class="text-[11px] text-text-light mb-3">上传文档开始构建你的知识库</p>
              <Button variant="primary" @click="showUpload = true">📤 上传第一篇文档</Button>
            </div>
          </div>

          <!-- Document grid -->
          <div v-else :class="store.gridView ? 'grid grid-cols-3 gap-2.5' : 'flex flex-col gap-2'">
            <DocumentCard
              v-for="doc in store.documentsInCurrentFolder"
              :key="doc.id"
              :document="doc"
              @preview="handlePreview"
              @download="handleDownload"
              @delete="handleDelete"
            />
          </div>
        </div>
      </div>
    </template>

    <!-- Search Mode -->
    <template v-else>
      <div class="max-w-[680px] mx-auto mb-5 text-center">
        <h2 class="text-[18px] font-bold text-text-heading mb-1">在知识库中搜索</h2>
        <p class="text-[12px] text-text-light mb-3.5">语义搜索 · 向量相似度检索 · 共 {{ store.documents.length }} 个文档</p>

        <div class="flex items-center gap-2.5 bg-card-bg border-2 border-accent rounded-xl px-4 py-2.5 text-left">
          <span class="text-[16px]">🔍</span>
          <input
            v-model="searchText"
            type="text"
            placeholder="输入查询内容，如：校园安全管理政策..."
            class="flex-1 text-[13px] text-text-body bg-transparent outline-none"
            @keyup.enter="handleSearch"
          />
          <Chip style="font-size: 10px">语义</Chip>
          <Button size="small" variant="primary" @click="handleSearch">搜索</Button>
        </div>
      </div>

      <div class="flex gap-3.5 flex-1 min-h-0">
        <Card class="w-[196px] flex-shrink-0">
          <RowTitle label="筛选" />
          <div class="text-[10px] text-text-light mb-1">文件类型</div>
          <div class="text-[11px] text-text-body space-y-1 mb-3">
            <div v-for="t in fileTypes" :key="t" class="flex items-center gap-1.5 py-1">
              <div
                class="w-3 h-3 rounded border bg-chip border-border"
                :style="{ backgroundColor: typeColors[t]?.[1] || '#eee' }"
              />
              {{ t }}
            </div>
          </div>

          <div class="text-[10px] text-text-light mb-1 mt-3">时间范围</div>
          <div class="text-[11px] text-text-body space-y-1">
            <div class="flex items-center gap-1.5 py-1">
              <div class="w-3 h-3 rounded-full bg-chip border-border" />
              最近 7 天
            </div>
            <div class="flex items-center gap-1.5 py-1">
              <div class="w-3 h-3 rounded-full bg-chip border-border" />
              最近 30 天
            </div>
            <div class="flex items-center gap-1.5 py-1">
              <div class="w-3 h-3 rounded-full bg-chip border-border" />
              全部时间
            </div>
          </div>
        </Card>

        <div class="flex-1 flex flex-col gap-2.5">
          <div class="text-[11px] text-text-light" v-if="!store.searchLoading">
            找到 {{ store.searchResults.length }} 个结果
          </div>

          <div v-if="store.searchLoading" class="text-center py-8">
            <div class="text-[13px] text-text-light">搜索中...</div>
          </div>

          <template v-else-if="store.searchResults.length > 0">
            <SearchResultCard
              v-for="r in store.searchResults"
              :key="r.doc_id + r.heading_path"
              :result="r"
              @view="handlePreview"
            />
          </template>

          <div v-else-if="store.searchQuery" class="text-center py-8">
            <div class="text-[28px] mb-2">🔍</div>
            <p class="text-[13px] text-text-light">没有找到匹配的文档</p>
            <p class="text-[11px] text-text-light">尝试使用不同的关键词搜索</p>
          </div>
        </div>
      </div>
    </template>

    <!-- Upload Dialog -->
    <UploadDialog
      v-if="showUpload"
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
  </div>
</template>
