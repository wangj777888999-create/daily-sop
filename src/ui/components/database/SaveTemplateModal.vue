<script setup lang="ts">
import { ref, watch } from 'vue'
import Button from '@/ui/components/common/Button.vue'
import Input from '@/ui/components/common/Input.vue'
import Chip from '@/ui/components/common/Chip.vue'
import {
  type SqlTemplate, type TemplateVariable, type VariableType,
  parseVariables, loadTemplates, saveTemplates,
} from '@/types/sqlTemplate'

const props = defineProps<{ sql: string }>()
const emit = defineEmits<{ saved: [t: SqlTemplate]; close: [] }>()

const templateName = ref('')
const variables = ref<TemplateVariable[]>([])

function syncVariables(sql: string) {
  const names = parseVariables(sql)
  // Keep existing type/defaultValue for already-known variables
  const existing = Object.fromEntries(variables.value.map(v => [v.name, v]))
  variables.value = names.map(name => existing[name] ?? { name, type: 'text' as VariableType, defaultValue: '' })
}

watch(() => props.sql, syncVariables, { immediate: true })

function setType(v: TemplateVariable, t: VariableType) {
  v.type = t
  if (t === 'date' && !v.defaultValue) {
    v.defaultValue = new Date().toISOString().slice(0, 10)
  } else if (t === 'month' && !v.defaultValue) {
    v.defaultValue = new Date().toISOString().slice(0, 7)
  }
}

function varTag(name: string) { return `{{${name}}}` }

function save() {
  const tmpl: SqlTemplate = {
    id: Date.now().toString(),
    name: templateName.value.trim(),
    sql: props.sql,
    variables: variables.value.map(v => ({ ...v })),
    createdAt: Date.now(),
  }
  const all = loadTemplates()
  all.unshift(tmpl)
  saveTemplates(all)
  emit('saved', tmpl)
}
</script>

<template>
  <div
    class="fixed inset-0 z-50 flex items-center justify-center"
    style="background: rgba(61,53,48,0.35); backdrop-filter: blur(2px)"
    @click.self="emit('close')"
  >
    <div
      class="w-[480px] max-h-[85vh] flex flex-col rounded-xl border border-border overflow-hidden"
      style="background: #FEFCF8; box-shadow: 0 20px 60px rgba(61,53,48,0.18), 0 4px 12px rgba(61,53,48,0.1)"
    >
      <!-- header -->
      <div class="flex items-center gap-2 px-5 py-4 border-b border-border">
        <span class="text-[15px] font-bold text-text-heading">保存为 SQL 模板</span>
        <button
          class="ml-auto text-text-light hover:text-text-body w-6 h-6 flex items-center justify-center rounded hover:bg-chip"
          @click="emit('close')"
        >✕</button>
      </div>

      <div class="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        <!-- name -->
        <div>
          <div class="text-[11px] font-semibold text-text-body mb-1">
            模板名称<span class="text-[#C17F3A] ml-0.5">*</span>
          </div>
          <Input v-model="templateName" placeholder="例：查询某日签到数据" />
        </div>

        <!-- sql preview -->
        <div>
          <div class="text-[11px] font-semibold text-text-body mb-1">SQL 预览</div>
          <pre class="bg-[#F2EDE4] border border-border rounded-lg px-3 py-2.5 font-mono text-[11px] text-text-body leading-relaxed whitespace-pre-wrap break-all max-h-[120px] overflow-y-auto">{{ sql }}</pre>
        </div>

        <!-- variables -->
        <div v-if="variables.length > 0">
          <div class="text-[11px] font-semibold text-text-body mb-2">
            检测到 {{ variables.length }} 个变量
          </div>
          <div class="space-y-2.5">
            <div
              v-for="v in variables"
              :key="v.name"
              class="flex items-center gap-2 bg-page-bg border border-border rounded-lg px-3 py-2"
            >
              <!-- var name -->
              <span class="text-[12px] font-semibold text-text-heading font-mono shrink-0">
                {{ varTag(v.name) }}
              </span>

              <!-- type chips -->
              <div class="flex gap-1 ml-auto">
                <Chip
                  v-for="t in ['text', 'month', 'date', 'number'] as VariableType[]"
                  :key="t"
                  :active="v.type === t"
                  @click="setType(v, t)"
                  style="font-size: 10px; padding: 2px 7px"
                >{{ t === 'text' ? '文本' : t === 'month' ? '年月' : t === 'date' ? '日期' : '数字' }}</Chip>
              </div>

              <!-- default value -->
              <div class="w-[130px] shrink-0">
                <Input
                  v-model="v.defaultValue"
                  :type="v.type === 'date' ? 'date' : v.type === 'month' ? 'month' : v.type === 'number' ? 'number' : 'text'"
                  placeholder="默认值（可选）"
                />
              </div>
            </div>
          </div>
        </div>

        <div v-else class="text-[11px] text-text-light text-center py-2">
          SQL 中未检测到 <span class="font-mono">&#123;&#123;变量&#125;&#125;</span> 占位符
        </div>
      </div>

      <!-- footer -->
      <div class="flex items-center justify-end gap-2 px-5 py-4 border-t border-border">
        <Button variant="secondary" @click="emit('close')">取消</Button>
        <Button variant="primary" :disabled="!templateName.trim()" @click="save">保存模板</Button>
      </div>
    </div>
  </div>
</template>
