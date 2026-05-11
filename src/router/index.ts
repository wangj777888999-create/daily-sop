import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/home'
  },
  {
    path: '/home',
    name: 'home',
    component: () => import('@/ui/pages/home/HomePage.vue'),
    meta: { title: '工作台首页' }
  },
  {
    path: '/toolbox',
    name: 'toolbox',
    component: () => import('@/ui/pages/toolbox/ToolboxPage.vue'),
    meta: { title: '工具箱' }
  },
  {
    path: '/toolbox/:toolId',
    name: 'toolbox-detail',
    component: () => import('@/ui/pages/toolbox/ToolDetailPage.vue'),
    meta: { title: '工具' },
    children: [
      {
        path: 'monthly-analysis',
        name: 'monthly-analysis-tool',
        component: () => import('@/ui/pages/tools/MonthlyAnalysis.vue'),
        meta: { title: '校内月度分析' }
      }
    ]
  },
  {
    path: '/policy',
    name: 'policy',
    component: () => import('@/ui/pages/policy/PolicyPage.vue'),
    meta: { title: '政策报告撰写' }
  },
  {
    path: '/analytics',
    name: 'analytics',
    component: () => import('@/ui/pages/analytics/AnalyticsPage.vue'),
    meta: { title: '高级数据分析' }
  },
  {
    path: '/database',
    name: 'database',
    component: () => import('@/ui/pages/database/DatabasePage.vue'),
    meta: { title: '数据库连接' }
  },
  {
    path: '/knowledge',
    name: 'knowledge',
    component: () => import('@/ui/pages/knowledge/KnowledgePage.vue'),
    meta: { title: '个人知识库' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, _from, next) => {
  document.title = `${to.meta.title || '工作台'} - 智能工作台`
  next()
})

export default router
