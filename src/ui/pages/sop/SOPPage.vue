<script setup lang="ts">
import { ref } from 'vue'
import Card from '@/ui/components/common/Card.vue'
import Button from '@/ui/components/common/Button.vue'
import StepBadge from '@/ui/components/common/StepBadge.vue'
import StepDivider from '@/ui/components/common/StepDivider.vue'
import RowTitle from '@/ui/components/common/RowTitle.vue'
import DataTable from '@/ui/components/common/DataTable.vue'
import SearchBox from '@/ui/components/common/SearchBox.vue'

const currentStep = ref(1)
const selectedTemplate = ref<number | null>(null)
const searchQuery = ref('')

const steps = [
  { step: 1, label: '上传数据' },
  { step: 2, label: '选择 SOP' },
  { step: 3, label: '配置参数' },
  { step: 4, label: '生成报告' }
]

const templates: Array<{
  id: number
  name: string
  desc: string
}> = []

const tableColumns: string[] = []

const getStepStatus = (step: number) => {
  if (step < currentStep.value) return 'completed'
  if (step === currentStep.value) return 'active'
  return 'pending'
}
</script>

<template>
  <div class="flex flex-col h-full">
    <div class="flex items-center gap-1.5 mb-5">
      <template v-for="(s, i) in steps" :key="s.step">
        <StepBadge
          :step="s.step"
          :label="s.label"
          :status="getStepStatus(s.step)"
        />
        <StepDivider v-if="i < steps.length - 1" :active="s.step < currentStep" />
      </template>
    </div>

    <div class="flex gap-3.5 flex-1 min-h-0">
      <Card class="w-[272px] flex-shrink-0 flex flex-col">
        <RowTitle label="SOP 模板库" />
        <SearchBox v-model="searchQuery" placeholder="🔍 搜索模板…" class="mb-2.5" />

        <div class="flex-1 overflow-y-auto">
          <div
            v-for="tpl in templates"
            :key="tpl.id"
            @click="selectedTemplate = tpl.id"
            class="px-[11px] py-2 rounded-md mb-1 cursor-pointer transition-colors text-[12px]"
            :class="selectedTemplate === tpl.id
              ? 'bg-accent text-white'
              : 'bg-page-bg border border-border text-text-body hover:border-accent/50'"
          >
            <div class="flex items-center justify-between">
              <span>{{ tpl.name }}</span>
              <span
                v-if="selectedTemplate === tpl.id"
                class="text-[10px] bg-white/25 px-1.5 py-0.5 rounded-full"
              >
                已选
              </span>
            </div>
          </div>
        </div>
      </Card>

      <div class="flex-1 flex flex-col gap-3.5 min-w-0">
        <Card>
          <RowTitle label="SOP 详情" />
          <p class="text-[11px] text-text-light leading-relaxed mb-2.5">
            请从左侧选择 SOP 模板
          </p>
          <div class="flex gap-1.5 mb-2.5 flex-wrap">
          </div>
          <p class="text-[11px] text-text-body"></p>
        </Card>

        <Card class="flex-1 flex flex-col min-h-0">
          <RowTitle label="数据预览" />
          <DataTable :columns="tableColumns" :row-count="0" />
        </Card>
      </div>
    </div>

    <div class="flex justify-end gap-2.5 mt-3.5 pt-3.5 border-t border-border">
      <Button variant="secondary">← 上一步</Button>
      <Button variant="primary">开始分析 →</Button>
    </div>
  </div>
</template>
