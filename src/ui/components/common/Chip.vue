<script setup lang="ts">
interface Props {
  active?: boolean
  accent?: boolean
}

withDefaults(defineProps<Props>(), {
  active: false,
  accent: false
})
</script>

<template>
  <span
    class="inline-flex items-center text-[11px] px-[9px] py-1 rounded-md border border-border bg-chip text-text-body cursor-pointer transition-colors hover:bg-chip/80"
    :class="{
      'bg-accent text-white border-accent': accent,
      'bg-accent-light text-accent border-accent': active
    }"
  >
    <slot />
  </span>
</template>
