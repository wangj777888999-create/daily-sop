<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import Card from '@/ui/components/common/Card.vue'
import Button from '@/ui/components/common/Button.vue'
import Input from '@/ui/components/common/Input.vue'
import Chip from '@/ui/components/common/Chip.vue'
import RowTitle from '@/ui/components/common/RowTitle.vue'
import { createSOP, generateSOPFromDescription, type SOPStep } from '@/services/sopApi'

const router = useRouter()

const sopName = ref('')
const sopDescription = ref('')
const descriptionInput = ref('')
const tags = ref<string[]>([])
const newTag = ref('')
const generatedSteps = ref<SOPStep[]>([])
const isGenerating = ref(false)
const isSaving = ref(false)
const activeTab = ref<'input' | 'preview'>('input')

// Auto-generate preview when description changes
watch(descriptionInput, async (newVal) => {
  if (newVal.length > 20 && !isGenerating.value) {
    activeTab.value = 'preview'
  }
})

const canSave = computed(() => {
  return sopName.value.trim() && generatedSteps.value.length > 0
})

function addTag() {
  const tag = newTag.value.trim()
  if (tag && !tags.value.includes(tag)) {
    tags.value.push(tag)
  }
  newTag.value = ''
}

function removeTag(tag: string) {
  tags.value = tags.value.filter(t => t !== tag)
}

async function generatePreview() {
  if (!descriptionInput.value.trim()) return

  isGenerating.value = true
  try {
    const result = await generateSOPFromDescription(descriptionInput.value)
    if (result) {
      sopName.value = result.name || ''
      sopDescription.value = result.description || ''
      if (result.steps) {
        generatedSteps.value = result.steps
      } else if (result as any) {
        // Fallback: create steps from description
        generatedSteps.value = (descriptionInput.value as any).split('\n')
          .filter((line: string) => line.trim())
          .map((line: string, index: number) => ({
            id: `step-${index + 1}`,
            order: index + 1,
            description: line.trim(),
            code: ''
          }))
      }
      activeTab.value = 'preview'
    }
  } catch (error) {
    console.error('Failed to generate SOP:', error)
  } finally {
    isGenerating.value = false
  }
}

function updateStepDescription(index: number, value: string) {
  if (generatedSteps.value[index]) {
    generatedSteps.value[index].description = value
  }
}

function updateStepCode(index: number, value: string) {
  if (generatedSteps.value[index]) {
    generatedSteps.value[index].code = value
  }
}

function addStep() {
  const newOrder = generatedSteps.value.length + 1
  generatedSteps.value.push({
    id: `step-${newOrder}`,
    order: newOrder,
    description: '',
    code: ''
  })
}

function removeStep(index: number) {
  generatedSteps.value.splice(index, 1)
  // Re-order remaining steps
  generatedSteps.value.forEach((step, i) => {
    step.order = i + 1
  })
}

async function handleSave() {
  if (!canSave.value) return

  isSaving.value = true
  try {
    const sop = {
      name: sopName.value,
      description: sopDescription.value,
      steps: generatedSteps.value,
      tags: tags.value
    }

    const result = await createSOP(sop)
    if (result) {
      router.push('/sop')
    }
  } catch (error) {
    console.error('Failed to save SOP:', error)
  } finally {
    isSaving.value = false
  }
}

function goBack() {
  router.push('/sop')
}
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <div>
        <h1 class="text-[20px] font-bold text-text-heading">新建 SOP</h1>
        <p class="text-[13px] text-text-light mt-0.5">通过自然语言描述创建标准操作流程</p>
      </div>
      <Button variant="secondary" @click="goBack">← 返回</Button>
    </div>

    <!-- Main Content -->
    <div class="flex gap-4 flex-1 min-h-0">
      <!-- Left: Input Panel -->
      <Card class="w-96 flex-shrink-0 flex flex-col">
        <RowTitle label="描述操作流程" />

        <div class="mb-3">
          <label class="text-[11px] text-text-light mb-1 block">SOP 名称</label>
          <Input
            v-model="sopName"
            placeholder="输入 SOP 名称…"
          />
        </div>

        <div class="mb-3">
          <label class="text-[11px] text-text-light mb-1 block">SOP 描述</label>
          <Input
            v-model="sopDescription"
            placeholder="简要描述这个 SOP 的用途…"
          />
        </div>

        <div class="mb-3 flex-1 flex flex-col">
          <label class="text-[11px] text-text-light mb-1 block">自然语言描述</label>
          <textarea
            v-model="descriptionInput"
            placeholder="用自然语言描述操作步骤，例如：&#10;&#10;1. 首先读取上传的 Excel 文件&#10;2. 筛选出最近一个月的数据&#10;3. 按产品类别汇总销售额&#10;4. 生成包含图表的分析报告"
            class="flex-1 w-full bg-page-bg border border-border rounded-md px-3 py-2 text-[12px] text-text-body placeholder-text-light outline-none transition-shadow focus:border-accent focus:shadow-input-focus resize-none"
            style="min-height: 200px"
          />
        </div>

        <div class="mb-3">
          <label class="text-[11px] text-text-light mb-1 block">标签</label>
          <div class="flex flex-wrap gap-1 mb-2">
            <Chip
              v-for="tag in tags"
              :key="tag"
              accent
              @click="removeTag(tag)"
            >
              {{ tag }} ×
            </Chip>
          </div>
          <div class="flex gap-2">
            <Input
              v-model="newTag"
              placeholder="添加标签…"
              @keydown.enter.prevent="addTag"
            />
            <Button variant="secondary" size="small" @click="addTag">添加</Button>
          </div>
        </div>

        <Button
          variant="primary"
          class="w-full"
          :disabled="!descriptionInput.trim() || isGenerating"
          @click="generatePreview"
        >
          {{ isGenerating ? '生成中…' : '✨ 智能生成步骤预览' }}
        </Button>
      </Card>

      <!-- Right: Preview Panel -->
      <Card class="flex-1 flex flex-col min-w-0">
        <RowTitle label="步骤预览" action="可编辑" />

        <!-- Tab Switcher -->
        <div class="flex gap-2 mb-3">
          <Chip :active="activeTab === 'input'" @click="activeTab = 'input'">
            📝 手动输入
          </Chip>
          <Chip :active="activeTab === 'preview'" @click="activeTab = 'preview'">
            👁️ 预览编辑
          </Chip>
        </div>

        <!-- Manual Input Tab -->
        <div v-if="activeTab === 'input'" class="flex-1 flex flex-col">
          <div class="text-[11px] text-text-light mb-2">
            手动输入各个步骤，或使用左侧的「智能生成」功能
          </div>
          <Button variant="secondary" size="small" @click="addStep" class="self-start mb-3">
            ＋ 添加步骤
          </Button>
        </div>

        <!-- Preview Tab -->
        <div v-if="activeTab === 'preview'" class="flex-1 overflow-y-auto">
          <div v-if="generatedSteps.length === 0" class="flex flex-col items-center justify-center h-full">
            <div class="text-[48px] mb-3">📋</div>
            <h3 class="text-[14px] font-bold text-text-heading mb-1">暂无预览</h3>
            <p class="text-[11px] text-text-light">在左侧输入描述后点击「智能生成」</p>
          </div>

          <div v-else class="space-y-3">
            <div
              v-for="(step, index) in generatedSteps"
              :key="step.id"
              class="bg-page-bg border border-border rounded-lg p-3"
            >
              <div class="flex items-center gap-2 mb-2">
                <div
                  class="w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold"
                  :style="{
                    backgroundColor: '#D6EDE7',
                    color: '#5B8F7A'
                  }"
                >
                  {{ index + 1 }}
                </div>
                <span class="text-[11px] text-text-light">步骤 {{ index + 1 }}</span>
                <button
                  @click="removeStep(index)"
                  class="ml-auto text-[11px] text-text-light hover:text-red-500"
                >
                  删除
                </button>
              </div>

              <div class="mb-2">
                <label class="text-[10px] text-text-light mb-1 block">步骤描述</label>
                <Input
                  :model-value="step.description"
                  @update:model-value="(v) => updateStepDescription(index, v)"
                  placeholder="描述这个步骤做什么…"
                />
              </div>

              <div>
                <label class="text-[10px] text-text-light mb-1 block">执行代码（可选）</label>
                <textarea
                  :value="step.code || ''"
                  @input="(e) => updateStepCode(index, (e.target as HTMLTextAreaElement).value)"
                  placeholder="# Python 代码（可选）"
                  class="w-full h-20 bg-chip border border-border rounded-md px-3 py-2 text-[11px] text-text-body placeholder-text-light outline-none focus:border-accent font-mono resize-none"
                />
              </div>
            </div>

            <Button variant="secondary" size="small" @click="addStep" class="self-start">
              ＋ 添加步骤
            </Button>
          </div>
        </div>
      </Card>
    </div>

    <!-- Footer Actions -->
    <div class="flex justify-end gap-2.5 mt-4 pt-4 border-t border-border">
      <Button variant="secondary" @click="goBack">取消</Button>
      <Button
        variant="primary"
        :disabled="!canSave || isSaving"
        @click="handleSave"
      >
        {{ isSaving ? '保存中…' : '💾 保存 SOP' }}
      </Button>
    </div>
  </div>
</template>
