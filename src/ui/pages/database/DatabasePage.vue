<script setup lang="ts">
import { ref } from 'vue'
import Card from '@/ui/components/common/Card.vue'
import Button from '@/ui/components/common/Button.vue'
import Chip from '@/ui/components/common/Chip.vue'
import RowTitle from '@/ui/components/common/RowTitle.vue'
import DataTable from '@/ui/components/common/DataTable.vue'
import SearchBox from '@/ui/components/common/SearchBox.vue'

const viewMode = ref<'editor' | 'visual'>('editor')
const expandedTable = ref('')
const searchQuery = ref('')

const tables: string[] = []
const columns: string[] = []

const tableColumns: Array<{
  key: string
  label: string
  type: string
}> = []
</script>

<template>
  <div class="flex flex-col h-full">
    <div class="flex items-center gap-2 mb-3.5">
      <Button variant="secondary" icon="📂">连接数据库</Button>
      <div class="ml-auto flex gap-1.5">
        <Button variant="secondary" size="small">🔄 刷新</Button>
        <Button variant="primary" size="small" icon="📤">导出</Button>
      </div>
    </div>

    <div class="flex gap-2 mb-3">
      <Chip :active="viewMode === 'editor'" @click="viewMode = 'editor'">SQL 编辑器</Chip>
      <Chip :active="viewMode === 'visual'" @click="viewMode = 'visual'">可视化查询构建器</Chip>
    </div>

    <template v-if="viewMode === 'editor'">
      <div class="flex gap-3.5 flex-1 min-h-0">
        <Card class="w-[220px] flex-shrink-0 flex flex-col">
          <RowTitle label="数据库结构" />
          <SearchBox v-model="searchQuery" placeholder="🔍 搜索表/字段" class="mb-2" />

          <div class="flex-1 overflow-y-auto">
            <div v-for="tbl in tables" :key="tbl">
              <div
                @click="expandedTable = expandedTable === tbl ? '' : tbl"
                class="flex items-center gap-1.5 px-1.5 py-1.5 text-[12px] cursor-pointer rounded-md"
                :class="expandedTable === tbl ? 'bg-chip' : 'hover:bg-page-bg'"
              >
                <span class="text-[10px]">{{ expandedTable === tbl ? '▼' : '▶' }}</span>
                <span>⬡</span>
                <span class="text-text-body">{{ tbl }}</span>
              </div>

              <template v-if="expandedTable === tbl && tableColumns.length > 0">
                <div
                  v-for="col in tableColumns"
                  :key="col.key"
                  class="flex items-center gap-1.5 px-1.5 py-1 pl-[22px] text-[10px] text-text-light"
                >
                  <span>—</span>
                  <span class="flex-1">{{ col.key }}</span>
                  <span class="text-[9px] text-placeholder">{{ col.type }}</span>
                </div>
              </template>
            </div>
          </div>
        </Card>

        <div class="flex-1 flex flex-col gap-3 min-w-0">
          <Card>
            <div class="flex items-center gap-2 mb-2.5">
              <span class="text-[14px] font-bold text-text-heading">SQL 编辑器</span>
              <div class="ml-auto flex gap-1.5">
                <Button size="small" variant="secondary">格式化</Button>
                <Button size="small" variant="primary">▶ 执行</Button>
              </div>
            </div>

            <div class="bg-[#F2EDE4] border border-border rounded-lg p-3 font-mono text-[12px] leading-relaxed min-h-[100px]">
              <span class="text-text-light">-- 输入 SQL 查询...</span>
            </div>

            <div class="flex gap-1.5 mt-2">
              <Chip v-for="t in ['历史查询', '保存查询']" :key="t" style="font-size: 10px">{{ t }}</Chip>
              <Chip style="font-size: 10px" accent>AI 优化 SQL</Chip>
            </div>
          </Card>

          <Card class="flex-1 flex flex-col min-h-0">
            <div class="flex items-center gap-2 mb-3">
              <span class="text-[14px] font-bold text-text-heading">查询结果</span>
            </div>
            <DataTable :columns="columns" :row-count="0" />
          </Card>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="flex gap-3.5 flex-1 min-h-0">
        <Card class="w-[190px] flex-shrink-0">
          <RowTitle label="数据表" />
          <div
            v-for="tbl in tables"
            :key="tbl"
            class="flex items-center gap-2 px-2 py-1.5 rounded-md mb-1 bg-page-bg border border-border text-[12px] text-text-body cursor-grab"
          >
            <span class="text-[10px]">⬡</span>
            <span class="flex-1">{{ tbl }}</span>
            <span class="text-[9px] text-text-light">拖拽</span>
          </div>
        </Card>

        <div class="flex-1 flex flex-col gap-3 min-w-0">
          <Card class="flex-1 flex flex-col">
            <RowTitle label="可视化查询画布" />
            <div class="flex-1 bg-page-bg border border-dashed border-border rounded-lg flex items-center justify-center min-h-[180px]">
              <span class="text-[11px] text-text-light">拖拽数据表到画布以建立关联</span>
            </div>
          </Card>

          <div class="flex gap-3">
            <Card class="flex-1">
              <RowTitle label="筛选条件" />
            </Card>

            <Card class="w-[200px]">
              <RowTitle label="输出字段" />
            </Card>
          </div>

          <div class="flex justify-end gap-2">
            <Button variant="secondary">预览 SQL</Button>
            <Button variant="primary">▶ 运行查询</Button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
