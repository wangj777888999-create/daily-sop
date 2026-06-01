<script setup lang="ts">
import type { School } from '@/services/campusReportApi'
defineProps<{ selectedSchoolId: string | null }>()
defineEmits<{ select: [school: School] }>()
</script>
<template><aside class="w-[180px] border-r border-border p-3 text-[12px] text-text-light">学校列表（加载中…）</aside></template>
