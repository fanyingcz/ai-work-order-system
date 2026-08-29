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
    path: '/test',
    name: 'Test',
    component: () => import('../views/TestView.vue'),
    meta: { title: '模型测试' }
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('../views/DashboardView.vue'),
    meta: { title: '系统仪表盘' }
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
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router