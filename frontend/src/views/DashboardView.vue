<template>
  <div class="page">
    <div class="page-head">
      <h2 class="page-title">数据看板</h2>
      <p class="page-desc">系统运行概览与规则数据完整性</p>
    </div>

    <!-- 加载 / 失败提示：避免接口挂了却显示全 0，让人误判为「没有数据」 -->
    <div v-if="error" class="card card--pad notice notice--error">
      <div class="notice__left">
        <el-icon class="notice__icon"><Warning /></el-icon>
        <div>
          <div class="notice__title">看板数据加载失败</div>
          <div class="notice__desc">{{ error }}</div>
        </div>
      </div>
      <el-button type="primary" plain size="small" :loading="loading" @click="reload">重试</el-button>
    </div>

    <!-- 指标卡 -->
    <div v-loading="loading && !loaded" class="stats">
      <button
        v-for="(s, i) in cards"
        :key="s.label"
        class="stat stat--link anim-fade-up"
        :style="{ animationDelay: i * 60 + 'ms' }"
        :title="`查看「${s.label}」明细`"
        @click="goList(s)"
      >
        <div class="stat__icon" :style="{ background: s.bg, color: s.color }">
          <el-icon><component :is="s.icon" /></el-icon>
        </div>
        <div class="stat__body">
          <div class="stat__value">{{ loaded ? s.value : '—' }}</div>
          <div class="stat__label">{{ s.label }}</div>
        </div>
      </button>
    </div>

    <div class="grid">
      <!-- 状态分布 -->
      <section class="card">
        <div class="card-head">
          <span class="card-head__title">工单状态分布</span>
          <span class="card-head__hint">共 {{ stats.total_orders || 0 }} 条</span>
        </div>
        <div class="card-body">
          <div v-if="stats.total_orders" class="bars">
            <div v-for="item in statusDist" :key="item.label" class="bar">
              <div class="bar__meta">
                <span class="bar__label">
                  <i class="bar__dot" :style="{ background: item.color }" />{{ item.label }}
                </span>
                <span class="bar__num">{{ item.count }}</span>
              </div>
              <div class="bar__track">
                <div
                  class="bar__fill"
                  :style="{ width: item.percent + '%', background: item.color }"
                />
              </div>
            </div>
          </div>
          <div v-else class="empty">
            <div class="empty__icon"><el-icon><DataLine /></el-icon></div>
            <div class="empty__text">暂无工单数据</div>
          </div>
        </div>
      </section>

      <!-- 子类别分布 -->
      <section class="card">
        <div class="card-head">
          <span class="card-head__title">报修类型 Top 8</span>
          <span class="card-head__hint">按工单量降序</span>
        </div>
        <div class="card-body">
          <div v-if="subDist.length" class="bars">
            <div v-for="(item, i) in subDist.slice(0, 8)" :key="item.sub_category" class="bar">
              <div class="bar__meta">
                <span class="bar__label">{{ item.sub_category || '未分类' }}</span>
                <span class="bar__num">{{ item.count }}</span>
              </div>
              <div class="bar__track">
                <div
                  class="bar__fill"
                  :style="{ width: item.percent + '%', background: colors[i % colors.length] }"
                />
              </div>
            </div>
          </div>
          <div v-else class="empty">
            <div class="empty__icon"><el-icon><FolderOpened /></el-icon></div>
            <div class="empty__text">暂无分类数据</div>
          </div>
        </div>
      </section>
    </div>

    <!-- 规则完整性 -->
    <section class="card">
      <div class="card-head">
        <span class="card-head__title">规则数据完整性</span>
        <span class="card-head__hint">{{ healthyCount }} / {{ rulesData.length }} 项正常</span>
      </div>
      <div class="card-body health">
        <div v-for="r in rulesData" :key="r.key" class="health__item">
          <span class="health__dot" :class="r.value > 0 ? 'is-ok' : 'is-bad'" />
          <span class="health__key">{{ r.key }}</span>
          <span class="health__val">{{ r.value }}</span>
        </div>
      </div>
    </section>
  </div>
</template>

<script>
import api from '../api'

export default {
  name: 'DashboardView',
  data() {
    return {
      stats: {},
      rules: {},
      loading: false,
      loaded: false,
      error: '',
      colors: ['#6366f1', '#8b5cf6', '#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#14b8a6']
    }
  },
  computed: {
    // 状态分布字段大小写不统一（库里有 'PENDING' 也有小写），统一按小写取值
    dist() {
      const d = this.stats.status_distribution || {}
      const out = {}
      Object.keys(d).forEach(k => { out[String(k).toLowerCase()] = d[k] })
      return out
    },
    cards() {
      const d = this.dist
      return [
        { label: '工单总数', value: this.stats.total_orders || 0, icon: 'Tickets', color: '#6366f1', bg: '#eef2ff', to: { path: '/orders' } },
        { label: '待处理', value: d.pending || 0, icon: 'Clock', color: '#f59e0b', bg: '#fffbeb', to: { path: '/orders', query: { status: 'PENDING' } } },
        { label: '处理中', value: d.processing || 0, icon: 'Loading', color: '#0ea5e9', bg: '#eff6ff', to: { path: '/orders', query: { status: 'processing' } } },
        { label: '已完成', value: d.completed || 0, icon: 'CircleCheck', color: '#10b981', bg: '#ecfdf5', to: { path: '/orders', query: { status: 'completed' } } },
        { label: '维修工人', value: this.stats.total_workers || 0, icon: 'User', color: '#8b5cf6', bg: '#f5f3ff', to: { path: '/database', query: { tab: 'workers' } } },
        { label: '待审核反馈', value: this.stats.pending_feedbacks || 0, icon: 'ChatDotSquare', color: '#ec4899', bg: '#fdf2f8', to: { path: '/feedback' } }
      ]
    },
    statusDist() {
      const d = this.dist
      const total = this.stats.total_orders || 1
      const defs = [
        { label: '待处理', key: 'pending', color: '#f59e0b' },
        { label: '处理中', key: 'processing', color: '#0ea5e9' },
        { label: '待确认', key: 'worker_completed', color: '#8b5cf6' },
        { label: '已完成', key: 'completed', color: '#10b981' }
      ]
      return defs.map(x => ({
        label: x.label,
        color: x.color,
        count: d[x.key] || 0,
        percent: Math.round(((d[x.key] || 0) / total) * 100)
      }))
    },
    subDist() {
      const d = this.stats.subcategory_distribution || []
      const max = d.length ? d[0].count : 1
      return d.map(item => ({ ...item, percent: Math.round((item.count / max) * 100) }))
    },
    rulesData() {
      const r = this.rules
      return [
        { key: '子类别定义', value: r.subcategories_count || 0 },
        { key: '分类规则', value: r.categories_count || 0 },
        { key: '触发关键词', value: r.keywords_count || 0 },
        { key: '触发位置', value: r.locations_count || 0 },
        { key: '地址映射', value: r.address_mappings_count || 0 },
        { key: '维修工人', value: r.workers_count || 0 }
      ]
    },
    healthyCount() {
      return this.rulesData.filter(r => r.value > 0).length
    }
  },
  mounted() {
    this.load()
  },
  methods: {
    // 区分「加载中」「真的为空」「加载失败」三种状态：
    // 接口挂掉时如果照旧渲染全 0，会被误读成「系统里没有数据」。
    async load() {
      if (this.loading) return
      this.loading = true
      this.error = ''
      try {
        this.stats = (await api.getStats()) || {}
        this.loaded = true
      } catch (e) {
        this.error = (e && e.message) || '无法连接到后端服务'
      } finally {
        this.loading = false
      }
      // 规则完整性是次要信息，失败不拖累主看板
      try {
        this.rules = (await api.checkRulesCompleteness()) || {}
      } catch (e) { /* ignore */ }
    },
    reload() {
      this.load()
    },
    // 指标卡跳转到对应明细页，并带上筛选条件
    goList(s) {
      if (!s || !s.to) return
      this.$router.push(s.to)
    }
  }
}
</script>

<style scoped>
.stats {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}

/* 指标卡现在可点击跳明细，重置 button 默认样式 */
.stat--link {
  width: 100%;
  border: 1px solid var(--line);
  background: var(--surface);
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.stat--link:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--brand-ring);
}
.stat__body { min-width: 0; }

.notice {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}
.notice--error {
  border-color: #fecaca;
  background: linear-gradient(180deg, #fff7f7, #ffffff);
}
.notice__left { display: flex; align-items: flex-start; gap: 10px; min-width: 0; }
.notice__icon { font-size: 16px; line-height: 1.5; }
.notice__title { font-weight: 600; color: #b91c1c; font-size: 13.5px; }
.notice__desc { margin-top: 2px; color: var(--ink-500); font-size: 12.5px; word-break: break-word; }

.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.card-head__hint { color: var(--ink-400); font-size: 12px; font-weight: 400; }

.bars { display: grid; gap: 14px; }
.bar__meta {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 13px;
}
.bar__label { display: inline-flex; align-items: center; gap: 7px; color: var(--ink-700); }
.bar__dot { width: 7px; height: 7px; border-radius: 99px; }
.bar__num { color: var(--ink-500); font-variant-numeric: tabular-nums; }
.bar__track {
  height: 8px;
  border-radius: 99px;
  background: #f1f4f9;
  overflow: hidden;
}
.bar__fill {
  height: 100%;
  border-radius: 99px;
  transition: width 0.7s var(--ease);
}

.health {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
}
.health__item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid var(--line-soft);
  border-radius: var(--r-md);
  background: #fafbfd;
}
.health__dot { width: 7px; height: 7px; border-radius: 99px; flex: none; }
.health__dot.is-ok { background: var(--ok); box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.15); }
.health__dot.is-bad { background: var(--danger); box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.15); }
.health__key { flex: 1; color: var(--ink-500); font-size: 12.5px; }
.health__val { font-weight: 600; color: var(--ink-900); font-variant-numeric: tabular-nums; }

@media (max-width: 1200px) {
  .stats { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .health { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 860px) {
  .grid { grid-template-columns: 1fr; }
  .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
