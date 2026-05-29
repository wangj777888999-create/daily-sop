<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Card from '@/ui/components/common/Card.vue'
import Button from '@/ui/components/common/Button.vue'
import Chip from '@/ui/components/common/Chip.vue'
import RowTitle from '@/ui/components/common/RowTitle.vue'
import SearchBox from '@/ui/components/common/SearchBox.vue'
import ConnectModal from '@/ui/components/database/ConnectModal.vue'
import SqlTemplatePanel from '@/ui/components/database/SqlTemplatePanel.vue'
import SaveTemplateModal from '@/ui/components/database/SaveTemplateModal.vue'
import QueryResultTable from '@/ui/components/database/QueryResultTable.vue'
import { databaseApi, type ConnStatus, type TableColumn, type QueryResult } from '@/services/databaseApi'

// ── connection state ──
const showModal = ref(false)
const connStatus = ref<ConnStatus | null>(null)

// ── database browser (SSH multi-db) ──
const databases = ref<string[]>([])
const currentDatabase = ref<string | null>(null)
const dbSwitching = ref(false)

// ── table browser ──
const tables = ref<string[]>([])
const columnMap = ref<Record<string, TableColumn[]>>({})
const expandedTable = ref('')
const searchQuery = ref('')

// ── SQL editor ──
const viewMode = ref<'editor' | 'template'>('editor')
const sqlText = ref('SELECT * FROM ')
const queryResult = ref<QueryResult | null>(null)
const queryError = ref('')
const queryLoading = ref(false)
const showSaveTemplateModal = ref(false)
const templatePanelKey = ref(0)

// SSH multi-db mode: connected to server but no specific DB selected
const isMultiDbMode = computed(
  () => connStatus.value?.connection_type === 'ssh' && !currentDatabase.value
)

const dbSwitchError = ref('')

// ── on mount: restore any existing connection ──
onMounted(async () => {
  try {
    const s = await databaseApi.getStatus()
    if (s.db_type) {
      connStatus.value = s
      currentDatabase.value = (s as any).current_database ?? null
      if (currentDatabase.value) {
        await loadTables()
      } else if (s.connection_type === 'ssh') {
        await loadDatabases()
      } else {
        await loadTables()
      }
    }
  } catch {
    // ignore
  }
})

async function loadDatabases() {
  try {
    databases.value = await databaseApi.listDatabases()
  } catch {
    databases.value = []
  }
}

async function loadTables() {
  try {
    tables.value = await databaseApi.getTables()
    columnMap.value = {}
  } catch {
    tables.value = []
  }
}

async function selectDatabase(db: string) {
  dbSwitching.value = true
  dbSwitchError.value = ''
  try {
    const result = await databaseApi.switchDatabase(db)
    connStatus.value = result
    currentDatabase.value = db
    await loadTables()
  } catch (e: unknown) {
    dbSwitchError.value = e instanceof Error ? e.message : '切换数据库失败'
  } finally {
    dbSwitching.value = false
  }
}

async function handleConnected(info: ConnStatus) {
  connStatus.value = info
  currentDatabase.value = (info as any).current_database ?? null
  showModal.value = false
  tables.value = []
  columnMap.value = {}
  databases.value = []
  if (currentDatabase.value) {
    await loadTables()
  } else if (info.connection_type === 'ssh') {
    await loadDatabases()
  } else {
    await loadTables()
  }
}

async function handleDisconnect() {
  await databaseApi.disconnect()
  connStatus.value = null
  currentDatabase.value = null
  databases.value = []
  tables.value = []
  columnMap.value = {}
  expandedTable.value = ''
  queryResult.value = null
  queryError.value = ''
}

async function toggleTable(tbl: string) {
  if (expandedTable.value === tbl) {
    expandedTable.value = ''
    return
  }
  expandedTable.value = tbl
  if (!columnMap.value[tbl]) {
    try {
      columnMap.value[tbl] = await databaseApi.getColumns(tbl)
    } catch {
      columnMap.value[tbl] = []
    }
  }
}

function insertTableName(tbl: string) {
  sqlText.value = `SELECT * FROM \`${tbl}\` LIMIT 100`
}

const filteredTables = () =>
  searchQuery.value
    ? tables.value.filter(t => t.toLowerCase().includes(searchQuery.value.toLowerCase()))
    : tables.value

async function runQuery() {
  if (!sqlText.value.trim()) return
  queryError.value = ''
  queryResult.value = null
  queryLoading.value = true
  try {
    queryResult.value = await databaseApi.query(sqlText.value)
  } catch (e: unknown) {
    queryError.value = e instanceof Error ? e.message : '执行失败'
  } finally {
    queryLoading.value = false
  }
}

function handleKeydown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
    e.preventDefault()
    runQuery()
  }
}

function dbTypeIcon(t: string) {
  return t === 'sqlite' ? '🗂' : t === 'mysql' ? '🐬' : '🐘'
}
</script>

<template>
  <div class="flex flex-col">
    <!-- toolbar -->
    <div class="flex items-center gap-2 mb-3.5">
      <template v-if="!connStatus">
        <Button variant="secondary" icon="📂" @click="showModal = true">连接数据库</Button>
      </template>
      <template v-else>
        <div class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-accent-light border border-accent/30 text-[12px]">
          <span>{{ dbTypeIcon(connStatus.db_type || '') }}</span>
          <span class="text-text-heading font-semibold">{{ connStatus.display_name }}</span>
          <span class="text-text-light text-[10px] uppercase">{{ connStatus.connection_type }}</span>
        </div>
        <Button variant="secondary" size="small" @click="showModal = true">切换连接</Button>
        <Button variant="secondary" size="small" @click="handleDisconnect">断开</Button>
      </template>

      <div class="ml-auto flex gap-1.5">
        <Button variant="secondary" size="small" @click="currentDatabase ? loadTables() : (connStatus?.connection_type === 'ssh' ? loadDatabases() : loadTables())">🔄 刷新</Button>
      </div>
    </div>

    <!-- view tabs -->
    <div class="flex gap-2 mb-3">
      <Chip :active="viewMode === 'editor'" @click="viewMode = 'editor'">SQL 编辑器</Chip>
      <Chip :active="viewMode === 'template'" @click="viewMode = 'template'">SQL 模板</Chip>
    </div>

    <!-- no connection hint -->
    <template v-if="!connStatus">
      <div class="flex-1 flex items-center justify-center">
        <div class="text-center">
          <div class="text-[32px] mb-3">🔌</div>
          <div class="text-[14px] font-semibold text-text-heading mb-1">尚未连接数据库</div>
          <div class="text-[12px] text-text-light mb-4">支持本地 SQLite / MySQL / PostgreSQL，以及 SSH 远程连接</div>
          <Button variant="primary" icon="📂" @click="showModal = true">连接数据库</Button>
        </div>
      </div>
    </template>

    <!-- SQL editor view -->
    <template v-else-if="viewMode === 'editor'">
      <div class="flex gap-3.5 flex-1 min-h-0">
        <!-- sidebar -->
        <Card class="w-[280px] flex-shrink-0 flex flex-col max-h-[600px]">
          <!-- multi-db mode: show database list -->
          <template v-if="isMultiDbMode">
            <RowTitle label="选择数据库" />
            <div class="flex-1 overflow-y-auto">
              <div v-if="dbSwitchError" class="text-[11px] text-[#A0522D] px-2 py-2 mb-1 bg-[#FEF0E7] rounded-md">
                {{ dbSwitchError }}
              </div>
              <div v-if="databases.length === 0" class="text-[11px] text-text-light text-center py-4">
                加载中…
              </div>
              <div
                v-for="db in databases"
                :key="db"
                @click="selectDatabase(db)"
                class="flex items-center gap-2 px-2 py-1.5 text-[12px] cursor-pointer rounded-md select-none"
                :class="dbSwitching ? 'opacity-50 pointer-events-none' : 'hover:bg-page-bg'"
              >
                <span class="text-[13px]">🗄</span>
                <span class="flex-1 text-text-body truncate">{{ db }}</span>
                <span class="text-[9px] text-text-light">→</span>
              </div>
            </div>
          </template>

          <!-- normal mode: show table list -->
          <template v-else>
            <div class="flex items-center gap-1">
              <h3 class="flex-1 text-[14px] font-bold text-text-heading mb-2.5 truncate">
                {{ currentDatabase || '数据库结构' }}
              </h3>
              <button
                v-if="currentDatabase && connStatus?.connection_type === 'ssh'"
                @click="currentDatabase = null; loadDatabases()"
                class="text-[10px] text-text-light hover:text-accent px-1 mb-2.5 shrink-0"
                title="返回数据库列表"
              >← 返回</button>
            </div>
            <SearchBox v-model="searchQuery" placeholder="🔍 搜索表" class="mb-2" />

            <div class="flex-1 overflow-y-auto">
              <div v-if="tables.length === 0" class="flex flex-col items-center gap-2 py-6 px-3">
                <span class="text-[11px] text-text-light">暂无数据表</span>
                <button
                  @click="loadTables"
                  class="text-[11px] px-3 py-1.5 rounded-lg border border-border bg-chip hover:bg-accent-light hover:border-accent hover:text-accent transition-colors"
                >🔄 重新加载</button>
              </div>
              <div v-for="tbl in filteredTables()" :key="tbl">
                <div
                  @click="toggleTable(tbl)"
                  @dblclick="insertTableName(tbl)"
                  class="flex items-center gap-1.5 px-1.5 py-1.5 text-[12px] cursor-pointer rounded-md select-none"
                  :class="expandedTable === tbl ? 'bg-chip' : 'hover:bg-page-bg'"
                  title="单击展开列，双击插入查询"
                >
                  <span class="text-[10px] text-text-light w-3">{{ expandedTable === tbl ? '▼' : '▶' }}</span>
                  <span class="text-[12px]">⬡</span>
                  <span class="flex-1 text-text-body break-all">{{ tbl }}</span>
                </div>

                <template v-if="expandedTable === tbl">
                  <div
                    v-for="col in columnMap[tbl] || []"
                    :key="col.name"
                    class="flex items-center gap-1.5 px-1.5 py-1 pl-[22px] text-[10px] text-text-light"
                  >
                    <span class="text-[9px]" :class="col.pk ? 'text-amber' : ''">{{ col.pk ? '🔑' : '—' }}</span>
                    <span class="flex-1 truncate" :class="col.pk ? 'font-semibold text-text-body' : ''">{{ col.name }}</span>
                    <span class="text-[9px] text-placeholder shrink-0">{{ col.type }}</span>
                  </div>
                  <div v-if="!columnMap[tbl]" class="pl-6 text-[10px] text-text-light py-1">加载中…</div>
                </template>
              </div>
            </div>
          </template>
        </Card>

        <!-- main panel -->
        <div class="flex-1 flex flex-col gap-3 min-w-0 min-h-0">
          <!-- SQL editor card -->
          <Card>
            <div class="flex items-center gap-2 mb-2.5">
              <span class="text-[14px] font-bold text-text-heading">SQL 编辑器</span>
              <span class="text-[10px] text-text-light">⌘↩ 执行</span>
              <div class="ml-auto flex gap-1.5">
                <Button size="small" variant="secondary" @click="showSaveTemplateModal = true">📋 保存为模板</Button>
                <Button size="small" variant="primary" :disabled="queryLoading" @click="runQuery">
                  {{ queryLoading ? '执行中…' : '▶ 执行' }}
                </Button>
              </div>
            </div>

            <textarea
              v-model="sqlText"
              @keydown="handleKeydown"
              rows="5"
              spellcheck="false"
              class="w-full bg-[#F2EDE4] border border-border rounded-lg px-3 py-2.5 font-mono text-[12px] leading-relaxed text-text-body outline-none resize-none transition-all duration-150 focus:border-accent focus:shadow-input-focus"
              placeholder="-- 输入 SQL 查询，⌘↩ 执行"
            />
          </Card>

          <!-- results card -->
          <Card>
            <div class="flex items-center gap-2 mb-2.5 shrink-0">
              <span class="text-[14px] font-bold text-text-heading">查询结果</span>
              <span v-if="queryResult?.affected !== undefined" class="text-[11px] text-text-light">
                影响 {{ queryResult.affected }} 行
              </span>
            </div>

            <div v-if="queryError" class="px-3 py-2 rounded-lg bg-[#FEF0E7] border border-[#E8C5A0] text-[11px] text-[#A0522D] mb-2 shrink-0">
              {{ queryError }}
            </div>
            <div v-else-if="queryLoading" class="flex-1 flex items-center justify-center text-[12px] text-text-light">
              执行中…
            </div>
            <div v-else-if="queryResult && queryResult.columns.length === 0" class="text-[12px] text-accent font-semibold px-1">
              ✓ 执行成功，影响 {{ queryResult.affected ?? 0 }} 行
            </div>
            <QueryResultTable v-else-if="queryResult && queryResult.columns.length > 0" :result="queryResult" />
            <div v-else class="flex-1 flex items-center justify-center text-[12px] text-text-light">
              执行 SQL 后查看结果
            </div>
          </Card>
        </div>
      </div>
    </template>

    <!-- SQL template view -->
    <template v-else-if="viewMode === 'template'">
      <SqlTemplatePanel :key="templatePanelKey" :conn-status="connStatus" />
    </template>

    <!-- connect modal -->
    <ConnectModal
      v-if="showModal"
      @connected="handleConnected"
      @close="showModal = false"
    />

    <!-- save template modal -->
    <SaveTemplateModal
      v-if="showSaveTemplateModal"
      :sql="sqlText"
      @saved="showSaveTemplateModal = false; templatePanelKey++; viewMode = 'template'"
      @close="showSaveTemplateModal = false"
    />
  </div>
</template>
