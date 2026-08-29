<template>
  <el-container style="min-height: 100vh">
    <el-header style="background: #409EFF; color: white; display: flex; align-items: center; padding: 0 20px">
      <h2 style="margin: 0; cursor: pointer" @click="$router.push('/')">🏠 智能工单系统</h2>
      <span style="flex:1"></span>
      <el-tag type="warning" v-if="!online" style="margin-right:10px">后端未连接</el-tag>
    </el-header>
    <el-container>
      <el-aside width="200px" style="background: #f5f7fa">
        <el-menu :default-active="$route.path" router style="border-right:none">
          <el-menu-item index="/">
            <el-icon><Edit /></el-icon>
            <span>智能报修</span>
          </el-menu-item>
          <el-menu-item index="/orders">
            <el-icon><List /></el-icon>
            <span>工单管理</span>
          </el-menu-item>
          <el-menu-item index="/feedback">
            <el-icon><ChatDotSquare /></el-icon>
            <span>反馈管理</span>
          </el-menu-item>
          <el-menu-item index="/test">
            <el-icon><Cpu /></el-icon>
            <span>模型测试</span>
          </el-menu-item>
          <el-menu-item index="/dashboard">
            <el-icon><DataAnalysis /></el-icon>
            <span>仪表盘</span>
          </el-menu-item>
          <el-menu-item index="/database">
            <el-icon><Coin /></el-icon>
            <span>数据库管理</span>
          </el-menu-item>
          <el-menu-item index="/prompts">
            <el-icon><Setting /></el-icon>
            <span>提示词管理</span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script>
import api from './api'

export default {
  data() {
    return { online: false }
  },
  async mounted() {
    try {
      await api.healthCheck()
      this.online = true
    } catch (e) {
      this.online = false
    }
  }
}
</script>