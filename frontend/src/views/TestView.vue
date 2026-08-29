<template>
  <div>
    <h2>模型准确度测试</h2>

    <el-card style="max-width:700px;margin-bottom:20px">
      <el-form :inline="true">
        <el-form-item label="测试条数">
          <el-input-number v-model="testCount" :min="10" :max="2000" :step="50" />
        </el-form-item>
        <el-form-item label="并发数">
          <el-input-number v-model="workers" :min="1" :max="10" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="startTest" :loading="running">启动测试</el-button>
        </el-form-item>
      </el-form>
      <p style="color:#909399;font-size:13px">测试耗时：200条约2分钟，1000条约10分钟</p>
    </el-card>

    <el-card v-if="taskId" style="margin-bottom:20px">
      <template #header>测试进度</template>
      <el-progress :percentage="progress" :status="status==='completed'?'success':status==='failed'?'exception':''" />
      <p style="margin-top:8px">
        状态: <el-tag :type="status==='completed'?'success':status==='failed'?'danger':'warning'">{{ statusText }}</el-tag>
        <span v-if="running" style="margin-left:12px">约需 {{ Math.round(estimateMinutes) }} 分钟</span>
      </p>
      <div v-if="logLines.length" style="background:#f5f7fa;padding:10px;border-radius:4px;max-height:200px;overflow-y:auto;margin-top:10px">
        <div v-for="(line,i) in logLines" :key="i" style="font-size:13px;font-family:monospace;white-space:pre-wrap">{{ line }}</div>
      </div>
    </el-card>

    <el-card v-if="result">
      <template #header>测试结果</template>
      <el-row :gutter="20">
        <el-col :span="6">
          <el-statistic title="综合正确率" :value="result.accuracy" suffix="%" :precision="1" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="subCategory通过率" :value="result.subcategory_accuracy" suffix="%" :precision="1" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="problem匹配率" :value="result.problem_accuracy" suffix="%" :precision="1" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="总耗时" :value="result.total_elapsed_seconds" suffix="秒" :precision="0" />
        </el-col>
      </el-row>
      <el-divider />
      <p>正确: {{ result.correct_count }} / 有效测试: {{ result.effective_total }} / 失败: {{ result.failed_count }}</p>
      <el-button v-if="result.log_file" style="margin-top:8px" @click="viewLog(result.log_file)">查看完整日志</el-button>
    </el-card>

    <el-card style="margin-top:20px">
      <template #header>历史测试日志</template>
      <el-table :data="logFiles" stripe v-loading="logLoading">
        <el-table-column prop="filename" label="文件名" min-width="300" />
        <el-table-column prop="size_bytes" label="大小" width="100">
          <template #default="{row}">{{ (row.size_bytes/1024).toFixed(1) }}KB</template>
        </el-table-column>
        <el-table-column prop="modified_time" label="修改时间" width="180" />
        <el-table-column label="操作" width="120">
          <template #default="{row}">
            <el-button link type="primary" size="small" @click="viewLog(row.filename)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script>
import api from '../api'

export default {
  data() {
    return {
      testCount: 200, workers: 3, running: false,
      taskId: '', status: '', progress: 0, logLines: [],
      result: null, logFiles: [], logLoading: false,
      timer: null, startTime: null
    }
  },
  computed: {
    statusText() {
      const map = { running: '运行中', completed: '已完成', failed: '失败' }
      return map[this.status] || this.status
    },
    estimateMinutes() {
      if (!this.startTime || this.progress <= 0) return 0
      const elapsed = (Date.now() - this.startTime) / 1000
      return elapsed / this.progress * 100 / 60
    }
  },
  mounted() { this.loadLogs() },
  beforeUnmount() { this.stopPolling() },
  methods: {
    async startTest() {
      this.running = true; this.result = null
      try {
        const data = await api.runTest(this.testCount, this.workers)
        this.taskId = data.task_id
        this.status = 'running'; this.startTime = Date.now()
        this.startPolling()
      } catch (e) { this.$message.error(e.message); this.running = false }
    },
    startPolling() {
      this.stopPolling()
      this.timer = setInterval(() => this.poll(), 3000)
    },
    stopPolling() { if (this.timer) { clearInterval(this.timer); this.timer = null } },
    async poll() {
      try {
        const data = await api.getTestStatus(this.taskId)
        this.status = data.status
        this.progress = data.progress || 0
        if (data.log_lines) this.logLines = data.log_lines.slice(-30)
        if (data.status === 'completed') {
          this.result = data; this.running = false; this.stopPolling(); this.loadLogs()
          this.$message.success(`测试完成！正确率: ${data.accuracy}%`)
        } else if (data.status === 'failed') { this.running = false; this.stopPolling(); this.$message.error('测试失败') }
      } catch (e) { this.running = false; this.stopPolling() }
    },
    async loadLogs() {
      this.logLoading = true
      try { const data = await api.getTestLogs(); this.logFiles = data.logs || [] }
      catch (e) { /* ignore */ }
      finally { this.logLoading = false }
    },
    async viewLog(filename) {
      try {
        const data = await api.getTestLogContent(filename)
        this.$alert(data.content, filename, { dangerouslyUseHTMLString: false, customClass: 'log-dialog' })
      } catch (e) { this.$message.error(e.message) }
    }
  }
}
</script>