<template>
  <div class="login">
    <div class="login__panel card anim-fade-up">
      <div class="login__brand">
        <div class="login__logo">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
          </svg>
        </div>
        <div>
          <h1>维修工人工作台</h1>
          <p>使用姓名与工人 ID 登录</p>
        </div>
      </div>

      <el-form :model="form" :rules="rules" ref="formRef" size="large" @submit.prevent>
        <el-form-item prop="worker_name">
          <el-input
            v-model="form.worker_name"
            placeholder="工人姓名，如 张三"
            :prefix-icon="User"
            clearable
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="工人 ID，如 1"
            :prefix-icon="Lock"
            show-password
            clearable
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-form-item class="login__submit">
          <el-button type="primary" size="large" :loading="loading" @click="handleLogin">
            {{ loading ? '登录中' : '登 录' }}
          </el-button>
        </el-form-item>
      </el-form>

      <p class="login__tip">账号信息由物业管理员在「人员管理」中维护</p>
    </div>
  </div>
</template>

<script>
import { User, Lock } from '@element-plus/icons-vue'
import api from '../api'

export default {
  name: 'LoginView',
  data() {
    return {
      form: { worker_name: '', password: '' },
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
.login {
  display: grid;
  place-items: center;
  min-height: 100vh;
  padding: 20px;
  background:
    radial-gradient(circle at 15% 15%, rgba(99, 102, 241, 0.28), transparent 45%),
    radial-gradient(circle at 85% 10%, rgba(139, 92, 246, 0.25), transparent 40%),
    linear-gradient(160deg, #101935 0%, #0b1224 100%);
}

.login__panel {
  width: 400px;
  max-width: 100%;
  padding: 30px 28px 24px;
  border: 0;
  box-shadow: var(--shadow-lg);
}

.login__brand {
  display: flex;
  align-items: center;
  gap: 13px;
  margin-bottom: 24px;
}
.login__logo {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  flex: none;
  border-radius: 13px;
  color: #fff;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  box-shadow: 0 8px 20px rgba(99, 102, 241, 0.4);
}
.login__brand h1 { font-size: 17px; }
.login__brand p { margin-top: 2px; color: var(--ink-500); font-size: 12.5px; }

.login__submit { margin-bottom: 0; }
.login__submit :deep(.el-button) { width: 100%; height: 44px; border-radius: var(--r-md); }

.login__tip {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px dashed var(--line);
  color: var(--ink-400);
  font-size: 12px;
  text-align: center;
}
</style>
