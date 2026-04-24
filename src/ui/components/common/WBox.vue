<script setup lang="ts">
interface Props {
  label?: string
  dashed?: boolean
}

withDefaults(defineProps<Props>(), {
  dashed: true
})
</script>

<template>
  <div
    class="border border-dashed border-border rounded-md flex items-center justify-center"
    :class="{ 'border-solid': !dashed }"
  >
    <span class="text-[11px] text-text-light text-center p-2 leading-relaxed whitespace-pre-line">
      {{ label }}
    </span>
  </div>
</template>
