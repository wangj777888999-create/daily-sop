<script setup lang="ts">
interface Props {
  modelValue: string
  placeholder?: string
  type?: string
}

defineProps<Props>()
const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

<template>
  <input
    :value="modelValue"
    @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    :type="type || 'text'"
    :placeholder="placeholder"
    class="w-full bg-page-bg border border-border rounded-md px-3 py-1.5 text-[12px] text-text-body placeholder:text-text-light outline-none transition-all duration-150 focus:border-accent focus:shadow-input-focus focus:bg-[#FFFDF9]"
  />
</template>
