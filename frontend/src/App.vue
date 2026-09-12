<template>
  <div class="shell" :class="{ 'shell--collapsed': collapsed }">
    <!-- 侧边栏 -->
    <aside class="side">
      <div class="side__brand" @click="$router.push('/')">
        <div class="side__logo">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
          </svg>
        </div>
        <div v-show="!collapsed" class="side__name">
          <span class="side__title">智能工单系统</span>
          <span class="side__sub">Property Repair Console</span>
        </div>
      </div>

      <nav class="side__nav">
        <p v-show="!collapsed" class="side__group">业务</p>
        <button
          v-for="item in navMain"
          :key="item.path"
          class="nav-item"
          :class="{ 'is-active': isActive(item.path) }"
          :title="collapsed ? item.label : ''"
          @click="$router.push(item.path)"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span v-show="!collapsed" class="nav-item__label">{{ item.label }}</span>
        </button>

        <p v-show="!collapsed" class="side__group">系统</p>
        <button
          v-for="item in navSys"
          :key="item.path"
          class="nav-item"
          :class="{ 'is-active': isActive(item.path) }"
          :title="collapsed ? item.label : ''"
          @click="$router.push(item.path)"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span v-show="!collapsed" class="nav-item__label">{{ item.label }}</span>
        </button>
      </nav>

      <button class="side__collapse" :title="collapsed ? '展开侧栏' : '收起侧栏'" @click="toggleSidebar">
        <el-icon><component :is="collapsed ? 'Expand' : 'Fold'" /></el-icon>
        <span v-show="!collapsed">收起侧栏</span>
      </button>
    </aside>

    <!-- 主区域 -->
    <div class="main">
      <header class="topbar">
        <div class="topbar__left">
          <h1 class="topbar__title">{{ pageTitle }}</h1>
          <button
            type="button"
            class="chip health-chip"
            :class="online ? 'chip--ok' : 'chip--danger'"
            :disabled="healthChecking"
            :title="healthChecking ? '正在检测后端连通性…' : (online ? '点击重新检测后端连通性' : '后端未连接，点击重试')"
            @click="checkHealth"
          >
            <i class="chip--dot" />{{ healthChecking ? '检测中…' : (online ? '服务正常' : '后端未连接') }}
          </button>
        </div>
        <div class="topbar__right">
          <span class="topbar__clock">{{ clock }}</span>
        </div>
      </header>

      <main class="content">
        <router-view v-slot="{ Component }">
          <transition name="route" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script>
import api from './api'

export default {
  data() {
    return {
      online: false,
      collapsed: false,
      clock: '',
      clockTimer: null,
      healthTimer: null,
      // 防重入：定时器与手动点击可能同时触发，避免并发打同一个健康检查接口
      healthChecking: false,
      navMain: [
        { path: '/', label: '智能报修', icon: 'ChatLineSquare' },
        { path: '/orders', label: '工单管理', icon: 'Tickets' },
        { path: '/feedback', label: '反馈管理', icon: 'ChatDotSquare' }
      ],
      navSys: [
        { path: '/dashboard', label: '数据看板', icon: 'DataAnalysis' },
        { path: '/test', label: '模型测试', icon: 'Cpu' },
        { path: '/database', label: '数据库', icon: 'Coin' },
        { path: '/prompts', label: '提示词', icon: 'Setting' }
      ]
    }
  },
  computed: {
    pageTitle() {
      return this.$route.meta.title || '智能工单系统'
    }
  },
  async mounted() {
    this.tick()
    // 只显示到分钟，没必要每秒触发一次渲染；20s 一跳足够且省掉大量无意义 diff
    this.clockTimer = setInterval(() => this.tick(), 20000)
    this.checkHealth()
    // 服务掉线/恢复时，状态点跟着变，不用手动刷新
    this.healthTimer = setInterval(() => this.checkHealth(), 60000)
  },
  beforeUnmount() {
    if (this.clockTimer) clearInterval(this.clockTimer)
    if (this.healthTimer) clearInterval(this.healthTimer)
  },
  methods: {
    isActive(path) {
      if (path === '/') return this.$route.path === '/'
      return this.$route.path === path || this.$route.path.startsWith(path + '/')
    },
    toggleSidebar() {
      this.collapsed = !this.collapsed
    },
    async checkHealth() {
      if (this.healthChecking) return
      this.healthChecking = true
      try {
        await api.healthCheck()
        this.online = true
      } catch (e) {
        this.online = false
      } finally {
        this.healthChecking = false
      }
    },
    tick() {
      const d = new Date()
      const pad = n => String(n).padStart(2, '0')
      this.clock = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
    }
  }
}
</script>

<style scoped>
.shell {
  display: flex;
  min-height: 100vh;
}

/* ---------- 侧栏 ---------- */
.side {
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  width: 232px;
  height: 100vh;
  flex: none;
  padding: 18px 14px 12px;
  background: linear-gradient(180deg, #101935 0%, #0b1224 100%);
  transition: width var(--dur) var(--ease);
}
.shell--collapsed .side { width: 68px; }

.side__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 6px 18px;
  cursor: pointer;
}
.side__logo {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  flex: none;
  border-radius: 10px;
  color: #fff;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  box-shadow: 0 6px 18px rgba(99, 102, 241, 0.4);
}
.side__name { display: flex; flex-direction: column; overflow: hidden; }
.side__title { color: #f8fafc; font-size: 15px; font-weight: 600; white-space: nowrap; }
.side__sub { color: #64748b; font-size: 10.5px; letter-spacing: 0.04em; white-space: nowrap; }

.side__nav { flex: 1; overflow-y: auto; overflow-x: hidden; padding-bottom: 8px; }
.side__group {
  margin: 14px 8px 6px;
  color: #475569;
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 11px;
  width: 100%;
  margin-bottom: 2px;
  padding: 0 10px;
  height: 40px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: #94a3b8;
  font: inherit;
  font-size: 13.5px;
  text-align: left;
  cursor: pointer;
  transition: background 0.18s var(--ease), color 0.18s var(--ease);
}
.nav-item:hover { background: rgba(148, 163, 184, 0.12); color: #e2e8f0; }
.nav-item.is-active {
  background: linear-gradient(90deg, rgba(99, 102, 241, 0.9), rgba(139, 92, 246, 0.75));
  color: #fff;
  box-shadow: 0 6px 16px rgba(79, 70, 229, 0.35);
}
.nav-item .el-icon { font-size: 17px; flex: none; }
.nav-item__label { white-space: nowrap; overflow: hidden; }

.side__collapse {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 36px;
  margin-top: 10px;
  border: 0;
  border-radius: 10px;
  background: rgba(148, 163, 184, 0.1);
  color: #94a3b8;
  font: inherit;
  font-size: 12.5px;
  cursor: pointer;
  transition: background 0.18s var(--ease), color 0.18s var(--ease);
}
.side__collapse:hover { background: rgba(148, 163, 184, 0.2); color: #e2e8f0; }

.side::-webkit-scrollbar-thumb { background: rgba(148, 163, 184, 0.3); }

/* ---------- 主区域 ---------- */
.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  height: 60px;
  padding: 0 26px;
  background: rgba(255, 255, 255, 0.86);
  backdrop-filter: saturate(180%) blur(12px);
  border-bottom: 1px solid var(--line);
}
.topbar__left { display: flex; align-items: center; gap: 12px; }
/* 状态点做成按钮：点击即可重新检测连通性 */
.health-chip {
  border: 0;
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: filter 0.18s var(--ease);
}
.health-chip:hover { filter: brightness(0.96); }
.health-chip:disabled { cursor: progress; }
.health-chip:focus-visible { outline: none; box-shadow: 0 0 0 3px var(--brand-ring); }
.topbar__title { font-size: 16px; font-weight: 600; color: var(--ink-900); }
.topbar__clock {
  color: var(--ink-400);
  font-size: 12.5px;
  font-variant-numeric: tabular-nums;
}

.content {
  flex: 1;
  padding: 22px 26px 40px;
  max-width: 1440px;
  width: 100%;
}

/* 路由切换 */
.route-enter-active { transition: opacity 0.26s var(--ease), transform 0.26s var(--ease); }
.route-leave-active { transition: opacity 0.16s var(--ease), transform 0.16s var(--ease); }
.route-enter-from { opacity: 0; transform: translateY(10px); }
.route-leave-to { opacity: 0; transform: translateY(-6px); }

@media (max-width: 900px) {
  .shell--collapsed .side,
  .side { width: 68px; }
  .side__name, .side__group, .nav-item__label { display: none; }
  .content { padding: 18px 14px 32px; }
  .topbar { padding: 0 14px; }
  .topbar__clock { display: none; }
}
</style>
