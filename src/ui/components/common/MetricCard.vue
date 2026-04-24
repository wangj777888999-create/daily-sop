<script setup lang="ts">
interface Props {
  label: string
  value: string | number
  delta?: number
}

defineProps<Props>()
</script>

<template>
  <div class="bg-card-bg border border-border rounded-lg p-4">
    <div class="text-[10px] text-text-light mb-1">{{ label }}</div>
    <div class="text-[22px] font-bold text-text-heading leading-none">{{ value }}</div>
    <div
      v-if="delta !== undefined"
      class="text-[10px] mt-0.5"
      :class="delta >= 0 ? 'text-accent' : 'text-amber'"
    >
      {{ delta >= 0 ? '↑' : '↓' }} {{ Math.abs(delta) }}%
    </div>
  </div>
</template>
