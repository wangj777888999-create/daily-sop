import { defineStore } from 'pinia'
import type { User } from '@/types'

interface AppState {
  user: User
  globalLoading: boolean
}

export const useAppStore = defineStore('app', {
  state: (): AppState => ({
    user: {
      id: '1',
      name: '张三',
      role: '管理员'
    },
    globalLoading: false
  }),

  actions: {
    setUser(user: User) {
      this.user = user
    },
    setLoading(loading: boolean) {
      this.globalLoading = loading
    }
  }
})
