import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Login',
    component: () => import('../views/LoginView.vue'),
    meta: { title: '工人登录' }
  },
  {
    path: '/orders',
    name: 'Orders',
    component: () => import('../views/OrdersView.vue'),
    meta: { title: '我的工单', requiresAuth: true }
  },
  // 兜底：路径不匹配时回首页，避免出现整页空白
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

// 这个包有两种访问方式，base 必须跟着变，否则其中一种会白屏：
//   1. 经后端统一入口 /worker/ 打开（api.py 会把 /worker/* 回退到本包 index.html）
//   2. 独立部署在域名根路径（如 Netlify）
// 固定成 '/' 会让 (1) 匹配不到路由，固定成 '/worker/' 会让 (2) 匹配不到。
const base = window.location.pathname.startsWith('/worker') ? '/worker/' : '/'

const router = createRouter({
  history: createWebHistory(base),
  routes
})

// 路由守卫：未登录跳转到登录页
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('worker_token')
  if (to.meta.requiresAuth && !token) {
    next('/')
  } else if (to.path === '/' && token) {
    next('/orders')
  } else {
    next()
  }
})

export default router