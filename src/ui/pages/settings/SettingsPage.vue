<template>
  <div class="max-w-2xl mx-auto py-xl">

    <!-- 页面标题 -->
    <div class="mb-xl">
      <h1 class="text-title-lg text-text-heading">系统设置</h1>
      <p class="text-body text-text-light mt-1">配置 AI 工作台的运行参数</p>
    </div>

    <!-- API 配置卡片 -->
    <div class="bg-card-bg border border-border rounded-xl p-xl shadow-sm">

      <!-- 卡片标题 -->
      <div class="flex items-center gap-2 mb-lg">
        <span class="text-[16px]">🔑</span>
        <h2 class="text-title-sm text-text-heading">Claude API 配置</h2>
      </div>

      <!-- 当前状态指示 -->
      <div class="flex items-center gap-2 mb-lg">
        <span
          class="w-2 h-2 rounded-full flex-shrink-0"
          :class="status.api_key_configured ? 'bg-accent' : 'bg-amber'"
        />
        <span class="text-helper text-text-body">
          {{ status.api_key_configured
            ? `已配置 · ${status.api_key_preview}`
            : '未配置 · 请输入 API Key 后保存' }}
        </span>
      </div>

      <!-- 输入区 -->
      <div class="mb-lg">
        <label class="block text-label text-text-body mb-sm">
          Anthropic API Key
        </label>
        <div class="relative">
          <input
            v-model="inputKey"
            :type="showKey ? 'text' : 'password'"
            placeholder="sk-ant-api03-..."
            class="w-full bg-page-bg border border-border rounded-lg px-md py-[10px] pr-10
                   text-body text-text-heading placeholder:text-text-light
                   focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/30
                   transition-colors font-mono text-[12px]"
          />
          <!-- 眼睛图标 -->
          <button
            type="button"
            @click="showKey = !showKey"
            class="absolute right-3 top-1/2 -translate-y-1/2 text-text-light
                   hover:text-text-body transition-colors text-[14px]"
          >
            {{ showKey ? '🙈' : '👁' }}
          </button>
        </div>
        <p class="text-[11px] text-text-light mt-sm">
          前往
          <a
            href="https://console.anthropic.com/settings/keys"
            target="_blank"
            class="text-accent hover:underline"
          >console.anthropic.com</a>
          获取 API Key
        </p>
      </div>

      <!-- 测试结果提示 -->
      <div
        v-if="testResult"
        class="flex items-start gap-2 px-md py-sm rounded-lg mb-lg text-helper"
        :class="testResult.success
          ? 'bg-accent-light text-accent-dark border border-accent/20'
          : 'bg-red-50 text-red-700 border border-red-200'"
      >
        <span class="flex-shrink-0 mt-[1px]">{{ testResult.success ? '✓' : '✗' }}</span>
        <span>{{ testResult.message }}</span>
      </div>

      <!-- 保存成功提示 -->
      <div
        v-if="savedTip"
        class="flex items-center gap-2 px-md py-sm rounded-lg mb-lg text-helper
               bg-accent-light text-accent-dark border border-accent/20"
      >
        <span>✓</span>
        <span>配置已保存，重启后端后生效</span>
      </div>

      <!-- 操作按钮 -->
      <div class="flex items-center gap-sm">
        <button
          @click="handleTest"
          :disabled="testing || !currentKey"
          class="flex items-center gap-1.5 px-md py-[8px] rounded-lg border border-border
                 text-body text-text-body hover:bg-chip hover:border-accent/40
                 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <span v-if="testing" class="animate-spin text-[12px]">◌</span>
          <span>{{ testing ? '测试中…' : '测试连接' }}</span>
        </button>

        <button
          @click="handleSave"
          :disabled="saving || !inputKey.trim()"
          class="flex items-center gap-1.5 px-md py-[8px] rounded-lg
                 bg-gradient-to-r from-accent to-accent-dark text-white
                 hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed
                 transition-opacity shadow-sm"
        >
          <span v-if="saving" class="animate-spin text-[12px]">◌</span>
          <span>{{ saving ? '保存中…' : '保存' }}</span>
        </button>
      </div>

    </div>

    <!-- 占位：未来可扩展更多设置项 -->
    <div class="mt-xl text-helper text-text-light text-center">
      更多系统参数配置即将推出
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { getSettings, saveSettings, testConnection } from '@/services/settingsApi'
import type { SettingsStatus, TestResult } from '@/services/settingsApi'

const status = ref<SettingsStatus>({ api_key_configured: false, api_key_preview: '' })
const inputKey = ref('')
const showKey = ref(false)
const testing = ref(false)
const saving = ref(false)
const testResult = ref<TestResult | null>(null)
const savedTip = ref(false)

// 用于测试的 key：优先用输入框里的，否则用已配置的（通过测试接口取）
const currentKey = computed(() => inputKey.value.trim() || status.value.api_key_configured)

onMounted(async () => {
  try {
    status.value = await getSettings()
  } catch {
    // 忽略，保持默认状态
  }
})

async function handleTest() {
  // 如果输入框有新值，先保存再测试
  if (inputKey.value.trim()) {
    await handleSave(false)
  }
  testing.value = true
  testResult.value = null
  try {
    testResult.value = await testConnection()
  } catch {
    testResult.value = { success: false, message: '请求失败，请检查后端是否运行' }
  } finally {
    testing.value = false
  }
}

async function handleSave(showTip = true) {
  const key = inputKey.value.trim()
  if (!key) return
  saving.value = true
  savedTip.value = false
  try {
    await saveSettings(key)
    status.value = await getSettings()
    inputKey.value = ''
    if (showTip) {
      savedTip.value = true
      setTimeout(() => { savedTip.value = false }, 4000)
    }
  } catch (e: any) {
    testResult.value = { success: false, message: e.message || '保存失败' }
  } finally {
    saving.value = false
  }
}
</script>
