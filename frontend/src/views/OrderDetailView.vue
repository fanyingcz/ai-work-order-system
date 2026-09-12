<template>
  <div class="page">
    <button class="back" @click="$router.back()">
      <span class="back__arrow">←</span> 返回工单列表
    </button>

    <div class="card" v-loading="loading">
      <div class="card-head">
        <div class="card-head__left">
          <span class="card-head__title">工单详情</span>
          <span v-if="wo.order_no" class="mono">{{ wo.order_no }}</span>
        </div>
        <span class="chip" :class="statusClass(wo.status)">{{ statusText(wo.status) }}</span>
      </div>

      <div class="card-body">
        <!-- 编辑模式 -->
        <el-form v-if="editing" :model="editForm" label-width="96px">
          <div class="form-grid">
            <el-form-item label="报修类型"><el-input v-model="editForm.sub_category" /></el-form-item>
            <el-form-item label="报修项目"><el-input v-model="editForm.problem" /></el-form-item>
            <el-form-item label="优先级">
              <el-select v-model="editForm.priority" style="width:100%">
                <el-option label="高" value="高" />
                <el-option label="中" value="中" />
                <el-option label="低" value="低" />
              </el-select>
            </el-form-item>
            <el-form-item label="物业公司"><el-input v-model="editForm.property_company" /></el-form-item>
            <el-form-item label="维修单位"><el-input v-model="editForm.maintenance_unit" /></el-form-item>
            <el-form-item label="报修人"><el-input v-model="editForm.reporter_name" /></el-form-item>
            <el-form-item label="联系电话"><el-input v-model="editForm.reporter_phone" /></el-form-item>
          </div>
          <el-form-item label="报修概述">
            <el-input v-model="editForm.user_input" type="textarea" :rows="3" />
          </el-form-item>
          <el-form-item label="报修地址">
            <el-input v-model="editForm.address" />
          </el-form-item>
          <div class="form-actions">
            <el-button type="primary" @click="saveEdit" :loading="saving">保存修改</el-button>
            <el-button @click="cancelEdit">取消</el-button>
          </div>
        </el-form>

        <!-- 查看模式 -->
        <template v-else>
          <div class="detail-grid">
            <div class="kv"><span>受理时间</span><b>{{ wo.accept_time || '-' }}</b></div>
            <div class="kv"><span>报修类型</span><b>{{ wo.sub_category || '-' }}</b></div>
            <div class="kv"><span>报修项目</span><b>{{ wo.problem || '-' }}</b></div>
            <div class="kv">
              <span>优先级</span>
              <b><span class="chip" :class="wo.priority === '高' ? 'chip--danger' : 'chip--warn'">{{ wo.priority || '-' }}</span></b>
            </div>
            <div class="kv"><span>物业公司</span><b>{{ wo.property_company || '-' }}</b></div>
            <div class="kv"><span>维修单位</span><b>{{ wo.maintenance_unit || '-' }}</b></div>
            <div class="kv">
              <span>指派工人</span>
              <b v-if="wo.worker_info" class="worker">
                <el-avatar :size="22" class="worker__av">{{ (wo.worker_info.name || '?').charAt(0) }}</el-avatar>
                {{ wo.worker_info.name }} · {{ wo.worker_info.phone || '-' }}
              </b>
              <b v-else class="muted">未指派</b>
            </div>
            <div class="kv"><span>目标部门</span><b>{{ wo.target_dept_semantic || '-' }}</b></div>
            <div class="kv"><span>报修人</span><b>{{ wo.reporter_name || '-' }}</b></div>
            <div class="kv"><span>联系电话</span><b>{{ wo.reporter_phone || '-' }}</b></div>
            <div class="kv kv--wide"><span>报修概述</span><b>{{ wo.user_input || '-' }}</b></div>
            <div class="kv kv--wide"><span>报修地址</span><b>{{ wo.address || '-' }}</b></div>
          </div>

          <div class="actions">
            <el-button
              v-if="isPending"
              type="warning"
              :loading="acting === 'start'"
              :disabled="!!acting"
              @click="startOrder"
            >开始处理</el-button>
            <el-button v-if="isPending" type="primary" plain :disabled="!!acting" @click="enterEdit">编辑工单</el-button>
            <el-button
              v-if="wo.status && wo.status !== 'completed'"
              type="success"
              :loading="acting === 'complete'"
              :disabled="!!acting"
              @click="completeOrder"
            >标记为已完成</el-button>
            <span v-if="wo.status === 'worker_completed'" class="chip chip--warn">
              <i class="chip--dot" />工人已完工，请确认后标记完成
            </span>
          </div>

          <div class="feedback">
            <div class="feedback__head">
              <h4>分类反馈</h4>
              <p>判定有误时可提交人工修正，审核通过后关键词会进入规则表</p>
            </div>
            <div class="feedback__form">
              <el-input v-model="fb.human_problem" placeholder="正确的报修项目" clearable />
              <el-input v-model="fb.human_keyword" placeholder="建议补充的关键词" clearable />
              <el-button @click="submitFeedback" :loading="submitting">提交反馈</el-button>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script>
import api from '../api'

export default {
  name: 'OrderDetailView',
  data() {
    return {
      wo: {},
      loading: false,
      submitting: false,
      saving: false,
      editing: false,
      editForm: {},
      // 正在执行的动作（'start' / 'complete'），既防重复点击也用来给按钮加 loading
      acting: '',
      fb: { human_problem: '', human_keyword: '' }
    }
  },
  computed: {
    statusKey() {
      return String(this.wo.status || '').toLowerCase()
    },
    isPending() {
      return this.statusKey === 'pending'
    },
    isCompleted() {
      return this.statusKey === 'completed'
    },
    isWorkerCompleted() {
      return this.statusKey === 'worker_completed'
    }
  },
  created() { this.load() },
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
    async load() {
      this.loading = true
      try {
        this.wo = await api.getWorkOrder(this.$route.params.orderNo) || {}
      } catch (e) {
        this.$message.error('加载失败: ' + e.message)
      } finally {
        this.loading = false
      }
    },
    async startOrder() {
      if (this.acting) return
      try {
        await this.$confirm('确认开始处理该工单？', '确认', { type: 'info' })
      } catch (e) {
        return
      }
      this.acting = 'start'
      try {
        await api.startWorkOrder(this.wo.order_no)
        this.$message.success('工单已标记为处理中')
        await this.load()
      } catch (e) {
        this.$message.error(e.message || '操作失败')
      } finally {
        this.acting = ''
      }
    },
    async completeOrder() {
      if (this.acting) return
      const tip = this.isWorkerCompleted
        ? '工人已提交完工，确认后该工单将标记为已完成。'
        : '确认标记该工单为已完成？'
      try {
        await this.$confirm(tip, '确认', { type: 'warning' })
      } catch (e) {
        return
      }
      this.acting = 'complete'
      try {
        await api.completeWorkOrder(this.wo.order_no)
        this.$message.success('已标记完成')
        await this.load()
      } catch (e) {
        this.$message.error(e.message || '操作失败')
      } finally {
        this.acting = ''
      }
    },
    enterEdit() {
      this.editForm = {
        user_input: this.wo.user_input || '',
        sub_category: this.wo.sub_category || '',
        problem: this.wo.problem || '',
        priority: this.wo.priority || '',
        property_company: this.wo.property_company || '',
        maintenance_unit: this.wo.maintenance_unit || '',
        address: this.wo.address || '',
        reporter_name: this.wo.reporter_name || '',
        reporter_phone: this.wo.reporter_phone || ''
      }
      this.editing = true
    },
    cancelEdit() {
      this.editing = false
      this.editForm = {}
    },
    async saveEdit() {
      if (this.saving) return
      this.saving = true
      try {
        await api.updateWorkOrder(this.wo.order_no, this.editForm)
        this.$message.success('工单修改成功')
        this.editing = false
        this.editForm = {}
        await this.load()
      } catch (e) {
        this.$message.error(e.message || '保存失败')
      } finally {
        this.saving = false
      }
    },
    async submitFeedback() {
      if (this.submitting) return
      if (!this.fb.human_problem || !this.fb.human_keyword) {
        this.$message.warning('请填写正确项目和关键词')
        return
      }
      this.submitting = true
      try {
        await api.submitFeedback(this.wo.order_no, this.fb.human_problem, this.fb.human_keyword)
        this.$message.success('反馈已提交，等待审核')
        this.fb = { human_problem: '', human_keyword: '' }
      } catch (e) {
        this.$message.error(e.message || '提交失败')
      } finally {
        this.submitting = false
      }
    }
  }
}
</script>

<style scoped>
.back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 14px;
  padding: 6px 12px 6px 8px;
  border: 1px solid var(--line);
  border-radius: 99px;
  background: #fff;
  color: var(--ink-700);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.18s var(--ease);
}
.back:hover { border-color: var(--brand); color: var(--brand); }
.back__arrow { transition: transform 0.18s var(--ease); }
.back:hover .back__arrow { transform: translateX(-3px); }

.card-head__left { display: flex; align-items: center; gap: 10px; }
.mono {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 12.5px;
  color: var(--ink-400);
}

.detail-grid {
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
  gap: 12px;
  padding: 12px 16px;
  background: #fff;
  font-size: 13.5px;
}
.kv--wide { grid-column: 1 / -1; }
.kv span { flex: none; width: 72px; color: var(--ink-400); font-size: 12.5px; }
.kv b { font-weight: 500; color: var(--ink-800); word-break: break-word; }
.muted { color: var(--ink-400) !important; font-weight: 400 !important; }
.worker { display: inline-flex; align-items: center; gap: 7px; }
.worker__av {
  background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
  font-size: 11px;
}

.actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 18px;
}

.feedback {
  margin-top: 20px;
  padding: 16px;
  border: 1px dashed var(--line);
  border-radius: var(--r-md);
  background: #fafbfd;
}
.feedback__head h4 { font-size: 13.5px; }
.feedback__head p { margin-top: 3px; color: var(--ink-500); font-size: 12.5px; }
.feedback__form {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: 10px;
  margin-top: 12px;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 18px;
}
.form-actions { display: flex; gap: 10px; margin-top: 6px; }

@media (max-width: 760px) {
  .detail-grid, .form-grid, .feedback__form { grid-template-columns: 1fr; }
}
</style>
