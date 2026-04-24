<script setup lang="ts">
interface Props {
  label: string
  action?: string
}

defineProps<Props>()
</script>

<template>
  <div class="flex items-center mb-2.5 gap-2">
    <h3 class="text-[14px] font-bold text-text-heading">{{ label }}</h3>
    <span
      v-if="action"
      class="ml-auto text-[11px] text-accent cursor-pointer hover:underline"
    >
      {{ action }}
    </span>
  </div>
</template>
