<script setup lang="ts">
interface Props {
  active?: boolean
  accent?: boolean
  disabled?: boolean
}

withDefaults(defineProps<Props>(), {
  active: false,
  accent: false,
  disabled: false,
})
</script>

<template>
  <span
    class="inline-flex items-center text-[11px] px-[9px] py-1 rounded-md border transition-colors"
    :class="[
      disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer',
      accent   ? 'bg-accent text-white border-accent' :
      active   ? 'bg-accent-light text-accent border-accent' :
                 'bg-chip text-text-body border-border hover:bg-chip/80'
    ]"
  >
    <slot />
  </span>
</template>
