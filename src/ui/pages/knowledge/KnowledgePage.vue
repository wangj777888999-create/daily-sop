<script setup lang="ts">
import { ref, computed } from 'vue'
import Card from '@/ui/components/common/Card.vue'
import Button from '@/ui/components/common/Button.vue'
import Chip from '@/ui/components/common/Chip.vue'
import RowTitle from '@/ui/components/common/RowTitle.vue'
import SearchBox from '@/ui/components/common/SearchBox.vue'

const viewMode = ref<'browser' | 'search'>('browser')
const selectedFolder = ref('')
const searchQuery = ref('')
const gridView = ref(true)
const searchText = ref('')

const folders: Array<{
  id: string
  name: string
  count: number
}> = []

const files: Array<{
  name: string
  type: string
  size: string
  date: string
}> = []

const searchResults: Array<{
  name: string
  match: string
  type: string
  excerpt: string
}> = []

const typeColors: Record<string, [string, string]> = {
  PDF: ['#C17F3A', '#FFE8D6'],
  XLSX: ['#5B8F7A', '#D6EDE7'],
  DOCX: ['#3A7FC1', '#D6E4ED']
}

const selectedFolderName = computed(() => {
  return folders.find(f => f.id === selectedFolder.value)?.name || '全部文档'
})

const fileCount = computed(() => {
  return folders.find(f => f.id === selectedFolder.value)?.count || 0
})
</script>

<template>
  <div class="flex flex-col h-full">
    <div class="flex items-center gap-2 mb-3.5">
      <SearchBox v-model="searchQuery" placeholder="🔍 语义搜索知识库…" class="flex-1" />
      <Button variant="primary" icon="📤">上传文档</Button>
      <Button variant="secondary">新建文件夹</Button>
    </div>

    <div class="flex gap-2 mb-3">
      <Chip :active="viewMode === 'browser'" @click="viewMode = 'browser'">文件浏览器</Chip>
      <Chip :active="viewMode === 'search'" @click="viewMode = 'search'">搜索优先</Chip>
    </div>

    <template v-if="viewMode === 'browser'">
      <div class="flex gap-3.5 flex-1 min-h-0">
        <Card class="w-[216px] flex-shrink-0 flex flex-col">
          <RowTitle label="文件夹" />
          <div class="flex-1 overflow-y-auto">
            <div
              v-for="folder in folders"
              :key="folder.id"
              @click="selectedFolder = folder.id"
              class="flex items-center gap-2 px-2.5 py-1.5 rounded-md mb-0.5 cursor-pointer text-[12px]"
              :class="selectedFolder === folder.id
                ? 'bg-accent-light text-accent border border-accent'
                : 'text-text-body hover:bg-page-bg'"
            >
              <span>📁</span>
              <span class="flex-1">{{ folder.name }}</span>
              <span class="text-[10px] text-text-light">{{ folder.count }}</span>
            </div>
          </div>

          <div class="mt-3 pt-2.5 border-t border-border">
            <div class="text-[10px] text-text-light mb-1.5">标签筛选</div>
            <div class="flex flex-wrap gap-1">
              <Chip v-for="t in []" :key="t" style="font-size: 10px">{{ t }}</Chip>
            </div>
          </div>
        </Card>

        <div class="flex-1 flex flex-col min-w-0">
          <div class="flex items-center gap-2 mb-3">
            <span class="text-[13px] font-bold text-text-heading">{{ selectedFolderName }}</span>
            <span class="text-[11px] text-text-light">{{ fileCount }} 个文件</span>
            <div class="ml-auto flex gap-1.5">
              <Chip style="font-size: 11px">≡ 列表</Chip>
              <Chip accent style="font-size: 11px">⊞ 网格</Chip>
            </div>
          </div>

          <div class="grid grid-cols-3 gap-2.5 flex-1 content-start">
            <Card
              v-for="(file, i) in files"
              :key="i"
              :hoverable="true"
              class="flex flex-col gap-2"
            >
              <div
                class="h-[58px] rounded-md flex items-center justify-center text-[13px] font-bold"
                :style="{
                  backgroundColor: typeColors[file.type]?.[1] || '#eee',
                  color: typeColors[file.type]?.[0] || '#999'
                }"
              >
                {{ file.type }}
              </div>
              <div class="text-[12px] font-semibold text-text-heading leading-tight">{{ file.name }}</div>
              <div class="flex justify-between text-[10px] text-text-light">
                <span>{{ file.size }}</span>
                <span>{{ file.date }}</span>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="max-w-[680px] mx-auto mb-5 text-center">
        <h2 class="text-[18px] font-bold text-text-heading mb-1">在知识库中搜索</h2>
        <p class="text-[12px] text-text-light mb-3.5">语义搜索 · 关键词检索 · 共 0 个文档</p>

        <div class="flex items-center gap-2.5 bg-card-bg border-2 border-accent rounded-xl px-4 py-2.5 text-left">
          <span class="text-[16px]">🔍</span>
          <input
            v-model="searchText"
            type="text"
            placeholder=""
            class="flex-1 text-[13px] text-text-body bg-transparent outline-none"
          />
          <Chip style="font-size: 10px">语义</Chip>
          <Chip style="font-size: 10px">关键词</Chip>
          <Button size="small" variant="primary">搜索</Button>
        </div>
      </div>

      <div class="flex gap-3.5 flex-1 min-h-0">
        <Card class="w-[196px] flex-shrink-0">
          <RowTitle label="筛选" />
          <div class="text-[10px] text-text-light mb-1">文件类型</div>
          <div class="text-[11px] text-text-body space-y-1 mb-3">
            <div v-for="t in []" :key="t" class="flex items-center gap-1.5 py-1">
              <div class="w-3 h-3 rounded border bg-chip border-border" />
              {{ t }}
            </div>
          </div>

          <div class="text-[10px] text-text-light mb-1 mt-3">时间范围</div>
          <div class="text-[11px] text-text-body space-y-1">
            <div v-for="t in []" :key="t" class="flex items-center gap-1.5 py-1">
              <div class="w-3 h-3 rounded-full bg-chip border-border" />
              {{ t }}
            </div>
          </div>
        </Card>

        <div class="flex-1 flex flex-col gap-2.5">
          <div class="text-[11px] text-text-light">找到 0 个结果</div>

          <Card
            v-for="(r, i) in searchResults"
            :key="i"
            :hoverable="true"
            class="flex gap-3 items-start"
          >
            <div
              class="w-[38px] h-[38px] rounded-lg flex items-center justify-center text-[10px] font-bold flex-shrink-0"
              :style="{
                backgroundColor: typeColors[r.type]?.[1] || '#eee',
                color: typeColors[r.type]?.[0] || '#999'
              }"
            >
              {{ r.type }}
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1">
                <span class="text-[13px] font-bold text-text-heading">{{ r.name }}</span>
                <span class="text-[10px] px-1.5 py-0.5 rounded-full bg-accent-light text-accent flex-shrink-0">
                  相关度 {{ r.match }}
                </span>
              </div>
              <p class="text-[11px] text-text-light leading-relaxed">{{ r.excerpt }}</p>
            </div>
            <div class="flex gap-1 flex-shrink-0">
              <Button size="small" variant="secondary">查看</Button>
              <Button size="small" variant="primary">引用</Button>
            </div>
          </Card>
        </div>
      </div>
    </template>
  </div>
</template>
