<template>
  <div class="page">
    <div class="page-head">
      <h2 class="page-title">反馈管理</h2>
      <p class="page-desc">审核人工修正建议，通过后关键词自动同步到规则表</p>
    </div>

    <div class="card">
      <div class="card-head">
        <div class="tabs">
          <button
            v-for="t in tabs"
            :key="t.value"
            class="tab"
            :class="{ 'is-active': activeTab === t.value }"
            @click="switchTab(t.value)"
          >
            {{ t.label }}
            <span class="tab__badge">{{ t.value === 'pending' ? pendingCount : total }}</span>
          </button>
        </div>
        <el-button :loading="loading" size="small" @click="loadData">刷新</el-button>
      </div>

      <el-table :data="items" v-loading="loading">
        <el-table-column prop="id" label="ID" width="64" />
        <el-table-column prop="order_no" label="工单号" min-width="180">
          <template #default="{ row }">
            <span class="mono">{{ row.order_no }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="model_problem" label="模型判定" min-width="140" show-overflow-tooltip />
        <el-table-column prop="human_problem" label="人工修正" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="fix">{{ row.human_problem || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="human_keyword" label="建议关键词" min-width="140" />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <span class="chip" :class="statusClass(row.status)">{{ statusText(row.status) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="提交时间" width="170" />
        <el-table-column v-if="activeTab === 'pending'" label="操作" width="150" fixed="right" align="right">
          <template #default="{ row }">
            <div class="ops">
              <el-button link type="success" size="small" @click="approve(row)">通过</el-button>
              <el-button link type="danger" size="small" @click="reject(row)">驳回</el-button>
            </div>
          </template>
        </el-table-column>

        <template #empty>
          <div class="empty">
            <div class="empty__icon"><el-icon><ChatDotRound /></el-icon></div>
            <div class="empty__text">{{ activeTab === 'pending' ? '没有待审核的反馈' : '暂无反馈记录' }}</div>
          </div>
        </template>
      </el-table>

      <!-- 后端现已返回真实 total，分页与总数直接用 total，不再靠「是否填满一页」猜 -->
      <div v-if="activeTab === 'all' && total > limit" class="pager">
        <el-pagination
          v-model:current-page="page"
          :page-size="limit"
          :total="total"
          layout="prev, pager, next, total"
          @current-change="loadData"
        />
      </div>
    </div>
  </div>
</template>

<script>
import api from '../api'

export default {
  name: 'FeedbackView',
  data() {
    return {
      activeTab: 'pending',
      items: [],
      loading: false,
      page: 1,
      limit: 20,
      total: 0,
      pendingCount: 0,
      actingId: null,
      actingType: '',
      tabs: [
        { label: '待审核', value: 'pending' },
        { label: '全部记录', value: 'all' }
      ]
    }
  },
  mounted() { this.loadData() },
  methods: {
    switchTab(value) {
      if (this.activeTab === value) return
      this.activeTab = value
      this.page = 1
      this.loadData()
    },
    // 两个页签的徽标同时可见，所以各自维护自己的计数，不能共用一个 total
    async refreshCounts() {
      try {
        if (this.activeTab === 'pending') {
          const d = await api.getAllFeedbacks({ page: 1, limit: 1 })
          if (typeof d.total === 'number') this.total = d.total
        } else {
          const d = await api.getPendingFeedbacks()
          this.pendingCount = typeof d.total === 'number' ? d.total : (d.items || []).length
        }
      } catch (e) { /* 仅用于徽标，失败不影响主列表 */ }
    },
    statusText(status) {
      if (status === 'approved') return '已通过'
      if (status === 'rejected') return '已驳回'
      return '待审核'
    },
    statusClass(status) {
      if (status === 'approved') return 'chip--ok'
      if (status === 'rejected') return 'chip--danger'
      return 'chip--warn'
    },
    async loadData() {
      if (this.loading) return
      this.loading = true
      try {
        if (this.activeTab === 'pending') {
          const data = await api.getPendingFeedbacks()
          this.items = data.items || []
          this.pendingCount = typeof data.total === 'number' ? data.total : this.items.length
        } else {
          const data = await api.getAllFeedbacks({ page: this.page, limit: this.limit })
          this.items = data.items || []
          // 后端现已返回 total；保底分支只为兼容旧后端
          this.total = typeof data.total === 'number'
            ? data.total
            : (this.page - 1) * this.limit + this.items.length
        }
        await this.refreshCounts()
      } catch (e) {
        this.$message.error('加载失败: ' + e.message)
      } finally {
        this.loading = false
      }
    },
    async approve(row) {
      if (this.actingId !== null) return
      try {
        await this.$confirm('确认通过该反馈？通过后关键词将自动加入规则表。', '确认', { type: 'warning' })
      } catch (e) {
        return
      }
      this.actingId = row.id
      this.actingType = 'approve'
      try {
        await api.approveFeedback(row.id)
        this.$message.success('已通过，关键词已同步到规则表')
        await this.loadData()
      } catch (e) {
        this.$message.error(e.message || '操作失败')
      } finally {
        this.actingId = null
        this.actingType = ''
      }
    },
    async reject(row) {
      if (this.actingId !== null) return
      try {
        await this.$confirm('确认驳回该反馈？', '确认', { type: 'warning' })
      } catch (e) {
        return
      }
      this.actingId = row.id
      this.actingType = 'reject'
      try {
        await api.rejectFeedback(row.id)
        this.$message.success('已驳回')
        await this.loadData()
      } catch (e) {
        this.$message.error(e.message || '操作失败')
      } finally {
        this.actingId = null
        this.actingType = ''
      }
    }
  }
}
</script>

<style scoped>
.tabs {
  display: inline-flex;
  gap: 4px;
  padding: 3px;
  border-radius: 10px;
  background: #f1f4f9;
}
.tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 14px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--ink-500);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.18s var(--ease);
}
.tab:hover { color: var(--ink-800); }
.tab.is-active {
  background: #fff;
  color: var(--brand);
  font-weight: 600;
  box-shadow: var(--shadow-sm);
}
.tab__badge {
  min-width: 18px;
  padding: 0 5px;
  border-radius: 99px;
  background: rgba(100, 116, 139, 0.12);
  color: inherit;
  font-size: 11px;
  line-height: 16px;
  text-align: center;
}

.mono { font-family: ui-monospace, Consolas, monospace; font-size: 12.5px; color: var(--ink-700); }
.fix { color: var(--brand); font-weight: 500; }
.ops { display: flex; justify-content: flex-end; gap: 2px; }
.pager { display: flex; justify-content: flex-end; padding: 14px 16px; border-top: 1px solid var(--line-soft); }
</style>
