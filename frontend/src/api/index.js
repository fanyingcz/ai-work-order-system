import axios from 'axios'

// API请求统一配置
const http = axios.create({
  baseURL: '/api/v1',
  timeout: 120000,
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
    return Promise.reject(error)
  }
)

// ============================================================
// API 方法
// ============================================================

export default {
  // 工单流程
  submitWorkOrder(userId, userInput, reporterName, reporterPhone) {
    const body = { user_id: userId, user_input: userInput }
    if (reporterName) body.reporter_name = reporterName
    if (reporterPhone) body.reporter_phone = reporterPhone
    return http.post('/work-order/submit', body)
  },
  converse(userId, text, reporterName, reporterPhone) {
    const body = { user_id: userId, text }
    if (reporterName) body.reporter_name = reporterName
    if (reporterPhone) body.reporter_phone = reporterPhone
    return http.post('/work-order/converse', body)
  },
  getWorkOrder(orderNo) {
    return http.get(`/work-order/${orderNo}`)
  },
  listWorkOrders(params) {
    return http.get('/work-orders', { params })
  },
  searchWorkOrders(params) {
    return http.post('/work-orders/search', params)
  },
  startWorkOrder(orderNo) {
    return http.post(`/work-order/${orderNo}/start`)
  },
  completeWorkOrder(orderNo) {
    return http.post(`/work-order/${orderNo}/complete`)
  },
  updateWorkOrder(orderNo, data) {
    return http.put(`/work-order/${orderNo}`, data)
  },

  // 会话管理
  getSession(userId) {
    return http.get(`/session/${userId}`)
  },
  getSessionHistory(userId) {
    return http.get(`/session/${userId}/history`)
  },
  cancelSession(userId) {
    return http.delete(`/session/${userId}`)
  },

  // 数据查询
  getSubcategories() {
    return http.get('/subcategories')
  },
  getCategories() {
    return http.get('/categories')
  },
  getKeywords(subCategory) {
    return http.get('/keywords', { params: subCategory ? { sub_category: subCategory } : {} })
  },
  checkRulesCompleteness() {
    return http.get('/rules/completeness')
  },

  // 反馈管理
  submitFeedback(orderNo, humanProblem, humanKeyword) {
    return http.post('/feedback', {
      order_no: orderNo,
      human_problem: humanProblem,
      human_keyword: humanKeyword
    })
  },
  getPendingFeedbacks() {
    return http.get('/feedback/pending')
  },
  getAllFeedbacks(params = {}) {
    return http.get('/feedback/all', { params })
  },
  approveFeedback(id) {
    return http.post(`/feedback/${id}/approve`)
  },
  rejectFeedback(id) {
    return http.post(`/feedback/${id}/reject`)
  },

  // 地址映射
  listAddressMappings() {
    return http.get('/address-mappings')
  },
  addAddressMapping(data) {
    return http.post('/address-mappings', data)
  },
  updateAddressMapping(id, data) {
    return http.put(`/address-mappings/${id}`, data)
  },
  deleteAddressMapping(id) {
    return http.delete(`/address-mappings/${id}`)
  },

  // 系统管理
  getWorkers(company) {
    return http.get('/workers', { params: company ? { company } : {} })
  },
  getStats() {
    return http.get('/stats')
  },
  healthCheck() {
    return http.get('/health')
  },

  // 模型测试
  runTest(testCount = 200, workers = 3, sequential = false) {
    return http.post('/test/run', { test_count: testCount, workers, sequential })
  },
  getTestStatus(taskId) {
    return http.get(`/test/${taskId}/status`)
  },
  getTestTasks() {
    return http.get('/test/tasks')
  },
  getTestLogs() {
    return http.get('/test/logs')
  },
  getTestLogContent(filename) {
    return http.get(`/test/logs/${filename}`)
  },

  // 数据库管理 - 子类别
  adminListSubcategories() {
    return http.get('/admin/subcategories')
  },
  adminAddSubcategory(data) {
    return http.post('/admin/subcategories', data)
  },
  adminUpdateSubcategory(id, data) {
    return http.put(`/admin/subcategories/${id}`, data)
  },
  adminDeleteSubcategory(id) {
    return http.delete(`/admin/subcategories/${id}`)
  },

  // 数据库管理 - 分类规则
  adminListCategories() {
    return http.get('/admin/categories')
  },
  adminAddCategory(data) {
    return http.post('/admin/categories', data)
  },
  adminUpdateCategory(id, data) {
    return http.put(`/admin/categories/${id}`, data)
  },
  adminDeleteCategory(id) {
    return http.delete(`/admin/categories/${id}`)
  },

  // 数据库管理 - 关键词
  adminListKeywords() {
    return http.get('/admin/keywords')
  },
  adminAddKeyword(data) {
    return http.post('/admin/keywords', data)
  },
  adminUpdateKeyword(id, data) {
    return http.put(`/admin/keywords/${id}`, data)
  },
  adminDeleteKeyword(id) {
    return http.delete(`/admin/keywords/${id}`)
  },

  // 数据库管理 - 位置
  adminListLocations() {
    return http.get('/admin/locations')
  },
  adminAddLocation(data) {
    return http.post('/admin/locations', data)
  },
  adminUpdateLocation(id, data) {
    return http.put(`/admin/locations/${id}`, data)
  },
  adminDeleteLocation(id) {
    return http.delete(`/admin/locations/${id}`)
  },

  // 提示词管理
  getPrompts() {
    return http.get('/admin/prompts')
  },
  reloadPrompts() {
    return http.post('/admin/prompts/reload')
  },
  updatePromptField(path, value) {
    return http.put('/admin/prompts/field', { path, value })
  },
  addStep2Rule(ruleText) {
    return http.post('/admin/prompts/step2/rule', { rule_text: ruleText })
  },
  updateStep2Rule(index, ruleText) {
    return http.put(`/admin/prompts/step2/rule/${index}`, { rule_text: ruleText })
  },
  deleteStep2Rule(index) {
    return http.delete(`/admin/prompts/step2/rule/${index}`)
  },
  updateStep1Task(taskKey, value) {
    return http.put(`/admin/prompts/step1/task/${taskKey}`, { value })
  },

  // 数据库管理 - 人员管理
  adminListWorkers() {
    return http.get('/admin/workers')
  },
  adminAddWorker(data) {
    return http.post('/admin/workers', data)
  },
  adminUpdateWorker(id, data) {
    return http.put(`/admin/workers/${id}`, data)
  },
  adminDeleteWorker(id) {
    return http.delete(`/admin/workers/${id}`)
  }
}
