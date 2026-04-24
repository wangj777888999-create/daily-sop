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
    path: '/sop',
    name: 'sop',
    component: () => import('@/ui/pages/sop/SOPList.vue'),
    meta: { title: 'SOP 管理' }
  },
  {
    path: '/sop/create',
    name: 'sop-create',
    component: () => import('@/ui/pages/sop/SOPCreate.vue'),
    meta: { title: '新建 SOP' }
  },
  {
    path: '/sop/import',
    name: 'sop-import',
    component: () => import('@/ui/pages/sop/SOPImport.vue'),
    meta: { title: '导入 SOP' }
  },
  {
    path: '/sop/execute/:sopId?',
    name: 'sop-execute',
    component: () => import('@/ui/pages/sop/SOPExecute.vue'),
    meta: { title: '执行 SOP' }
  },
  {
    path: '/sop/edit/:sopId',
    name: 'sop-edit',
    component: () => import('@/ui/pages/sop/SOPCreate.vue'),
    meta: { title: '编辑 SOP' }
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
