<script setup lang="ts">
import type { Section } from '@/services/campusReportApi'
defineProps<{ schoolId: string; section: Section }>()
defineEmits<{ updated: [section: Section] }>()
</script>
<template><div class="p-4 text-[12px] text-text-light">编辑器（加载中…）</div></template>
