<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import Card from '@/ui/components/common/Card.vue'
import Button from '@/ui/components/common/Button.vue'
import Input from '@/ui/components/common/Input.vue'
import Chip from '@/ui/components/common/Chip.vue'
import RowTitle from '@/ui/components/common/RowTitle.vue'
import { createSOP, parsePythonCode, type SOPStep } from '@/services/sopApi'

const router = useRouter()

const pythonCode = ref('')
const sopName = ref('')
const sopDescription = ref('')
const tags = ref<string[]>([])
const newTag = ref('')
const parsedSteps = ref<SOPStep[]>([])
const isParsing = ref(false)
const isSaving = ref(false)
const parseError = ref('')
const hasParsed = ref(false)

const canSave = computed(() => {
  return sopName.value.trim() && parsedSteps.value.length > 0
})

const canParse = computed(() => {
  return pythonCode.value.trim().length > 0
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

function updateStepDescription(index: number, value: string) {
  if (parsedSteps.value[index]) {
    parsedSteps.value[index].description = value
  }
}

function updateStepCode(index: number, value: string) {
  if (parsedSteps.value[index]) {
    parsedSteps.value[index].code = value
  }
}

function removeStep(index: number) {
  parsedSteps.value.splice(index, 1)
  parsedSteps.value.forEach((step, i) => {
    step.order = i + 1
  })
}

function addStep() {
  const newOrder = parsedSteps.value.length + 1
  parsedSteps.value.push({
    id: `step-${newOrder}`,
    order: newOrder,
    description: '',
    code: ''
  })
}

async function handleParse() {
  if (!canParse.value) return

  isParsing.value = true
  parseError.value = ''
  hasParsed.value = false

  try {
    const result = await parsePythonCode(pythonCode.value)
    if (result && result.length > 0) {
      parsedSteps.value = result
      hasParsed.value = true
      // Auto-fill name from first function def if not set
      if (!sopName.value) {
        const firstFunc = pythonCode.value.match(/def\s+(\w+)/)
        if (firstFunc) {
          sopName.value = firstFunc[1].replace(/_/g, ' ')
        }
      }
    } else {
      parseError.value = '无法解析代码，请确保代码格式正确'
    }
  } catch (error) {
    console.error('Parse error:', error)
    parseError.value = '解析失败，请检查代码格式'
  } finally {
    isParsing.value = false
  }
}

async function handleSave() {
  if (!canSave.value) return

  isSaving.value = true
  try {
    const sop = {
      name: sopName.value,
      description: sopDescription.value,
      steps: parsedSteps.value,
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

function handleFileUpload(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  const reader = new FileReader()
  reader.onload = (e) => {
    pythonCode.value = e.target?.result as string || ''
  }
  reader.readAsText(file)
}
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <div>
        <h1 class="text-[20px] font-bold text-text-heading">导入 Python 代码</h1>
        <p class="text-[13px] text-text-light mt-0.5">将 Python 代码解析为 SOP 步骤</p>
      </div>
      <Button variant="secondary" @click="goBack">← 返回</Button>
    </div>

    <!-- Main Content -->
    <div class="flex gap-4 flex-1 min-h-0">
      <!-- Left: Code Input -->
      <Card class="w-96 flex-shrink-0 flex flex-col">
        <RowTitle label="Python 代码" />

        <div class="mb-3">
          <div class="flex items-center justify-between mb-2">
            <label class="text-[11px] text-text-light">上传文件</label>
            <label class="text-[11px] text-accent cursor-pointer hover:underline">
              选择文件…
              <input
                type="file"
                accept=".py,.pyw"
                class="hidden"
                @change="handleFileUpload"
              />
            </label>
          </div>
        </div>

        <div class="flex-1 flex flex-col">
          <label class="text-[11px] text-text-light mb-1 block">粘贴代码</label>
          <textarea
            v-model="pythonCode"
            placeholder="# 将 Python 代码粘贴到此处&#10;&#10;def analyze_sales_data(df):&#10;    # Step 1: 读取数据&#10;    data = pd.read_excel('sales.xlsx')&#10;    &#10;    # Step 2: 数据清洗&#10;    data = data.dropna()&#10;    &#10;    # Step 3: 分析&#10;    result = data.groupby('product').sum()&#10;    &#10;    return result"
            class="flex-1 w-full bg-chip border border-border rounded-md px-3 py-2 text-[11px] text-text-body placeholder-text-light outline-none transition-shadow focus:border-accent font-mono resize-none"
            style="min-height: 300px"
          />
        </div>

        <div v-if="parseError" class="text-[11px] text-red-500 mt-2 mb-2">
          {{ parseError }}
        </div>

        <Button
          variant="primary"
          class="w-full mt-3"
          :disabled="!canParse || isParsing"
          @click="handleParse"
        >
          {{ isParsing ? '解析中…' : '🔍 解析代码' }}
        </Button>
      </Card>

      <!-- Right: Parsed Preview -->
      <Card class="flex-1 flex flex-col min-w-0">
        <RowTitle label="解析预览" />

        <div class="mb-3">
          <label class="text-[11px] text-text-light mb-1 block">SOP 名称</label>
          <Input
            v-model="sopName"
            placeholder="自动从代码中提取，或手动输入…"
          />
        </div>

        <div class="mb-3">
          <label class="text-[11px] text-text-light mb-1 block">SOP 描述</label>
          <Input
            v-model="sopDescription"
            placeholder="简要描述这个 SOP 的用途…"
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

        <!-- Parsed Steps -->
        <div class="flex-1 overflow-y-auto">
          <div v-if="!hasParsed" class="flex flex-col items-center justify-center h-full">
            <div class="text-[48px] mb-3">🐍</div>
            <h3 class="text-[14px] font-bold text-text-heading mb-1">暂无解析结果</h3>
            <p class="text-[11px] text-text-light">在左侧粘贴代码后点击「解析代码」</p>
          </div>

          <div v-else class="space-y-3">
            <div
              v-for="(step, index) in parsedSteps"
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
                <label class="text-[10px] text-text-light mb-1 block">执行代码</label>
                <textarea
                  :value="step.code || ''"
                  @input="(e) => updateStepCode(index, (e.target as HTMLTextAreaElement).value)"
                  class="w-full h-20 bg-chip border border-border rounded-md px-3 py-2 text-[11px] text-text-body placeholder-text-light outline-none focus:border-accent font-mono resize-none"
                  :class="{ 'bg-placeholder': !step.code }"
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
        {{ isSaving ? '导入中…' : '💾 导入 SOP' }}
      </Button>
    </div>
  </div>
</template>
