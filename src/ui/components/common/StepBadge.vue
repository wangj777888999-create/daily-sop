<script setup lang="ts">
import type { StepStatus } from '@/types'

interface Props {
  step: number
  label: string
  status: StepStatus
}

defineProps<Props>()
</script>

<template>
  <div
    class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border flex-shrink-0"
    :class="{
      'bg-accent border-accent text-white': status === 'active',
      'bg-accent-light border-accent': status === 'completed',
      'bg-chip border-border text-text-body': status === 'pending'
    }"
  >
    <div
      class="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold"
      :class="{
        'bg-white text-accent': status === 'active',
        'bg-accent text-white': status === 'completed',
        'bg-placeholder-dk text-text-light': status === 'pending'
      }"
    >
      {{ status === 'completed' ? '✓' : step }}
    </div>
    <span class="text-[12px] whitespace-nowrap">{{ label }}</span>
  </div>
</template>
