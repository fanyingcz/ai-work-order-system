<template>
  <div class="page">
    <div class="page-head">
      <h2 class="page-title">工单管理</h2>
      <p class="page-desc">共 {{ total }} 条工单，点击任意行查看详情</p>
    </div>

    <!-- 筛选 -->
    <div class="card card--pad filter">
      <div class="filter__grid">
        <el-input v-model="filters.order_no" placeholder="工单号" clearable @keyup.enter="doSearch" />
        <el-input v-model="filters.sub_category" placeholder="报修类型，如 管道窨井" clearable @keyup.enter="doSearch" />
        <el-select v-model="filters.status" placeholder="全部状态" clearable>
          <el-option label="待处理" value="PENDING" />
          <el-option label="处理中" value="processing" />
          <el-option label="工人完成处理" value="worker_completed" />
          <el-option label="已完成" value="completed" />
        </el-select>
        <el-input v-model="filters.keyword" placeholder="搜索报修描述 / 地址" clearable @keyup.enter="doSearch" />
      </div>
      <div class="filter__actions">
        <el-button type="primary" @click="doSearch">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>
    </div>

    <!-- 列表 -->
    <div class="card">
      <div class="table-wrap">
        <el-table
          :data="items"
          v-loading="loading"
          row-class-name="row-link"
          @row-click="viewDetail"
        >
          <el-table-column prop="order_no" label="工单号" min-width="190">
            <template #default="{ row }">
              <span class="mono">{{ row.order_no }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="sub_category" label="类型" width="110">
            <template #default="{ row }">
              <span class="chip chip--brand">{{ row.sub_category }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="problem" label="报修项目" min-width="140" show-overflow-tooltip />
          <el-table-column prop="user_input" label="报修概述" min-width="200" show-overflow-tooltip />
          <el-table-column prop="priority" label="优先级" width="90" align="center">
            <template #default="{ row }">
              <span class="chip" :class="row.priority === '高' ? 'chip--danger' : row.priority === '中' ? 'chip--warn' : 'chip--muted'">
                {{ row.priority || '-' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="property_company" label="物业公司" min-width="140" show-overflow-tooltip />
          <el-table-column prop="status" label="状态" width="120" align="center">
            <template #default="{ row }">
              <span class="chip" :class="statusClass(row.status)">{{ statusText(row.status) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right" align="right">
            <template #default="{ row }">
              <div class="ops">
                <el-button v-if="isPending(row)" link type="warning" size="small" @click.stop="start(row)">开始</el-button>
                <el-button v-if="canComplete(row)" link type="success" size="small" @click.stop="complete(row)">完成</el-button>
                <el-button link type="primary" size="small" @click.stop="viewDetail(row)">详情</el-button>
              </div>
            </template>
          </el-table-column>

          <template #empty>
            <div class="empty">
              <div class="empty__icon"><el-icon><Tickets /></el-icon></div>
              <div class="empty__text">没有符合条件的工单</div>
            </div>
          </template>
        </el-table>
      </div>

      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="limit"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @size-change="doSearch"
          @current-change="load"
        />
      </div>
    </div>
  </div>
</template>

<script>
import api from '../api'

export default {
  name: 'OrdersView',
  data() {
    return {
      items: [],
      total: 0,
      page: 1,
      limit: 20,
      loading: false,
      actingNo: '',
      filters: { order_no: '', sub_category: '', keyword: '', status: '' }
    }
  },
  mounted() {
    // 支持从数据看板带筛选条件跳转过来，例如 /orders?status=PENDING
    const q = this.$route.query
    if (q.status) this.filters.status = String(q.status)
    if (q.sub_category) this.filters.sub_category = String(q.sub_category)
    if (q.keyword) this.filters.keyword = String(q.keyword)
    if (q.order_no) this.filters.order_no = String(q.order_no)
    this.load()
  },
  methods: {
    statusText(status) {
      const map = {
        PENDING: '待处理',
        processing: '处理中',
        worker_completed: '待确认',
        completed: '已完成'
      }
      return map[status] || status || '-'
    },
    statusClass(status) {
      const map = {
        PENDING: 'chip--muted',
        processing: 'chip--info',
        worker_completed: 'chip--warn',
        completed: 'chip--ok'
      }
      return map[status] || 'chip--muted'
    },
    isPending(row) {
      return String(row.status || '').toLowerCase() === 'pending'
    },
    // 未终态的工单都可以标记完成（worker_completed 需管理员确认）
    canComplete(row) {
      return row.status !== 'completed'
    },
    doSearch() {
      this.page = 1
      this.load()
    },
    resetFilters() {
      this.filters = { order_no: '', sub_category: '', keyword: '', status: '' }
      this.doSearch()
    },
    async load() {
      this.loading = true
      try {
        const data = await api.listWorkOrders({
          page: this.page,
          limit: this.limit,
          order_no: this.filters.order_no || undefined,
          sub_category: this.filters.sub_category || undefined,
          keyword: this.filters.keyword || undefined,
          status: this.filters.status || undefined
        })
        this.items = data.items || []
        this.total = data.total || 0
      } catch (e) {
        this.$message.error('查询失败: ' + e.message)
      } finally {
        this.loading = false
      }
    },
    viewDetail(row) {
      this.$router.push(`/order/${row.order_no}`)
    },
    async start(row) {
      if (this.actingNo) return
      try {
        await this.$confirm('确认开始处理该工单？', '确认', { type: 'info' })
      } catch (e) {
        return
      }
      this.actingNo = row.order_no
      try {
        await api.startWorkOrder(row.order_no)
        this.$message.success('工单已标记为处理中')
        await this.load()
      } catch (e) {
        this.$message.error(e.message || '操作失败')
      } finally {
        this.actingNo = ''
      }
    },
    async complete(row) {
      if (this.actingNo) return
      const isConfirm = String(row.status || '').toLowerCase() === 'worker_completed'
      const tip = isConfirm
        ? '工人已提交完工，确认后该工单将标记为已完成。'
        : '确认标记该工单为已完成？'
      try {
        await this.$confirm(tip, '确认', { type: 'warning' })
      } catch (e) {
        return
      }
      this.actingNo = row.order_no
      try {
        await api.completeWorkOrder(row.order_no)
        this.$message.success('工单已标记为完成')
        await this.load()
      } catch (e) {
        this.$message.error(e.message || '操作失败')
      } finally {
        this.actingNo = ''
      }
    }
  }
}
</script>

<style scoped>
.filter {
  display: flex;
  align-items: flex-end;
  gap: 14px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.filter__grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(160px, 1fr));
  gap: 10px;
  flex: 1 1 420px;
}
.filter__actions { display: flex; gap: 8px; }

.table-wrap { padding: 4px 4px 0; }
.mono {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 12.5px;
  color: var(--ink-700);
}
.ops { display: flex; justify-content: flex-end; gap: 2px; }

.pager {
  display: flex;
  justify-content: flex-end;
  padding: 14px 16px;
  border-top: 1px solid var(--line-soft);
}

:deep(.row-link) { cursor: pointer; }

@media (max-width: 900px) {
  .filter__grid { grid-template-columns: 1fr 1fr; }
}
</style>
