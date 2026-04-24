import { defineStore } from 'pinia'
import type { Breadcrumb } from '@/types'

interface NavigationState {
  currentRoute: string
  breadcrumbs: Breadcrumb[]
}

export const useNavigationStore = defineStore('navigation', {
  state: (): NavigationState => ({
    currentRoute: 'home',
    breadcrumbs: []
  }),

  actions: {
    setCurrentRoute(route: string) {
      this.currentRoute = route
    },
    setBreadcrumbs(breadcrumbs: Breadcrumb[]) {
      this.breadcrumbs = breadcrumbs
    }
  }
})
