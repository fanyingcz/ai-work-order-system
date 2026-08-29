<template>
  <div>
    <el-button @click="$router.back()" style="margin-bottom:16px">← 返回</el-button>

    <el-card v-loading="loading">
      <template #header>
        <div style="display:flex;align-items:center;justify-content:space-between">
          <span><strong>工单详情</strong></span>
          <el-tag
            :type="wo.status === 'completed' ? 'success' : wo.status === 'processing' ? 'warning' : wo.status === 'worker_completed' ? 'primary' : 'info'"
          >
            {{ statusText(wo.status) }}
          </el-tag>
        </div>
      </template>

      <!-- 编辑模式 -->
      <template v-if="editing">
        <el-form :model="editForm" label-width="100px" size="default">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="报修类型">
                <el-input v-model="editForm.sub_category" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="报修项目">
                <el-input v-model="editForm.problem" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="优先级">
                <el-select v-model="editForm.priority" style="width:100%">
                  <el-option label="高" value="高" />
                  <el-option label="中" value="中" />
                  <el-option label="低" value="低" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="物业公司">
                <el-input v-model="editForm.property_company" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="维修单位">
                <el-input v-model="editForm.maintenance_unit" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="报修人">
                <el-input v-model="editForm.reporter_name" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="联系电话">
                <el-input v-model="editForm.reporter_phone" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="报修概述">
            <el-input v-model="editForm.user_input" type="textarea" :rows="3" />
          </el-form-item>
          <el-form-item label="报修地址">
            <el-input v-model="editForm.address" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="saveEdit" :loading="saving">保存修改</el-button>
            <el-button @click="cancelEdit">取消</el-button>
          </el-form-item>
        </el-form>
      </template>

      <!-- 查看模式 -->
      <template v-else>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="工单号"><el-tag type="primary">{{ wo.order_no }}</el-tag></el-descriptions-item>
          <el-descriptions-item label="受理时间">{{ wo.accept_time }}</el-descriptions-item>
          <el-descriptions-item label="报修类型">{{ wo.sub_category }}</el-descriptions-item>
          <el-descriptions-item label="报修项目">{{ wo.problem }}</el-descriptions-item>
          <el-descriptions-item label="优先级">
            <el-tag :type="wo.priority === '高' ? 'danger' : 'warning'">{{ wo.priority }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="目标部门">{{ wo.target_dept_semantic || '-' }}</el-descriptions-item>
          <el-descriptions-item label="指派工人">
            <template v-if="wo.worker_info">
              <el-tag type="success">{{ wo.worker_info.name }}</el-tag>
            </template>
            <span v-else style="color:#909399">未指派</span>
          </el-descriptions-item>
          <el-descriptions-item label="工人电话">
            <template v-if="wo.worker_info">
              {{ wo.worker_info.phone }}
            </template>
            <span v-else style="color:#909399">-</span>
          </el-descriptions-item>
          <el-descriptions-item label="物业公司">{{ wo.property_company }}</el-descriptions-item>
          <el-descriptions-item label="维修单位">{{ wo.maintenance_unit }}</el-descriptions-item>
          <el-descriptions-item label="报修人">{{ wo.reporter_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="联系电话">{{ wo.reporter_phone || '-' }}</el-descriptions-item>
          <el-descriptions-item label="报修概述" :span="2">{{ wo.user_input }}</el-descriptions-item>
          <el-descriptions-item label="报修地址" :span="2">{{ wo.address || '-' }}</el-descriptions-item>
        </el-descriptions>

        <div style="margin-top:20px">
          <el-button v-if="(wo.status || '').toLowerCase() === 'pending'" type="warning" @click="startOrder">开始处理</el-button>
          <el-button v-if="(wo.status || '').toLowerCase() === 'pending'" type="primary" @click="enterEdit">编辑工单</el-button>
          <el-button v-if="wo.status !== 'completed'" type="success" @click="completeOrder">标记为已完成</el-button>
          <el-tag v-if="(wo.status || '').toLowerCase() === 'worker_completed'" type="primary" effect="dark" style="margin-left:10px">
            工人已完成处理，请确认后点击"标记为已完成"
          </el-tag>

          <el-divider />
          <h4>提交分类反馈</h4>
          <p style="color:#909399;font-size:13px;margin-bottom:10px">如果发现系统分类有误，可提交人工修正建议</p>
          <el-form :inline="true">
            <el-form-item label="正确项目">
              <el-input v-model="fb.human_problem" placeholder="正确的报修项目" />
            </el-form-item>
            <el-form-item label="关键词">
              <el-input v-model="fb.human_keyword" placeholder="建议添加的关键词" />
            </el-form-item>
            <el-form-item>
              <el-button @click="submitFeedback" :loading="submitting">提交反馈</el-button>
            </el-form-item>
          </el-form>
        </div>
      </template>
    </el-card>
  </div>
</template>

<script>
import api from '../api'

export default {
  data() {
    return {
      wo: {},
      loading: false,
      submitting: false,
      saving: false,
      editing: false,
      editForm: {},
      fb: { human_problem: '', human_keyword: '' }
    }
  },
  created() { this.load() },
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
    async load() {
      this.loading = true
      try {
        this.wo = await api.getWorkOrder(this.$route.params.orderNo)
      } catch (e) {
        this.$message.error('加载失败: ' + e.message)
      } finally {
        this.loading = false
      }
    },
    async startOrder() {
      try {
        await this.$confirm('确认开始处理该工单？', '确认', { type: 'info' })
        await api.startWorkOrder(this.wo.order_no)
        this.$message.success('工单已标记为处理中')
        this.load()
      } catch (e) {
        if (e !== 'cancel') this.$message.error(e.message || '操作失败')
      }
    },
    async completeOrder() {
      try {
        await this.$confirm('确认标记该工单为已完成？', '确认', { type: 'warning' })
        await api.completeWorkOrder(this.wo.order_no)
        this.$message.success('已标记完成')
        this.load()
      } catch (e) {
        if (e !== 'cancel') this.$message.error(e.message || '操作失败')
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
      this.saving = true
      try {
        await api.updateWorkOrder(this.wo.order_no, this.editForm)
        this.$message.success('工单修改成功')
        this.editing = false
        this.editForm = {}
        this.load()
      } catch (e) {
        this.$message.error(e.message || '保存失败')
      } finally {
        this.saving = false
      }
    },
    async submitFeedback() {
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
