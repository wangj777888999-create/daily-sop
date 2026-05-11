<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { tools } from '@/data/tools'

const route = useRoute()
const router = useRouter()
const iframeRef = ref<HTMLIFrameElement | null>(null)

const tool = computed(() => tools.find(t => t.id === route.params.toolId))
const getIconBg = (color: string) => color + '15'
const openInNewWindow = (src: string | undefined) => { if (src) window.open(src, '_blank') }

// --- Artifact injection for iframe tools ---
async function handleImportArtifact() {
  try {
    const resp = await fetch('/api/artifacts?type=monthly-analysis')
    const artifacts = await resp.json()
    if (!artifacts.length) {
      alert('暂无可用的平台数据，请先在「校内月度分析」中生成数据。')
      return
    }
    // Simple selection: pick the most recent one
    // TODO: show a proper selection dialog if multiple artifacts exist
    const chosen = artifacts[0]
    if (iframeRef.value?.contentWindow) {
      iframeRef.value.contentWindow.postMessage({
        type: 'ARTIFACT_INJECT',
        artifact: {
          name: chosen.name,
          type: chosen.type,
          data: chosen.data,
        },
      }, '*')
    }
  } catch (e) {
    console.error('Failed to import artifact:', e)
    alert('导入失败，请检查后端服务是否正常。')
  }
}
</script>

<template>
  <div v-if="tool">
    <div class="flex items-center gap-3 mb-4">
      <button
        class="flex items-center gap-1.5 text-[12px] text-text-light hover:text-text-heading transition-colors px-2 py-1 rounded-md hover:bg-chip"
        @click="router.push('/toolbox')"
      >
        ← 返回工具箱
      </button>
      <div class="w-px h-4 bg-border" />
      <div
        class="w-7 h-7 rounded-lg flex items-center justify-center text-sm"
        :style="{ backgroundColor: getIconBg(tool.color), color: tool.color }"
      >
        {{ tool.icon }}
      </div>
      <span class="text-[14px] font-bold text-text-heading">{{ tool.name }}</span>

      <!-- Artifact import button for iframe tools -->
      <button
        v-if="tool.type === 'iframe'"
        class="text-[11px] text-accent hover:text-accent-dark transition-colors px-2 py-1 rounded-md hover:bg-accent-light border border-accent/30"
        @click="handleImportArtifact"
      >
        ↓ 从平台导入
      </button>

      <button
        v-if="tool.type === 'iframe' && tool.src"
        class="ml-auto text-[11px] text-text-light hover:text-accent transition-colors px-2 py-1 rounded-md hover:bg-accent-light"
        @click="openInNewWindow(tool.src)"
      >
        ↗ 新窗口打开
      </button>
    </div>

    <!-- iframe tool -->
    <div
      v-if="tool.type === 'iframe'"
      class="bg-gradient-to-b from-card-bg to-card-gradient border border-border/70 rounded-xl shadow-card overflow-hidden"
    >
      <iframe
        ref="iframeRef"
        :src="tool.src"
        class="w-full border-0"
        :style="{ height: (tool.iframeHeight || 800) + 'px' }"
        :title="tool.name"
      />
    </div>

    <!-- vue tool -->
    <div v-else-if="tool.type === 'vue'">
      <router-view />
    </div>
  </div>

  <div v-else class="flex flex-col items-center justify-center py-20">
    <p class="text-[14px] text-text-body font-medium">工具不存在</p>
    <button
      class="mt-3 text-[12px] text-accent hover:underline"
      @click="router.push('/toolbox')"
    >
      返回工具箱
    </button>
  </div>
</template>
