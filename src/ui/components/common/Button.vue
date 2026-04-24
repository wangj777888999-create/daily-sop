<script setup lang="ts">
interface Props {
  variant?: 'primary' | 'secondary'
  size?: 'normal' | 'small'
  icon?: string
}

withDefaults(defineProps<Props>(), {
  variant: 'primary',
  size: 'normal'
})
</script>

<template>
  <button
    class="inline-flex items-center gap-1.5 cursor-pointer transition-colors font-medium"
    :class="[
      variant === 'primary'
        ? 'bg-accent text-white border border-accent hover:bg-accent/90'
        : 'bg-chip text-text-body border border-border hover:bg-chip/80',
      size === 'normal'
        ? 'px-[18px] py-2 text-[12px] rounded-lg'
        : 'px-3 py-1 text-[11px] rounded-md'
    ]"
  >
    <span v-if="icon" class="text-[13px]">{{ icon }}</span>
    <slot />
  </button>
</template>
