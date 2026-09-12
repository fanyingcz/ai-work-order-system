import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Repair',
    component: () => import('../views/RepairView.vue'),
    meta: { title: '智能报修' }
  },
  {
    path: '/orders',
    name: 'Orders',
    component: () => import('../views/OrdersView.vue'),
    meta: { title: '工单管理' }
  },
  {
    path: '/order/:orderNo',
    name: 'OrderDetail',
    component: () => import('../views/OrderDetailView.vue'),
    meta: { title: '工单详情' }
  },
  {
    path: '/feedback',
    name: 'Feedback',
    component: () => import('../views/FeedbackView.vue'),
    meta: { title: '反馈管理' }
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('../views/DashboardView.vue'),
    meta: { title: '数据看板' }
  },
  {
    path: '/test',
    name: 'Test',
    component: () => import('../views/TestView.vue'),
    meta: { title: '模型测试' }
  },
  {
    path: '/database',
    name: 'Database',
    component: () => import('../views/DBManagementView.vue'),
    meta: { title: '数据库管理' }
  },
  {
    path: '/prompts',
    name: 'Prompts',
    component: () => import('../views/PromptManagerView.vue'),
    meta: { title: '提示词管理' }
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  // 切页后回到顶部，否则长列表页之间跳转会停在半空
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    return { top: 0 }
  }
})

router.afterEach(to => {
  document.title = `${to.meta.title || '控制台'} · 智能工单系统`
})

export default router
