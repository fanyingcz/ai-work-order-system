<template>
  <div class="page">
    <div class="page-head">
      <h2 class="page-title">模型准确度测试</h2>
      <p class="page-desc">批量回放样本，评估分类与项目匹配准确率</p>
    </div>

    <!-- 参数 -->
    <div class="card card--pad runner">
      <div class="runner__fields">
        <label class="field">
          <span>测试条数</span>
          <el-input-number v-model="testCount" :min="10" :max="2000" :step="50" :disabled="running" />
        </label>
        <label class="field">
          <span>并发数</span>
          <el-input-number v-model="workers" :min="1" :max="10" :disabled="running" />
        </label>
      </div>
      <el-button type="primary" size="large" @click="startTest" :loading="running">
        {{ running ? '测试进行中' : '启动测试' }}
      </el-button>
      <p class="runner__hint">200 条约 2 分钟，1000 条约 10 分钟</p>
    </div>

    <!-- 进度 -->
    <transition name="fade">
      <div v-if="taskId" class="card progress">
        <div class="card-head">
          <span class="card-head__title">运行进度</span>
          <span class="chip" :class="statusChipClass">{{ statusText }}</span>
        </div>
        <div class="card-body">
          <div class="progress__row">
            <div class="progress__track">
              <div class="progress__fill" :class="{ 'is-done': status === 'completed' }" :style="{ width: progress + '%' }" />
            </div>
            <span class="progress__pct">{{ progress }}%</span>
          </div>
          <p v-if="running && estimateMinutes > 0" class="progress__hint">预计还需 {{ Math.round(estimateMinutes) }} 分钟</p>

          <div v-if="logLines.length" class="terminal">
            <div v-for="(line, i) in logLines" :key="i" class="terminal__line">{{ line }}</div>
          </div>
        </div>
      </div>
    </transition>

    <!-- 结果 -->
    <transition name="fade">
      <div v-if="result" class="card result">
        <div class="card-head">
          <span class="card-head__title">测试结果</span>
          <el-button v-if="result.log_file" size="small" @click="viewLog(result.log_file)">查看完整日志</el-button>
        </div>
        <div class="card-body">
          <div class="result__stats">
            <div v-for="m in metrics" :key="m.label" class="metric">
              <div class="metric__value" :style="{ color: m.color }">
                {{ m.value }}<small>{{ m.suffix }}</small>
              </div>
              <div class="metric__label">{{ m.label }}</div>
            </div>
          </div>
          <div class="result__foot">
            <span>正确 <b>{{ result.correct_count }}</b></span>
            <span>有效 <b>{{ result.effective_total }}</b></span>
            <span>失败 <b>{{ result.failed_count }}</b></span>
          </div>
        </div>
      </div>
    </transition>

    <!-- 历史日志 -->
    <div class="card">
      <div class="card-head">
        <span class="card-head__title">历史测试日志</span>
        <span class="card-head__hint">{{ logFiles.length }} 个文件</span>
      </div>
      <el-table :data="logFiles" v-loading="logLoading" max-height="360">
        <el-table-column prop="filename" label="文件名" min-width="280">
          <template #default="{ row }"><span class="mono">{{ row.filename }}</span></template>
        </el-table-column>
        <el-table-column prop="size_bytes" label="大小" width="110">
          <template #default="{ row }">{{ (row.size_bytes / 1024).toFixed(1) }} KB</template>
        </el-table-column>
        <el-table-column prop="modified_time" label="修改时间" width="180" />
        <el-table-column label="操作" width="90" align="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="viewLog(row.filename)">查看</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty">
            <div class="empty__icon"><el-icon><Files /></el-icon></div>
            <div class="empty__text">暂无历史日志</div>
          </div>
        </template>
      </el-table>
    </div>
  </div>
</template>

<script>
import api from '../api'

export default {
  name: 'TestView',
  data() {
    return {
      testCount: 200,
      workers: 3,
      running: false,
      taskId: '',
      status: '',
      progress: 0,
      logLines: [],
      result: null,
      logFiles: [],
      logLoading: false,
      timer: null,
      startTime: null
    }
  },
  computed: {
    statusText() {
      const map = { running: '运行中', completed: '已完成', failed: '失败' }
      return map[this.status] || '准备中'
    },
    statusChipClass() {
      if (this.status === 'completed') return 'chip--ok'
      if (this.status === 'failed') return 'chip--danger'
      return 'chip--info'
    },
    estimateMinutes() {
      if (!this.startTime || this.progress <= 0) return 0
      const elapsed = (Date.now() - this.startTime) / 1000
      return (elapsed / this.progress) * 100 / 60
    },
    metrics() {
      const r = this.result || {}
      const pct = v => (typeof v === 'number' ? v.toFixed(1) : '-')
      return [
        { label: '综合正确率', value: pct(r.accuracy), suffix: '%', color: '#10b981' },
        { label: '类型通过率', value: pct(r.subcategory_accuracy), suffix: '%', color: '#6366f1' },
        { label: '项目匹配率', value: pct(r.problem_accuracy), suffix: '%', color: '#8b5cf6' },
        { label: '总耗时', value: Math.round(r.total_elapsed_seconds || 0), suffix: 's', color: '#0ea5e9' }
      ]
    }
  },
  mounted() { this.loadLogs() },
  beforeUnmount() { this.stopPolling() },
  methods: {
    async startTest() {
      this.running = true
      this.result = null
      this.logLines = []
      this.progress = 0
      try {
        const data = await api.runTest(this.testCount, this.workers)
        this.taskId = data.task_id
        this.status = 'running'
        this.startTime = Date.now()
        this.startPolling()
      } catch (e) {
        this.$message.error(e.message || '启动失败')
        this.running = false
      }
    },
    startPolling() {
      this.stopPolling()
      this.timer = setInterval(() => this.poll(), 3000)
    },
    stopPolling() {
      if (this.timer) { clearInterval(this.timer); this.timer = null }
    },
    async poll() {
      try {
        const data = await api.getTestStatus(this.taskId)
        this.status = data.status
        // 后端 completed 分支不返回 progress，这里补齐，避免进度条回落到 0
        this.progress = data.status === 'completed' ? 100 : (data.progress || 0)
        if (data.log_lines) this.logLines = data.log_lines.slice(-30)
        if (data.status === 'completed') {
          this.result = data
          this.running = false
          this.stopPolling()
          this.loadLogs()
          this.$message.success(`测试完成！正确率: ${data.accuracy}%`)
        } else if (data.status === 'failed') {
          this.running = false
          this.stopPolling()
          this.$message.error('测试失败')
        }
      } catch (e) {
        // 后端对 failed / not_found 走 error_response（code != 0），会在这里落地
        this.running = false
        this.stopPolling()
        this.$message.error(e.message || '任务状态查询失败')
      }
    },
    async loadLogs() {
      this.logLoading = true
      try {
        const data = await api.getTestLogs()
        this.logFiles = data.logs || []
      } catch (e) { /* ignore */ }
      finally { this.logLoading = false }
    },
    async viewLog(filename) {
      try {
        const data = await api.getTestLogContent(filename)
        this.$alert(data.content, filename, { dangerouslyUseHTMLString: false })
      } catch (e) {
        this.$message.error(e.message || '读取失败')
      }
    }
  }
}
</script>

<style scoped>
.runner {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.runner__fields { display: flex; gap: 16px; }
.field { display: grid; gap: 6px; }
.field span { color: var(--ink-500); font-size: 12.5px; }
.runner__hint { flex-basis: 100%; color: var(--ink-400); font-size: 12px; }

.progress, .result { margin-bottom: 16px; }

.progress__row { display: flex; align-items: center; gap: 12px; }
.progress__track {
  flex: 1;
  height: 8px;
  border-radius: 99px;
  background: #f1f4f9;
  overflow: hidden;
}
.progress__fill {
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, #6366f1, #8b5cf6);
  transition: width 0.6s var(--ease);
}
.progress__fill.is-done { background: linear-gradient(90deg, #10b981, #34d399); }
.progress__pct {
  width: 44px;
  text-align: right;
  color: var(--ink-700);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
.progress__hint { margin-top: 8px; color: var(--ink-500); font-size: 12.5px; }

.terminal {
  margin-top: 14px;
  max-height: 220px;
  overflow-y: auto;
  padding: 12px 14px;
  border-radius: var(--r-md);
  background: #0f172a;
  font-family: ui-monospace, Consolas, monospace;
  font-size: 12px;
  line-height: 1.7;
  color: #a5b4fc;
}
.terminal__line { white-space: pre-wrap; }

.result__stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}
.metric {
  padding: 14px 16px;
  border: 1px solid var(--line-soft);
  border-radius: var(--r-md);
  background: #fafbfd;
}
.metric__value {
  font-size: 26px;
  font-weight: 700;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}
.metric__value small { margin-left: 2px; font-size: 13px; font-weight: 600; }
.metric__label { margin-top: 2px; color: var(--ink-500); font-size: 12.5px; }

.result__foot {
  display: flex;
  gap: 22px;
  margin-top: 14px;
  color: var(--ink-500);
  font-size: 13px;
}
.result__foot b { color: var(--ink-900); font-variant-numeric: tabular-nums; }

.mono { font-family: ui-monospace, Consolas, monospace; font-size: 12.5px; color: var(--ink-700); }

.fade-enter-active, .fade-leave-active { transition: opacity 0.24s var(--ease), transform 0.24s var(--ease); }
.fade-enter-from, .fade-leave-to { opacity: 0; transform: translateY(8px); }

@media (max-width: 900px) {
  .result__stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
