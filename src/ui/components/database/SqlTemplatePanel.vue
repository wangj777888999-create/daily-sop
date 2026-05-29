<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Card from '@/ui/components/common/Card.vue'
import Button from '@/ui/components/common/Button.vue'
import RowTitle from '@/ui/components/common/RowTitle.vue'
import Input from '@/ui/components/common/Input.vue'
import {
  type SqlTemplate, type VariableValues,
  loadTemplates, saveTemplates, buildFinalSql,
} from '@/types/sqlTemplate'
import { databaseApi, type QueryResult, type ConnStatus } from '@/services/databaseApi'
import QueryResultTable from '@/ui/components/database/QueryResultTable.vue'

const props = defineProps<{ connStatus: ConnStatus | null }>()

const templates = ref<SqlTemplate[]>([])
const active = ref<SqlTemplate | null>(null)
const varValues = ref<VariableValues>({})
const queryResult = ref<QueryResult | null>(null)
const queryError = ref('')
const queryLoading = ref(false)

onMounted(() => { templates.value = loadTemplates() })

function selectTemplate(t: SqlTemplate) {
  active.value = t
  varValues.value = Object.fromEntries(t.variables.map(v => [v.name, v.defaultValue]))
  queryResult.value = null
  queryError.value = ''
}

function deleteTemplate(id: string) {
  templates.value = templates.value.filter(t => t.id !== id)
  saveTemplates(templates.value)
  if (active.value?.id === id) active.value = null
}

const highlightedSql = computed(() => {
  if (!active.value) return ''
  return active.value.sql
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(
      /\{\{([^}]+)\}\}/g,
      '<mark style="background:rgba(193,127,58,0.18);color:#A0522D;border-radius:3px;padding:0 2px">{{$1}}</mark>',
    )
})

async function runTemplate() {
  if (!active.value || !props.connStatus) return
  queryLoading.value = true
  queryError.value = ''
  queryResult.value = null
  try {
    const sql = buildFinalSql(active.value.sql, varValues.value)
    queryResult.value = await databaseApi.query(sql)
  } catch (e: unknown) {
    queryError.value = e instanceof Error ? e.message : '执行失败'
  } finally {
    queryLoading.value = false
  }
}
</script>

<template>
  <div class="flex gap-3.5 flex-1 min-h-0">

    <!-- sidebar: template list -->
    <Card class="w-[280px] flex-shrink-0 flex flex-col max-h-[600px]">
      <RowTitle label="SQL 模板" />

      <div class="flex-1 overflow-y-auto">
        <div v-if="templates.length === 0" class="text-center py-8">
          <div class="text-[24px] mb-2">📋</div>
          <div class="text-[11px] text-text-light">暂无模板</div>
          <div class="text-[10px] text-placeholder mt-1">在 SQL 编辑器中点击<br>「保存为模板」创建</div>
        </div>

        <div
          v-for="t in templates"
          :key="t.id"
          @click="selectTemplate(t)"
          class="group flex items-start gap-1.5 px-2 py-2 rounded-md cursor-pointer select-none transition-colors"
          :class="active?.id === t.id ? 'bg-chip' : 'hover:bg-page-bg'"
        >
          <span class="text-[13px] mt-px shrink-0">📋</span>
          <div class="flex-1 min-w-0">
            <div class="text-[12px] text-text-body font-medium truncate">{{ t.name }}</div>
            <div class="text-[10px] text-text-light mt-0.5">
              {{ t.variables.length > 0 ? `${t.variables.length} 个变量` : '无变量' }}
            </div>
          </div>
          <button
            class="opacity-0 group-hover:opacity-100 text-[11px] text-text-light hover:text-[#A0522D] px-0.5 mt-0.5 shrink-0 transition-opacity"
            @click.stop="deleteTemplate(t.id)"
            title="删除模板"
          >✕</button>
        </div>
      </div>
    </Card>

    <!-- main panel -->
    <div class="flex-1 flex flex-col gap-3 min-w-0">

      <!-- empty state -->
      <div v-if="!active" class="flex-1 flex items-center justify-center">
        <div class="text-center">
          <div class="text-[32px] mb-3">←</div>
          <div class="text-[13px] text-text-light">点击左侧模板开始运行</div>
        </div>
      </div>

      <template v-else>
        <!-- SQL preview -->
        <Card>
          <div class="flex items-center gap-2 mb-2.5">
            <span class="text-[14px] font-bold text-text-heading">{{ active.name }}</span>
            <span class="text-[10px] text-text-light ml-1">
              {{ active.variables.length > 0 ? `${active.variables.length} 个参数` : '无参数' }}
            </span>
          </div>
          <pre
            class="bg-[#F2EDE4] border border-border rounded-lg px-3 py-2.5 font-mono text-[12px] leading-relaxed text-text-body whitespace-pre-wrap break-all max-h-[150px] overflow-y-auto"
            v-html="highlightedSql"
          />
        </Card>

        <!-- variable inputs -->
        <Card v-if="active.variables.length > 0">
          <RowTitle label="填写参数" />
          <div class="space-y-2.5">
            <div
              v-for="v in active.variables"
              :key="v.name"
              class="flex items-center gap-3"
            >
              <div class="w-[100px] shrink-0">
                <span class="text-[12px] font-semibold text-text-body">{{ v.name }}</span>
                <span class="text-[9px] text-text-light ml-1.5 uppercase">{{ v.type }}</span>
              </div>
              <div class="flex-1">
                <Input
                  v-model="varValues[v.name]"
                  :type="v.type === 'date' ? 'date' : v.type === 'month' ? 'month' : v.type === 'number' ? 'number' : 'text'"
                  :placeholder="`${v.name}…`"
                />
              </div>
            </div>
          </div>

          <div class="flex items-center justify-between mt-3 pt-3 border-t border-border/50">
            <span v-if="!connStatus" class="text-[11px] text-text-light">请先连接数据库</span>
            <span v-else class="text-[11px] text-text-light">⌘↩ 执行</span>
            <Button
              variant="primary"
              size="small"
              :disabled="!connStatus || queryLoading"
              @click="runTemplate"
            >{{ queryLoading ? '执行中…' : '▶ 执行' }}</Button>
          </div>
        </Card>

        <!-- no-variable template: just run button -->
        <div v-else class="flex justify-end">
          <Button
            variant="primary"
            size="small"
            :disabled="!connStatus || queryLoading"
            @click="runTemplate"
          >{{ queryLoading ? '执行中…' : '▶ 直接执行' }}</Button>
        </div>

        <!-- results -->
        <Card>
          <div class="flex items-center gap-2 mb-2.5">
            <span class="text-[14px] font-bold text-text-heading">查询结果</span>
          </div>

          <div v-if="queryError" class="px-3 py-2 rounded-lg bg-[#FEF0E7] border border-[#E8C5A0] text-[11px] text-[#A0522D] mb-2">
            {{ queryError }}
          </div>
          <div v-else-if="queryLoading" class="h-24 flex items-center justify-center text-[12px] text-text-light">
            执行中…
          </div>
          <div v-else-if="queryResult && queryResult.columns.length === 0" class="text-[12px] text-accent font-semibold px-1">
            ✓ 执行成功，影响 {{ queryResult.affected ?? 0 }} 行
          </div>
          <QueryResultTable v-else-if="queryResult && queryResult.columns.length > 0" :result="queryResult" />
          <div v-else class="h-24 flex items-center justify-center text-[12px] text-text-light">
            填写参数后执行查看结果
          </div>
        </Card>
      </template>
    </div>
  </div>
</template>
