<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Card from '@/ui/components/common/Card.vue'
import Button from '@/ui/components/common/Button.vue'
import Chip from '@/ui/components/common/Chip.vue'
import MetricCard from '@/ui/components/common/MetricCard.vue'
import RowTitle from '@/ui/components/common/RowTitle.vue'
import WBox from '@/ui/components/common/WBox.vue'
import { useKnowledgeStore } from '@/stores/knowledge'

const kbStore = useKnowledgeStore()
const viewMode = ref<'charts' | 'chat'>('charts')
const showKBPicker = ref(false)
const selectedKBDocIds = ref<string[]>([])

onMounted(async () => {
  await kbStore.loadDocuments()
})

const selectedKBDocs = computed(() =>
  kbStore.documents.filter(d => selectedKBDocIds.value.includes(d.id))
)

const kbButtonLabel = computed(() =>
  selectedKBDocIds.value.length > 0
    ? `知识库 (${selectedKBDocIds.value.length})`
    : '知识库'
)

function toggleDoc(docId: string) {
  const idx = selectedKBDocIds.value.indexOf(docId)
  if (idx >= 0) selectedKBDocIds.value.splice(idx, 1)
  else selectedKBDocIds.value.push(docId)
}

const metrics: Array<{
  label: string
  value: string
  delta?: number
}> = []

const charts: Array<{
  title: string
  subtitle: string
}> = []

const chatMessages: Array<{
  role: string
  content: string
}> = []

const quickLabels: string[] = []
</script>

<template>
  <div class="flex flex-col h-full">
    <div class="flex items-center gap-2 mb-3.5">
      <Button variant="secondary" icon="📂">加载数据集</Button>
      <div class="ml-auto flex gap-1.5">
        <Button variant="secondary" size="small">🔄 刷新</Button>
        <Button variant="primary" size="small" icon="📤">导出报告</Button>
      </div>
    </div>

    <div class="flex gap-2.5 mb-3.5">
      <MetricCard
        v-for="m in metrics"
        :key="m.label"
        :label="m.label"
        :value="m.value"
        :delta="m.delta"
      />
    </div>

    <div class="flex gap-2 mb-3">
      <Chip :active="viewMode === 'charts'" @click="viewMode = 'charts'">图表仪表盘</Chip>
      <Chip :active="viewMode === 'chat'" @click="viewMode = 'chat'">对话模式</Chip>
    </div>

    <template v-if="viewMode === 'charts'">
      <div class="grid grid-cols-2 gap-3.5 flex-1 min-h-0">
        <Card v-for="chart in charts" :key="chart.title" class="flex flex-col">
          <RowTitle :label="chart.title" action="配置图表 ⚙" />
          <WBox :label="chart.subtitle" class="flex-1 min-h-[120px]" />
        </Card>
      </div>
    </template>

    <template v-else>
      <div class="flex gap-3.5 flex-1 min-h-0">
        <div class="w-[300px] flex-shrink-0 flex flex-col gap-3">
          <Card>
            <RowTitle label="数据源" />
            <WBox label="拖拽上传\nExcel / CSV / JSON" class="w-full h-[76px] mb-2" />
            <div class="flex gap-1.5">
              <Button size="small" variant="secondary">数据库</Button>
              <Button size="small" variant="secondary" @click="showKBPicker = !showKBPicker">{{ kbButtonLabel }}</Button>
            </div>

            <!-- 知识库文档选择面板 -->
            <div v-if="showKBPicker" class="mt-2 border border-border rounded-lg bg-page-bg overflow-hidden">
              <div v-if="kbStore.documents.length === 0" class="p-3 text-[11px] text-text-light text-center">
                暂无文档，<router-link to="/knowledge" class="text-accent underline">前往知识库上传</router-link>
              </div>
              <template v-else>
                <div class="max-h-[180px] overflow-y-auto">
                  <label
                    v-for="doc in kbStore.documents"
                    :key="doc.id"
                    class="flex items-center gap-2 px-3 py-1.5 text-[11px] text-text-body hover:bg-accent-light cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      :checked="selectedKBDocIds.includes(doc.id)"
                      @change="toggleDoc(doc.id)"
                      class="accent-[var(--color-accent)]"
                    />
                    <span class="truncate">{{ doc.name }}</span>
                  </label>
                </div>
                <div
                  v-if="selectedKBDocIds.length > 0"
                  class="px-3 py-1.5 border-t border-border text-[10px] text-accent text-right"
                >
                  确认 {{ selectedKBDocIds.length }} 个
                </div>
              </template>
            </div>

            <!-- 已选知识库文档展示 -->
            <div v-if="selectedKBDocs.length > 0" class="mt-2 space-y-1">
              <div
                v-for="doc in selectedKBDocs"
                :key="doc.id"
                class="flex items-center justify-between bg-accent-light rounded px-2 py-1 text-[10px]"
              >
                <span class="truncate text-text-body">{{ doc.name }}</span>
                <span class="cursor-pointer text-text-light ml-1 flex-shrink-0" @click="toggleDoc(doc.id)">✕</span>
              </div>
            </div>
          </Card>

          <Card class="flex-1">
            <RowTitle label="数据概览" />
          </Card>
        </div>

        <Card class="flex-1 flex flex-col min-h-0">
          <RowTitle label="分析结果" />
          <div class="flex-1 overflow-y-auto space-y-2.5">
            <template v-for="(msg, i) in chatMessages" :key="i">
              <div
                v-if="msg.role === 'user'"
                class="bg-page-bg border border-border rounded-lg px-2.5 py-2 text-[11px] text-text-light"
              >
                {{ msg.content }}
              </div>
              <div
                v-else
                class="bg-accent-light border border-accent rounded-lg px-[11px] py-2 text-[11px] text-text-body"
              >
                {{ msg.content }}
              </div>
            </template>
          </div>

          <div class="mt-3">
            <div class="flex gap-2 mb-1.5">
              <div class="flex-1 bg-page-bg border border-border rounded-lg px-3 py-2 text-[12px] text-text-light">
                用自然语言提问，例如："找出增长最快的产品线"
              </div>
              <Button variant="primary">分析</Button>
            </div>
            <div class="flex gap-1 flex-wrap">
              <Chip v-for="l in quickLabels" :key="l" style="font-size: 10px">{{ l }}</Chip>
            </div>
          </div>
        </Card>
      </div>
    </template>
  </div>
</template>
