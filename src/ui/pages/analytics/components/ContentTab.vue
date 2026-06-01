<script setup lang="ts">
import type { School } from '@/services/campusReportApi'
defineProps<{ school: School }>()
</script>
<template><div class="text-text-light text-[12px]">内容素材（加载中…）</div></template>
