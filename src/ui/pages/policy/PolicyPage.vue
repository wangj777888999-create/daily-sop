<script setup lang="ts">
import Card from '@/ui/components/common/Card.vue'
import Button from '@/ui/components/common/Button.vue'
import Chip from '@/ui/components/common/Chip.vue'
import RowTitle from '@/ui/components/common/RowTitle.vue'

const outline: Array<{
  id: number
  text: string
  indent?: number
  active: boolean
}> = []
</script>

<template>
  <div class="flex gap-3.5 h-full">
    <Card class="w-[230px] flex-shrink-0 flex flex-col">
      <RowTitle label="文档大纲" />
      <div class="flex-1 overflow-y-auto">
        <div
          v-for="item in outline"
          :key="item.id"
          class="px-2 py-1.5 rounded-md mb-0.5 cursor-pointer text-[12px] transition-colors"
          :class="[
            item.active
              ? 'bg-accent-light text-accent border-l-2 border-accent'
              : 'text-text-body hover:bg-page-bg',
            item.indent ? 'ml-4' : ''
          ]"
          :style="{ paddingLeft: `${8 + (item.indent || 0) * 16}px` }"
        >
          {{ item.text }}
        </div>
      </div>
      <div class="mt-auto pt-2.5 border-t border-border">
        <Button variant="secondary" style="width: 100%; justify-content: center; font-size: 11px">
          ＋ 添加章节
        </Button>
      </div>
    </Card>

    <div class="flex-1 flex flex-col min-w-0">
      <div class="bg-card-bg border border-border border-b-none rounded-t-lg px-3 py-2 flex items-center gap-1.5 flex-wrap">
        <Chip v-for="t in ['B', 'I', 'U']" :key="t" style="font-size: 10px">{{ t }}</Chip>
        <div class="w-px h-4 bg-border mx-0.5" />
        <Chip v-for="t in ['H1', 'H2']" :key="t" style="font-size: 10px">{{ t }}</Chip>
        <div class="w-px h-4 bg-border mx-0.5" />
        <Chip v-for="t in ['列表', '引用']" :key="t" style="font-size: 10px">{{ t }}</Chip>
        <div class="w-px h-4 bg-border mx-0.5" />
        <Chip style="font-size: 10px">插图</Chip>
        <Chip accent style="font-size: 10px">AI润色</Chip>
      </div>

      <Card class="flex-1 rounded-t-none overflow-hidden">
        <h2 class="text-[16px] font-bold text-text-heading mb-2.5">请选择文档章节</h2>
        <p class="text-[11px] text-text-light">从左侧大纲选择要编辑的章节</p>
      </Card>
    </div>

    <div class="w-[210px] flex-shrink-0 flex flex-col gap-2.5">
      <Card>
        <RowTitle label="文档信息" />
        <div class="space-y-1.5 text-[11px]">
          <div
            v-for="[key, val] in [['字数', '0'], ['章节数', '0'], ['状态', '-'], ['上次保存', '-']]"
            :key="key"
            class="flex justify-between py-1 border-b border-border last:border-b-0"
          >
            <span class="text-text-light">{{ key }}</span>
            <span class="text-text-body">{{ val }}</span>
          </div>
        </div>
      </Card>

      <Card>
        <RowTitle label="导出" />
        <div class="space-y-1.5">
          <Button v-for="t in ['导出 Word (.docx)', '导出 PDF', '复制全文 Markdown']" :key="t"
            variant="secondary"
            style="width: 100%; justify-content: center; font-size: 11px"
          >
            {{ t }}
          </Button>
        </div>
      </Card>

      <Card class="flex-1">
        <RowTitle label="参考资料" />
      </Card>
    </div>
  </div>
</template>
