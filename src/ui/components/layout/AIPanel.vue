<script setup lang="ts">
import { ref } from 'vue'
import { useAIChatStore } from '@/stores/aiChat'

const chatStore = useAIChatStore()
const inputText = ref('')

const handleSend = () => {
  if (!inputText.value.trim()) return

  chatStore.addMessage({
    role: 'user',
    content: inputText.value
  })

  chatStore.setTyping(true)
  setTimeout(() => {
    chatStore.setTyping(false)
    chatStore.addMessage({
      role: 'ai',
      content: '好的，我来帮你分析这个问题...'
    })
  }, 1500)

  inputText.value = ''
}

const handleQuickAction = (action: string) => {
  inputText.value = action
}
</script>

<template>
  <aside class="w-ai-panel bg-ai-panel-bg border-l border-border flex flex-col">
    <div class="px-4 py-3 border-b border-border flex items-center gap-2">
      <div class="w-2 h-2 rounded-full bg-accent flex-shrink-0" />
      <span class="text-[13px] font-bold text-text-heading">AI 助理</span>
      <div class="ml-auto text-[10px] font-bold px-2 py-0.5 rounded-full bg-accent-light text-accent">
        Claude
      </div>
    </div>

    <div class="flex-1 p-3 flex flex-col gap-2 overflow-y-auto">
      <template v-for="msg in chatStore.messages" :key="msg.id">
        <div
          v-if="msg.role === 'ai'"
          class="max-w-[92%] rounded-tr-lg rounded-br-lg rounded-bl-sm px-[10px] py-[7px] text-[11px] leading-relaxed bg-card-bg border border-border self-start"
        >
          {{ msg.content }}
        </div>
        <div
          v-else
          class="max-w-[85%] rounded-tl-lg rounded-br-lg rounded-bl-sm px-[10px] py-[7px] text-[11px] leading-relaxed bg-accent text-white self-end"
        >
          {{ msg.content }}
        </div>
      </template>

      <div v-if="chatStore.isTyping" class="flex gap-1 p-1">
        <div class="w-1.5 h-1.5 rounded-full bg-text-light animate-pulse" />
        <div class="w-1.5 h-1.5 rounded-full bg-text-light animate-pulse [animation-delay:150ms]" />
        <div class="w-1.5 h-1.5 rounded-full bg-text-light animate-pulse [animation-delay:300ms]" />
      </div>

      <div v-if="chatStore.messages.length === 0" class="text-[11px] text-text-light text-center py-4">
        发送消息开始与 AI 助理对话
      </div>
    </div>

    <div class="px-3 py-2 border-t border-border">
      <div class="text-[10px] text-text-light mb-1.5">快捷操作</div>
      <div class="flex flex-wrap gap-1">
        <span
          v-for="action in chatStore.quickActions"
          :key="action"
          @click="handleQuickAction(action)"
          class="text-[10px] px-2 py-1 rounded-full bg-chip border border-border cursor-pointer hover:bg-chip/80 transition-colors"
        >
          {{ action }}
        </span>
      </div>
    </div>

    <div class="p-3">
      <div class="flex items-center gap-1.5 bg-card-bg border border-border rounded-lg px-2.5 py-1.5">
        <input
          v-model="inputText"
          type="text"
          placeholder="输入问题或指令…"
          class="flex-1 bg-transparent text-[11px] text-text-body placeholder-text-light outline-none"
          @keyup.enter="handleSend"
        />
        <button
          @click="handleSend"
          class="w-5 h-5 rounded-[5px] bg-accent text-white flex items-center justify-center text-[12px] cursor-pointer hover:bg-accent/90 transition-colors"
        >
          ↑
        </button>
      </div>
    </div>
  </aside>
</template>
