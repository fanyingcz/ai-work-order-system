<template>
  <div>
    <h2>反馈管理</h2>
    
    <el-tabs v-model="activeTab" @tab-change="loadData">
      <el-tab-pane label="待审核" name="pending" />
      <el-tab-pane label="全部记录" name="all" />
    </el-tabs>

    <el-table :data="items" stripe v-loading="loading">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="order_no" label="工单号" width="220" />
      <el-table-column prop="model_problem" label="模型判定" width="150" show-overflow-tooltip />
      <el-table-column prop="human_problem" label="人工修正" width="150" show-overflow-tooltip />
      <el-table-column prop="human_keyword" label="建议关键词" width="150" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{row}">
          <el-tag :type="row.status === 'approved' ? 'success' : row.status === 'rejected' ? 'danger' : 'warning'" size="small">
            {{ row.status === 'approved' ? '已通过' : row.status === 'rejected' ? '已驳回' : '待审核' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="提交时间" width="180" />
      <el-table-column label="操作" width="200" v-if="activeTab === 'pending'">
        <template #default="{row}">
          <el-button type="success" size="small" @click="approve(row)">通过</el-button>
          <el-button type="danger" size="small" @click="reject(row)">驳回</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div style="margin-top:16px;text-align:right" v-if="activeTab === 'all'">
      <el-pagination v-model:current-page="page" :page-size="limit" :total="total"
        layout="total,prev,pager,next" @current-change="loadData" />
    </div>
  </div>
</template>

<script>
import api from '../api'

export default {
  data() {
    return {
      activeTab: 'pending',
      items: [],
      loading: false,
      page: 1,
      limit: 20,
      total: 0
    }
  },
  mounted() { this.loadData() },
  methods: {
    async loadData() {
      this.loading = true
      try {
        if (this.activeTab === 'pending') {
          const data = await api.getPendingFeedbacks()
          this.items = data.items || []
          this.total = data.total || this.items.length
        } else {
          const data = await api.getAllFeedbacks({ page: this.page, limit: this.limit })
          this.items = data.items || []
          // API currently doesn't return total for /all, estimate
          this.total = data.items ? data.items.length * (this.page) : 0
        }
      } catch (e) {
        this.$message.error('加载失败: ' + e.message)
      } finally {
        this.loading = false
      }
    },
    async approve(row) {
      try {
        await this.$confirm('确认通过该反馈？通过后关键词将自动加入规则表。', '确认', { type: 'warning' })
        await api.approveFeedback(row.id)
        this.$message.success('已通过，关键词已同步到规则表')
        this.loadData()
      } catch (e) {
        if (e !== 'cancel') this.$message.error(e.message || '操作失败')
      }
    },
    async reject(row) {
      try {
        await this.$confirm('确认驳回该反馈？', '确认', { type: 'warning' })
        await api.rejectFeedback(row.id)
        this.$message.success('已驳回')
        this.loadData()
      } catch (e) {
        if (e !== 'cancel') this.$message.error(e.message || '操作失败')
      }
    }
  }
}
</script>