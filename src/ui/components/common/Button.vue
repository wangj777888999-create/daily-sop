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
    class="inline-flex items-center gap-1.5 cursor-pointer font-medium select-none
           transition-all duration-150 ease-spring
           active:scale-[0.97] active:brightness-95"
    :class="[
      variant === 'primary'
        ? 'bg-gradient-to-b from-accent to-accent-dark text-white border border-accent-dark/50 shadow-button-primary hover:brightness-105'
        : 'bg-chip text-text-body border border-border hover:bg-placeholder/50 hover:shadow-sm',
      size === 'normal'
        ? 'px-[18px] py-2 text-[12px] rounded-lg'
        : 'px-3 py-1 text-[11px] rounded-md'
    ]"
  >
    <span v-if="icon" class="text-[13px]">{{ icon }}</span>
    <slot />
  </button>
</template>
