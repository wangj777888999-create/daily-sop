<script setup lang="ts">
import { ref } from 'vue'
import { useAIChatStore } from '@/stores/aiChat'
import { useKnowledgeStore } from '@/stores/knowledge'
import { generateContent } from '@/services/knowledgeApi'

const chatStore = useAIChatStore()
const kbStore = useKnowledgeStore()
const inputText = ref('')

const handleSend = async () => {
  if (!inputText.value.trim()) return

  chatStore.addMessage({
    role: 'user',
    content: inputText.value
  })
  const prompt = inputText.value
  inputText.value = ''

  chatStore.setTyping(true)
  try {
    const docIds = kbStore.selectedDocument ? [kbStore.selectedDocument.id] : undefined
    const response = await generateContent({
      prompt,
      doc_ids: docIds,
      style: 'general',
      top_k: 3,
    })

    chatStore.addMessage({
      role: 'ai',
      content: response.generated_text,
      sources: response.sources?.map(s => ({
        doc_name: s.doc_name,
        chunk_text: s.content || '',
        heading_path: s.location || '',
        score: 0,
      })) || [],
    })
  } catch {
    chatStore.addMessage({
      role: 'ai',
      content: '抱歉，AI 生成失败。请确认已设置 ANTHROPIC_API_KEY 环境变量。',
    })
  } finally {
    chatStore.setTyping(false)
  }
}

const handleQuickAction = (action: string) => {
  if (action === '🔍 搜索知识库') {
    inputText.value = '在知识库中搜索：'
  } else if (action === '📝 撰写政策') {
    inputText.value = '请参考知识库中的政策文档，撰写一份关于'
  } else if (action === '📊 生成报告') {
    inputText.value = '请参考知识库中的报告模板，生成一份关于'
  } else {
    inputText.value = action
  }
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
          <div v-if="msg.sources?.length" class="mt-2 pt-1.5 border-t border-border">
            <div class="text-[9px] text-text-light mb-1">参考来源：</div>
            <div v-for="(s, i) in msg.sources.slice(0, 3)" :key="i" class="text-[9px] text-text-light truncate">
              · {{ s.doc_name }}
            </div>
          </div>
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
