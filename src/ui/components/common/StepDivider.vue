<script setup lang="ts">
interface Props {
  active?: boolean
}

withDefaults(defineProps<Props>(), {
  active: false
})
</script>

<template>
  <div
    class="flex-1 h-0.5 self-center"
    :class="active ? 'bg-accent/40' : 'bg-border'"
  />
</template>
