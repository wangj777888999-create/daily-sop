<script setup lang="ts">
interface Props {
  breadcrumbs: string[]
}

defineProps<Props>()
</script>

<template>
  <header class="h-topbar bg-topbar-bg border-b border-border px-xl flex items-center gap-3">
    <div class="flex-1 flex items-center gap-1 text-[12px]">
      <template v-for="(crumb, index) in breadcrumbs" :key="index">
        <span v-if="index > 0" class="text-border">/</span>
        <span :class="index === breadcrumbs.length - 1 ? 'text-text-heading' : 'text-text-light'">
          {{ crumb }}
        </span>
      </template>
    </div>

    <div class="flex items-center gap-2">
      <button class="w-7 h-7 rounded-md bg-chip border border-border text-[13px] cursor-pointer hover:bg-chip/80 transition-colors">
        🔔
      </button>
      <button class="w-7 h-7 rounded-md bg-chip border border-border text-[13px] cursor-pointer hover:bg-chip/80 transition-colors">
        ⚙
      </button>
      <div class="w-6 h-6 rounded-full bg-placeholder-dk cursor-pointer" />
    </div>
  </header>
</template>
