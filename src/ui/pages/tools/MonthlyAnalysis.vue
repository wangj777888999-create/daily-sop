<script setup lang="ts">
import { ref } from 'vue'
import Button from '@/ui/components/common/Button.vue'
import Card from '@/ui/components/common/Card.vue'

const saving = ref(false)
const message = ref('')

async function handleSaveToPlatform() {
  saving.value = true
  message.value = '保存功能待实现（后续接入分析逻辑）'
  saving.value = false
}
</script>

<template>
  <div class="p-6">
    <Card>
      <div class="flex flex-col gap-4">
        <div>
          <h2 class="text-lg font-bold text-text-heading">校内月度分析</h2>
          <p class="text-sm text-text-light mt-1">上传原始数据，执行分析，保存结果到平台</p>
        </div>

        <div class="border border-dashed border-border rounded-xl p-8 text-center">
          <p class="text-text-light text-sm">分析功能开发中...</p>
          <p class="text-text-light text-xs mt-1">后续支持上传数据文件并执行分析计算</p>
        </div>

        <div class="flex items-center gap-3">
          <Button
            variant="primary"
            :loading="saving"
            @click="handleSaveToPlatform"
          >
            保存到平台
          </Button>
          <span v-if="message" class="text-xs text-text-light">{{ message }}</span>
        </div>
      </div>
    </Card>
  </div>
</template>
