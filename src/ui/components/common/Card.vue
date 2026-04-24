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
    class="bg-card-bg border border-border rounded-lg p-4 transition-shadow"
    :class="{ 'cursor-pointer hover:shadow-card-hover': hoverable }"
  >
    <slot />
  </div>
</template>
