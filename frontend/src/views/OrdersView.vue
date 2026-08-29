<template>
  <div>
    <h2>工单管理</h2>
    
    <el-card style="margin-bottom:16px">
      <el-form :inline="true">
        <el-form-item label="工单号"><el-input v-model="filters.order_no" placeholder="工单号" clearable /></el-form-item>
        <el-form-item label="报修类型"><el-input v-model="filters.sub_category" placeholder="如:管道窨井" clearable /></el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width:150px">
            <el-option label="待处理" value="PENDING" />
            <el-option label="处理中" value="processing" />
            <el-option label="工人完成处理" value="worker_completed" />
            <el-option label="已完成" value="completed" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词"><el-input v-model="filters.keyword" placeholder="搜索报修描述/地址" clearable /></el-form-item>
        <el-form-item>
          <el-button type="primary" @click="search">搜索</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card>
      <el-table :data="items" stripe v-loading="loading" @row-click="viewDetail" style="cursor:pointer">
        <el-table-column prop="order_no" label="工单号" width="220" />
        <el-table-column prop="sub_category" label="报修类型" width="120">
          <template #default="{row}"><el-tag size="small">{{ row.sub_category }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="problem" label="报修项目" width="160" show-overflow-tooltip />
        <el-table-column prop="user_input" label="报修概述" show-overflow-tooltip />
        <el-table-column prop="priority" label="优先级" width="80" />
        <el-table-column prop="property_company" label="物业公司" width="140" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{row}">
            <el-tag
              :type="row.status === 'completed' ? 'success' : row.status === 'processing' ? 'warning' : row.status === 'worker_completed' ? 'primary' : 'info'"
              size="small"
            >
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{row}">
            <el-button link type="primary" size="small" @click.stop="viewDetail(row)">详情</el-button>
            <el-button v-if="(row.status || '').toLowerCase() === 'pending'" link type="warning" size="small" @click.stop="start(row)">开始处理</el-button>
            <el-button v-if="row.status !== 'completed' && row.status !== 'worker_completed'" link type="success" size="small" @click.stop="complete(row)">完成</el-button>
            <el-button v-if="row.status === 'worker_completed'" link type="success" size="small" @click.stop="complete(row)">完成</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <div style="margin-top:16px;text-align:right">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="limit"
          :total="total"
          :page-sizes="[10,20,50,100]"
          layout="total,sizes,prev,pager,next"
          @size-change="search"
          @current-change="search"
        />
      </div>
    </el-card>
  </div>
</template>

<script>
import api from '../api'

export default {
  data() {
    return {
      items: [],
      total: 0,
      page: 1,
      limit: 20,
      loading: false,
      filters: {
        order_no: '',
        sub_category: '',
        keyword: '',
        status: ''
      }
    }
  },
  mounted() { this.search() },
  methods: {
    statusText(status) {
      const map = {
        'PENDING': '待处理',
        'processing': '处理中',
        'worker_completed': '工人完成处理',
        'completed': '已完成'
      }
      return map[status] || status
    },
    async search() {
      this.loading = true
      try {
        const data = await api.listWorkOrders({
          page: this.page,
          limit: this.limit,
          order_no: this.filters.order_no || undefined,
          sub_category: this.filters.sub_category || undefined,
          keyword: this.filters.keyword || undefined,
          status: this.filters.status || undefined,
        })
        this.items = data.items || []
        this.total = data.total || 0
      } catch (e) {
        this.$message.error('查询失败: ' + e.message)
      } finally {
        this.loading = false
      }
    },
    resetFilters() {
      this.filters = { order_no: '', sub_category: '', keyword: '', status: '' }
      this.page = 1
      this.search()
    },
    viewDetail(row) {
      this.$router.push(`/order/${row.order_no}`)
    },
    async start(row) {
      try {
        await this.$confirm('确认开始处理该工单？', '确认', { type: 'info' })
        await api.startWorkOrder(row.order_no)
        this.$message.success('工单已标记为处理中')
        this.search()
      } catch (e) {
        if (e !== 'cancel') this.$message.error(e.message || '操作失败')
      }
    },
    async complete(row) {
      try {
        await this.$confirm('确认标记该工单为已完成？', '确认', { type: 'warning' })
        await api.completeWorkOrder(row.order_no)
        this.$message.success('工单已标记为完成')
        this.search()
      } catch (e) {
        if (e !== 'cancel') this.$message.error(e.message || '操作失败')
      }
    }
  }
}
</script>