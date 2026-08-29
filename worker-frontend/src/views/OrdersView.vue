<template>
  <div class="orders-page">
    <!-- 顶部导航 -->
    <header class="header">
      <div class="header-left">
        <span class="logo">🔧</span>
        <h1>维修工人工作台</h1>
      </div>
      <div class="header-right">
        <template v-if="worker">
          <el-avatar :size="32" style="background:#409EFF">{{ worker.name.charAt(0) }}</el-avatar>
          <div class="worker-info">
            <div class="worker-name">{{ worker.name }}</div>
            <div class="worker-id">ID: {{ worker.id }}</div>
          </div>
          <el-button text @click="handleLogout">退出登录</el-button>
        </template>
      </div>
    </header>

    <main class="content">
      <!-- 状态统计 -->
      <div class="stats-row">
        <el-card class="stat-card" :class="{ active: statusFilter === '' }" @click="setStatus('')">
          <div class="stat-value">{{ allCount }}</div>
          <div class="stat-label">全部工单</div>
        </el-card>
        <el-card class="stat-card" :class="{ active: statusFilter === 'PENDING' }" @click="setStatus('PENDING')">
          <div class="stat-value">{{ pendingCount }}</div>
          <div class="stat-label">待处理</div>
        </el-card>
        <el-card class="stat-card" :class="{ active: statusFilter === 'processing' }" @click="setStatus('processing')">
          <div class="stat-value">{{ processingCount }}</div>
          <div class="stat-label">处理中</div>
        </el-card>
        <el-card class="stat-card" :class="{ active: statusFilter === 'worker_completed' }" @click="setStatus('worker_completed')">
          <div class="stat-value">{{ workerCompletedCount }}</div>
          <div class="stat-label">工人完成</div>
        </el-card>
        <el-card class="stat-card" :class="{ active: statusFilter === 'completed' }" @click="setStatus('completed')">
          <div class="stat-value">{{ completedCount }}</div>
          <div class="stat-label">已完成</div>
        </el-card>
      </div>

      <!-- 工单列表 -->
      <el-card class="orders-card" v-loading="loading">
        <template #header>
          <div class="card-header">
            <span><strong>我的工单列表</strong></span>
            <span class="header-total">共 {{ total }} 条</span>
          </div>
        </template>

        <el-empty v-if="!items.length && !loading" description="暂无工单" />

        <el-table v-else :data="items" stripe style="width: 100%">
          <el-table-column prop="order_no" label="工单号" width="200" />
          <el-table-column prop="sub_category" label="报修类型" width="120">
            <template #default="{row}">
              <el-tag size="small">{{ row.sub_category }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="problem" label="报修项目" width="150" show-overflow-tooltip />
          <el-table-column prop="user_input" label="报修概述" show-overflow-tooltip />
          <el-table-column prop="address" label="报修地址" width="200" show-overflow-tooltip />
          <el-table-column prop="priority" label="优先级" width="80">
            <template #default="{row}">
              <el-tag :type="row.priority === '高' ? 'danger' : row.priority === '中' ? 'warning' : 'info'" size="small">
                {{ row.priority }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="110">
            <template #default="{row}">
              <el-tag
                :type="statusType(row.status)"
                size="small"
              >
                {{ statusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="accept_time" label="受理时间" width="170" />
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{row}">
              <el-button
                v-if="row.status === 'PENDING'"
                type="warning"
                size="small"
                @click="handleStart(row)"
              >
                开始处理
              </el-button>
              <el-button
                v-if="row.status === 'processing'"
                type="success"
                size="small"
                @click="handleWorkerComplete(row)"
              >
                完成处理
              </el-button>
              <el-button
                v-if="row.status === 'worker_completed'"
                type="info"
                size="small"
                disabled
              >
                已提交
              </el-button>
              <el-button
                v-if="row.status === 'completed'"
                type="success"
                size="small"
                disabled
              >
                已完成
              </el-button>
              <el-button link type="primary" size="small" @click="handleDetail(row)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div style="margin-top:16px;text-align:right" v-if="total > 0">
          <el-pagination
            v-model:current-page="page"
            v-model:page-size="limit"
            :total="total"
            :page-sizes="[10, 20, 50]"
            layout="total,sizes,prev,pager,next"
            @size-change="loadOrders"
            @current-change="loadOrders"
          />
        </div>
      </el-card>

      <!-- 工单详情弹窗 -->
      <el-dialog v-model="detailVisible" title="工单详情" width="650px">
        <el-descriptions :column="2" border v-if="currentOrder">
          <el-descriptions-item label="工单号">{{ currentOrder.order_no }}</el-descriptions-item>
          <el-descriptions-item label="受理时间">{{ currentOrder.accept_time }}</el-descriptions-item>
          <el-descriptions-item label="报修类型">{{ currentOrder.sub_category }}</el-descriptions-item>
          <el-descriptions-item label="报修项目">{{ currentOrder.problem }}</el-descriptions-item>
          <el-descriptions-item label="优先级">{{ currentOrder.priority }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusType(currentOrder.status)" size="small">{{ statusText(currentOrder.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="物业公司">{{ currentOrder.property_company }}</el-descriptions-item>
          <el-descriptions-item label="维修单位">{{ currentOrder.maintenance_unit }}</el-descriptions-item>
          <el-descriptions-item label="报修人">{{ currentOrder.reporter_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="联系电话">{{ currentOrder.reporter_phone || '-' }}</el-descriptions-item>
          <el-descriptions-item label="报修概述" :span="2">{{ currentOrder.user_input }}</el-descriptions-item>
          <el-descriptions-item label="报修地址" :span="2">{{ currentOrder.address || '-' }}</el-descriptions-item>
        </el-descriptions>
        <template #footer>
          <el-button @click="detailVisible = false">关闭</el-button>
          <el-button
            v-if="currentOrder && currentOrder.status === 'PENDING'"
            type="warning"
            @click="handleStart(currentOrder)"
          >开始处理</el-button>
          <el-button
            v-if="currentOrder && currentOrder.status === 'processing'"
            type="success"
            @click="handleWorkerComplete(currentOrder)"
          >完成处理</el-button>
        </template>
      </el-dialog>
    </main>
  </div>
</template>

<script>
import api from '../api'

export default {
  name: 'OrdersView',
  data() {
    return {
      worker: null,
      items: [],
      total: 0,
      page: 1,
      limit: 20,
      loading: false,
      statusFilter: '',
      detailVisible: false,
      currentOrder: null,
      // 各状态统计（通过独立请求获取）
      pendingTotal: 0,
      processingTotal: 0,
      workerCompletedTotal: 0,
      completedTotal: 0
    }
  },
  computed: {
    allCount() {
      return this.pendingTotal + this.processingTotal + this.workerCompletedTotal + this.completedTotal
    },
    pendingCount() {
      return this.pendingTotal
    },
    processingCount() {
      return this.processingTotal
    },
    workerCompletedCount() {
      return this.workerCompletedTotal
    },
    completedCount() {
      return this.completedTotal
    }
  },
  async mounted() {
    // 从 localStorage 恢复工人信息
    const workerInfo = localStorage.getItem('worker_info')
    if (!workerInfo) {
      this.$router.push('/')
      return
    }
    this.worker = JSON.parse(workerInfo)
    await this.loadAllStats()
    await this.loadOrders()
  },
  methods: {
    async loadAllStats() {
      // 统计各状态的工单数
      try {
        const statuses = ['PENDING', 'processing', 'worker_completed', 'completed']
        const results = await Promise.all(
          statuses.map(s => api.listMyWorkOrders(this.worker.id, s, 1, 1))
        )
        this.pendingTotal = results[0] ? results[0].total : 0
        this.processingTotal = results[1] ? results[1].total : 0
        this.workerCompletedTotal = results[2] ? results[2].total : 0
        this.completedTotal = results[3] ? results[3].total : 0
      } catch (e) {
        // 忽略统计失败
      }
    },
    setStatus(status) {
      this.statusFilter = status
      this.page = 1
      this.loadOrders()
    },
    async loadOrders() {
      this.loading = true
      try {
        const data = await api.listMyWorkOrders(this.worker.id, this.statusFilter, this.page, this.limit)
        this.items = data.items || []
        this.total = data.total || 0

        // 更新统计
        await this.loadAllStats()
      } catch (e) {
        this.$message.error('加载工单失败: ' + e.message)
      } finally {
        this.loading = false
      }
    },
    async handleStart(row) {
      try {
        await this.$confirm(`确认开始处理工单 ${row.order_no}？`, '开始处理', { type: 'warning' })
        await api.startWorkOrder(row.order_no)
        this.$message.success('工单已开始处理，状态变为处理中')
        this.loadOrders()
        if (this.detailVisible) {
          this.detailVisible = false
        }
      } catch (e) {
        if (e !== 'cancel') this.$message.error(e.message || '操作失败')
      }
    },
    async handleWorkerComplete(row) {
      try {
        await this.$confirm(`确认已完成工单 ${row.order_no} 的处理？`, '完成处理', { type: 'warning' })
        await api.workerCompleteWorkOrder(row.order_no, this.worker.id)
        this.$message.success('工单已完成，等待管理员确认')
        this.loadOrders()
        if (this.detailVisible) {
          this.detailVisible = false
        }
      } catch (e) {
        if (e !== 'cancel') this.$message.error(e.message || '操作失败')
      }
    },
    handleDetail(row) {
      this.currentOrder = row
      this.detailVisible = true
    },
    statusText(status) {
      const map = {
        'PENDING': '待处理',
        'processing': '处理中',
        'worker_completed': '工人完成',
        'completed': '已完成'
      }
      return map[status] || status
    },
    statusType(status) {
      const map = {
        'PENDING': 'info',
        'processing': 'warning',
        'worker_completed': 'success',
        'completed': 'success'
      }
      return map[status] || 'info'
    },
    handleLogout() {
      localStorage.removeItem('worker_token')
      localStorage.removeItem('worker_info')
      this.$router.push('/')
      this.$message.success('已退出登录')
    }
  }
}
</script>

<style scoped>
.orders-page {
  min-height: 100vh;
}

.header {
  background: #409EFF;
  color: white;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-left h1 {
  font-size: 18px;
  margin: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.worker-info {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.worker-name {
  font-size: 14px;
  font-weight: 600;
}

.worker-id {
  font-size: 12px;
  opacity: 0.8;
}

.header-right .el-button {
  color: white;
}

.content {
  padding: 20px 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  cursor: pointer;
  text-align: center;
  transition: all 0.2s;
  border: 2px solid transparent;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.stat-card.active {
  border-color: #409EFF;
  background: #ecf5ff;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}

.orders-card {
  border-radius: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-total {
  color: #909399;
  font-size: 13px;
}

@media (max-width: 768px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>