<script setup lang="ts">
interface Props {
  modelValue: string
  placeholder?: string
}

withDefaults(defineProps<Props>(), {
  placeholder: '搜索…'
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

<template>
  <div class="flex items-center gap-2 bg-card-bg border border-border rounded-md px-3 py-1.5">
    <span class="text-[13px] text-text-light">🔍</span>
    <input
      :value="modelValue"
      @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
      :placeholder="placeholder"
      class="flex-1 bg-transparent text-[11px] text-text-body placeholder-text-light outline-none"
    />
  </div>
</template>
