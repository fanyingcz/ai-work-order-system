import axios from 'axios'

// API请求统一配置
const http = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' }
})

// 响应拦截器
http.interceptors.response.use(
  response => {
    const { code, message, data } = response.data
    if (code === 0) {
      return data
    } else {
      const err = new Error(message || '请求失败')
      err.code = code
      return Promise.reject(err)
    }
  },
  error => {
    // 统一成带可读 message 的 Error，供页面直接展示
    const data = error?.response?.data
    const raw = (data && (data.message || data.detail)) || error.message || '网络错误'
    const err = new Error(Array.isArray(raw) ? JSON.stringify(raw) : raw)
    err.status = error?.response?.status
    return Promise.reject(err)
  }
)

export default {
  // 工人登录
  workerLogin(workerName, password) {
    return http.post('/worker/login', {
      worker_name: workerName,
      password
    })
  },

  // 获取指派给指定工人的工单列表
  listMyWorkOrders(workerId, status = '', page = 1, limit = 20) {
    return http.get('/work-orders', {
      params: {
        worker_id: workerId,
        status: status || undefined,
        page,
        limit
      }
    })
  },

  // 工单详情
  getWorkOrder(orderNo) {
    return http.get(`/work-order/${orderNo}`)
  },

  // 开始处理工单（PENDING -> processing）
  startWorkOrder(orderNo) {
    return http.post(`/work-order/${orderNo}/start`)
  },

  // 工人完成处理（processing -> worker_completed）
  workerCompleteWorkOrder(orderNo, workerId) {
    return http.post(`/work-order/${orderNo}/worker-complete`, { worker_id: workerId })
  }
}