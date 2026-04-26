<script setup lang="ts">
interface Props {
  label: string
  value: string | number
  delta?: number
}

defineProps<Props>()
</script>

<template>
  <div class="bg-gradient-to-b from-card-bg to-card-gradient border border-border/70 rounded-xl p-4 shadow-card transition-all duration-200 hover:shadow-card-hover hover:-translate-y-px flex-1">
    <div class="text-[10px] font-medium text-text-light mb-1 tracking-wide uppercase">{{ label }}</div>
    <div class="text-[24px] font-bold text-text-heading leading-none mt-1">{{ value }}</div>
    <div
      v-if="delta !== undefined"
      class="text-[10px] mt-1.5 font-medium flex items-center gap-0.5"
      :class="delta >= 0 ? 'text-accent' : 'text-amber'"
    >
      {{ delta >= 0 ? '↑' : '↓' }} {{ Math.abs(delta) }}%
    </div>
  </div>
</template>
