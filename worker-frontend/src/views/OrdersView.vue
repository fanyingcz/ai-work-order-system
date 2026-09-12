<template>
  <div class="orders">
    <header class="topbar">
      <div class="topbar__inner">
        <div class="topbar__brand">
          <span class="topbar__logo">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
            </svg>
          </span>
          <span>维修工作台</span>
        </div>

        <div v-if="worker" class="topbar__user">
          <el-avatar :size="30" class="topbar__avatar">{{ (worker.name || '?').charAt(0) }}</el-avatar>
          <div class="topbar__meta">
            <span class="topbar__name">{{ worker.name }}</span>
            <span class="topbar__id">ID {{ worker.id }}</span>
          </div>
          <button class="topbar__logout" @click="handleLogout">退出</button>
        </div>
      </div>
    </header>

    <main class="content">
      <!-- 状态筛选 -->
      <div class="filters">
        <button
          v-for="f in filterList"
          :key="f.value"
          class="filter"
          :class="{ 'is-active': statusFilter === f.value }"
          @click="setStatus(f.value)"
        >
          <span class="filter__num">{{ f.count }}</span>
          <span class="filter__label">{{ f.label }}</span>
        </button>
      </div>

      <!-- 工单卡片 -->
      <div v-loading="loading" class="list">
        <article
          v-for="(row, i) in items"
          :key="row.order_no"
          class="order card anim-fade-up"
          :style="{ animationDelay: Math.min(i, 8) * 45 + 'ms' }"
          @click="handleDetail(row)"
        >
          <div class="order__top">
            <span class="mono order__no">{{ row.order_no }}</span>
            <span class="chip" :class="statusClass(row.status)">{{ statusText(row.status) }}</span>
          </div>

          <h3 class="order__title">{{ row.problem || row.sub_category || '报修工单' }}</h3>

          <div class="order__tags">
            <span class="chip chip--brand">{{ row.sub_category }}</span>
            <span class="chip" :class="priorityClass(row.priority)">{{ row.priority || '常规' }}</span>
          </div>

          <p class="order__desc">{{ row.user_input || '—' }}</p>

          <div class="order__meta">
            <span class="order__addr"><el-icon class="order__addr-icon"><Location /></el-icon>{{ row.address || '地址未填写' }}</span>
            <span class="order__time">{{ row.accept_time }}</span>
          </div>

          <div class="order__actions" @click.stop>
            <el-button
              v-if="statusKey(row) === 'pending'"
              type="warning"
              size="small"
              :loading="actingNo === row.order_no"
              :disabled="!!actingNo"
              @click="handleStart(row)"
            >开始处理</el-button>
            <el-button
              v-else-if="statusKey(row) === 'processing'"
              type="success"
              size="small"
              :loading="actingNo === row.order_no"
              :disabled="!!actingNo"
              @click="handleWorkerComplete(row)"
            >完成处理</el-button>
            <span v-else class="order__done">
              {{ statusKey(row) === 'worker_completed' ? '已提交，等待确认' : '已完成' }}
            </span>
            <el-button size="small" plain @click="handleDetail(row)">详情</el-button>
          </div>
        </article>

        <div v-if="!items.length && !loading" class="empty">
          <div class="empty__icon"><el-icon><Tools /></el-icon></div>
          <div class="empty__text">{{ statusFilter ? '该状态下暂无工单' : '当前没有指派给您的工单' }}</div>
        </div>
      </div>

      <div v-if="total > 0" class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="limit"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, prev, pager, next"
          @size-change="loadOrders"
          @current-change="loadOrders"
        />
      </div>
    </main>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="工单详情" width="620px">
      <div v-if="currentOrder" class="detail">
        <div class="detail__top">
          <span class="mono">{{ currentOrder.order_no }}</span>
          <span class="chip" :class="statusClass(currentOrder.status)">{{ statusText(currentOrder.status) }}</span>
        </div>
        <div class="detail__grid">
          <div class="kv"><span>受理时间</span><b>{{ currentOrder.accept_time || '-' }}</b></div>
          <div class="kv"><span>报修类型</span><b>{{ currentOrder.sub_category || '-' }}</b></div>
          <div class="kv"><span>报修项目</span><b>{{ currentOrder.problem || '-' }}</b></div>
          <div class="kv">
            <span>优先级</span>
            <b><span class="chip" :class="priorityClass(currentOrder.priority)">{{ currentOrder.priority || '常规' }}</span></b>
          </div>
          <div class="kv"><span>物业公司</span><b>{{ currentOrder.property_company || '-' }}</b></div>
          <div class="kv"><span>维修单位</span><b>{{ currentOrder.maintenance_unit || '-' }}</b></div>
          <div class="kv"><span>报修人</span><b>{{ currentOrder.reporter_name || '-' }}</b></div>
          <div class="kv"><span>联系电话</span>
            <b>
              <a v-if="currentOrder.reporter_phone" :href="`tel:${currentOrder.reporter_phone}`">{{ currentOrder.reporter_phone }}</a>
              <span v-else>-</span>
            </b>
          </div>
          <div class="kv kv--wide"><span>报修概述</span><b>{{ currentOrder.user_input || '-' }}</b></div>
          <div class="kv kv--wide"><span>报修地址</span><b>{{ currentOrder.address || '-' }}</b></div>
        </div>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button
          v-if="currentOrder && statusKey(currentOrder) === 'pending'"
          type="warning"
          :loading="actingNo === currentOrder.order_no"
          :disabled="!!actingNo"
          @click="handleStart(currentOrder)"
        >开始处理</el-button>
        <el-button
          v-if="currentOrder && statusKey(currentOrder) === 'processing'"
          type="success"
          :loading="actingNo === currentOrder.order_no"
          :disabled="!!actingNo"
          @click="handleWorkerComplete(currentOrder)"
        >完成处理</el-button>
      </template>
    </el-dialog>
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
      actingNo: '',
      statusFilter: '',
      detailVisible: false,
      currentOrder: null,
      stats: { PENDING: 0, processing: 0, worker_completed: 0, completed: 0 }
    }
  },
  computed: {
    filterList() {
      const s = this.stats
      return [
        { label: '全部', value: '', count: s.PENDING + s.processing + s.worker_completed + s.completed },
        { label: '待处理', value: 'PENDING', count: s.PENDING },
        { label: '处理中', value: 'processing', count: s.processing },
        { label: '待确认', value: 'worker_completed', count: s.worker_completed },
        { label: '已完成', value: 'completed', count: s.completed }
      ]
    }
  },
  async mounted() {
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
    // 用单次 limit=1 请求拿各状态总数，避免每次都翻页统计
    async loadAllStats() {
      try {
        const statuses = ['PENDING', 'processing', 'worker_completed', 'completed']
        const results = await Promise.all(
          statuses.map(s => api.listMyWorkOrders(this.worker.id, s, 1, 1))
        )
        statuses.forEach((s, i) => {
          this.stats[s] = results[i] ? (results[i].total || 0) : 0
        })
      } catch (e) { /* 统计失败不影响列表 */ }
    },
    setStatus(status) {
      if (this.statusFilter === status) return
      this.statusFilter = status
      this.page = 1
      this.loadOrders()
    },
    async loadOrders() {
      if (this.loading) return
      this.loading = true
      try {
        const data = await api.listMyWorkOrders(this.worker.id, this.statusFilter, this.page, this.limit)
        this.items = data.items || []
        this.total = data.total || 0
      } catch (e) {
        this.$message.error('加载工单失败: ' + e.message)
      } finally {
        this.loading = false
      }
    },
    // 只有状态会变时（开始/完成/切筛选）才需要重拉统计，
    // 翻页时统计不变，避免每页都多发 4 个请求
    async refreshAfterAction() {
      await Promise.all([this.loadOrders(), this.loadAllStats()])
    },
    async handleStart(row) {
      try {
        await this.$confirm(`确认开始处理工单 ${row.order_no}？`, '开始处理', { type: 'warning' })
        await api.startWorkOrder(row.order_no)
        this.$message.success('工单已开始处理')
        this.detailVisible = false
        this.loadOrders()
      } catch (e) {
        if (e !== 'cancel') this.$message.error(e.message || '操作失败')
      }
    },
    async handleWorkerComplete(row) {
      try {
        await this.$confirm(`确认已完成工单 ${row.order_no} 的处理？`, '完成处理', { type: 'warning' })
        await api.workerCompleteWorkOrder(row.order_no, this.worker.id)
        this.$message.success('已提交，等待管理员确认')
        this.detailVisible = false
        this.loadOrders()
      } catch (e) {
        if (e !== 'cancel') this.$message.error(e.message || '操作失败')
      }
    },
    handleDetail(row) {
      this.currentOrder = row
      this.detailVisible = true
    },
    // 库里待处理是大写 'PENDING'、其余小写，统一小写比对
    statusKey(row) {
      return String((row && row.status) || '').toLowerCase()
    },
    statusText(status) {
      const map = {
        pending: '待处理',
        processing: '处理中',
        worker_completed: '待确认',
        completed: '已完成'
      }
      return map[String(status || '').toLowerCase()] || status || '-'
    },
    statusClass(status) {
      const map = {
        pending: 'chip--muted',
        processing: 'chip--info',
        worker_completed: 'chip--warn',
        completed: 'chip--ok'
      }
      return map[String(status || '').toLowerCase()] || 'chip--muted'
    },
    priorityClass(priority) {
      if (priority === '高') return 'chip--danger'
      if (priority === '中') return 'chip--warn'
      return 'chip--muted'
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
.orders { min-height: 100vh; background: var(--canvas); }

.topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  background: linear-gradient(120deg, #101935, #1e293b);
  color: #fff;
  box-shadow: 0 6px 20px rgba(15, 23, 42, 0.18);
}
.topbar__inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  max-width: 1180px;
  margin: 0 auto;
  padding: 12px 20px;
}
.topbar__brand { display: flex; align-items: center; gap: 9px; font-size: 15px; font-weight: 600; }
.topbar__logo {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 9px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  box-shadow: 0 4px 14px rgba(99, 102, 241, 0.45);
}
.topbar__user { display: flex; align-items: center; gap: 10px; }
.topbar__avatar {
  background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
  font-size: 12px;
  font-weight: 600;
}
.topbar__meta { display: flex; flex-direction: column; line-height: 1.25; }
.topbar__name { font-size: 13.5px; font-weight: 600; }
.topbar__id { font-size: 11px; opacity: 0.65; }
.topbar__logout {
  padding: 5px 12px;
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 99px;
  background: transparent;
  color: rgba(255, 255, 255, 0.85);
  font: inherit;
  font-size: 12.5px;
  cursor: pointer;
  transition: all 0.18s var(--ease);
}
.topbar__logout:hover { background: rgba(255, 255, 255, 0.12); color: #fff; }

.content {
  max-width: 1180px;
  margin: 0 auto;
  padding: 18px 20px 40px;
}

.filters {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}
.filter {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 12px 8px;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: #fff;
  cursor: pointer;
  transition: all 0.18s var(--ease);
}
.filter:hover { border-color: #c7cdec; transform: translateY(-2px); box-shadow: var(--shadow-sm); }
.filter.is-active {
  border-color: var(--brand);
  background: var(--brand-soft);
  box-shadow: 0 0 0 3px var(--brand-ring);
}
.filter__num { font-size: 20px; font-weight: 700; color: var(--ink-900); font-variant-numeric: tabular-nums; }
.filter.is-active .filter__num { color: var(--brand); }
.filter__label { font-size: 12px; color: var(--ink-500); }

.list { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 14px; }

.order { padding: 16px 18px; cursor: pointer; }
.order:hover { transform: translateY(-3px); box-shadow: var(--shadow-md); }
.order__top { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.order__no { color: var(--ink-400); }
.order__title {
  margin-top: 8px;
  font-size: 15px;
  line-height: 1.45;
}
.order__tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 9px; }
.order__desc {
  margin-top: 9px;
  color: var(--ink-500);
  font-size: 13px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.order__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 12px;
  padding-top: 11px;
  border-top: 1px dashed var(--line);
  font-size: 12px;
  color: var(--ink-400);
}
.order__addr { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
/* 线性图标是 inline-flex，与文字混排时默认按基线对齐会偏低，手动抬一点 */
.order__addr-icon { margin-right: 3px; vertical-align: -2px; }
.order__time { flex: none; font-variant-numeric: tabular-nums; }
.order__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}
.order__done { margin-right: auto; color: var(--ink-400); font-size: 12.5px; }

.pager { display: flex; justify-content: center; margin-top: 20px; }

/* 详情 */
.detail__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
  color: var(--ink-400);
}
.detail__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  background: var(--line-soft);
  border: 1px solid var(--line-soft);
  border-radius: var(--r-md);
  overflow: hidden;
}
.kv {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: #fff;
  font-size: 13px;
}
.kv--wide { grid-column: 1 / -1; }
.kv span { flex: none; width: 62px; color: var(--ink-400); font-size: 12.5px; }
.kv b { font-weight: 500; color: var(--ink-800); word-break: break-word; }

@media (max-width: 720px) {
  .topbar__inner { padding: 10px 14px; }
  .content { padding: 14px 14px 32px; }
  .filters { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .list { grid-template-columns: 1fr; }
  .detail__grid { grid-template-columns: 1fr; }
}
</style>
