import { defineStore } from 'pinia'
import type { AIMessage } from '@/types'

interface AIChatState {
  messages: AIMessage[]
  isTyping: boolean
  quickActions: string[]
}

export const useAIChatStore = defineStore('aiChat', {
  state: (): AIChatState => ({
    messages: [],
    isTyping: false,
    quickActions: ['🔍 搜索知识库', '📝 撰写政策', '📊 生成报告'],
  }),

  actions: {
    addMessage(message: Omit<AIMessage, 'id' | 'timestamp'>) {
      this.messages.push({
        ...message,
        id: Date.now().toString(),
        timestamp: Date.now()
      })
    },

    setTyping(typing: boolean) {
      this.isTyping = typing
    },

    setQuickActions(actions: string[]) {
      this.quickActions = actions
    },

    clearMessages() {
      this.messages = []
    }
  }
})
