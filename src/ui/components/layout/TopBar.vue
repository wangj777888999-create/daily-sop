<script setup lang="ts">
interface Props {
  breadcrumbs: string[]
}

defineProps<Props>()
</script>

<template>
  <header class="h-topbar bg-gradient-to-b from-topbar-bg to-[#F9F5EE] border-b border-border/60 px-xl flex items-center gap-3 shadow-[0_1px_0_rgba(196,186,168,0.4)]">
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
