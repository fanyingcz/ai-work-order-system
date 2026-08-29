<template>
  <div class="login-container">
    <el-card class="login-card">
      <template #header>
        <div class="login-header">
          <h2>🔧 维修工人工作台</h2>
          <p class="sub-title">请使用您的姓名和工人ID登录</p>
        </div>
      </template>

      <el-form :model="form" :rules="rules" ref="formRef" label-width="0" size="large">
        <el-form-item prop="worker_name">
          <el-input
            v-model="form.worker_name"
            placeholder="请输入工人姓名（如：张三）"
            :prefix-icon="User"
            clearable
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入工人ID（如：1）"
            :prefix-icon="Lock"
            show-password
            clearable
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            style="width: 100%"
            :loading="loading"
            @click="handleLogin"
          >
            登 录
          </el-button>
        </el-form-item>
      </el-form>

      <div class="login-tips">
        <el-alert
          type="info"
          :closable="false"
          show-icon
          title="登录说明"
          description="用户名：工人姓名（workers 表中的 name 字段）；密码：工人ID（workers 表中的 id 字段）"
        />
      </div>
    </el-card>
  </div>
</template>

<script>
import { User, Lock } from '@element-plus/icons-vue'
import api from '../api'

export default {
  name: 'LoginView',
  data() {
    return {
      form: {
        worker_name: '',
        password: ''
      },
      rules: {
        worker_name: [{ required: true, message: '请输入工人姓名', trigger: 'blur' }],
        password: [{ required: true, message: '请输入工人ID', trigger: 'blur' }]
      },
      loading: false,
      User,
      Lock
    }
  },
  methods: {
    async handleLogin() {
      try {
        await this.$refs.formRef.validate()
      } catch (e) {
        return
      }

      this.loading = true
      try {
        const data = await api.workerLogin(this.form.worker_name.trim(), this.form.password.trim())
        // 保存工人信息到 localStorage
        localStorage.setItem('worker_token', String(data.worker.id))
        localStorage.setItem('worker_info', JSON.stringify(data.worker))
        this.$message.success(data.message || '登录成功')
        this.$router.push('/orders')
      } catch (e) {
        this.$message.error(e.message || '登录失败')
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.login-card {
  width: 420px;
  max-width: 100%;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.login-header {
  text-align: center;
}

.login-header h2 {
  margin: 0 0 8px;
  color: #303133;
}

.sub-title {
  color: #909399;
  font-size: 13px;
  margin: 0;
}

.login-tips {
  margin-top: 20px;
}

.login-tips .el-alert {
  font-size: 12px;
}
</style>