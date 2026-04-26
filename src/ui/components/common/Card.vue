<script setup lang="ts">
interface Props {
  hoverable?: boolean
}

withDefaults(defineProps<Props>(), {
  hoverable: false
})
</script>

<template>
  <div
    class="bg-gradient-to-b from-card-bg to-card-gradient border border-border/70 rounded-xl p-4 shadow-card transition-all duration-200"
    :class="{ 'cursor-pointer hover:shadow-card-hover hover:-translate-y-px': hoverable }"
  >
    <slot />
  </div>
</template>
