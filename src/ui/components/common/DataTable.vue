<script setup lang="ts">
interface Props {
  columns: string[]
  rowCount?: number
}

withDefaults(defineProps<Props>(), {
  rowCount: 5
})
</script>

<template>
  <div class="border border-border rounded-lg overflow-hidden text-[11px]">
    <div class="flex bg-chip border-b border-border">
      <div
        v-for="col in columns"
        :key="col"
        class="flex-1 px-2.5 py-[7px] font-semibold text-text-body"
      >
        {{ col }}
      </div>
    </div>
    <div
      v-for="ri in rowCount"
      :key="ri"
      class="flex border-b border-border last:border-b-0"
      :class="ri % 2 === 0 ? 'bg-card-bg' : 'bg-page-bg'"
    >
      <div
        v-for="(_col, ci) in columns"
        :key="ci"
        class="flex-1 px-2.5 py-1.5"
      >
        <div
          class="h-2.5 bg-placeholder rounded"
          :style="{ width: ci === 0 ? '65%' : '45%' }"
        />
      </div>
    </div>
  </div>
</template>
