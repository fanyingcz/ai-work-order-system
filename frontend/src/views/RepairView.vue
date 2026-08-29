<template>
  <div style="max-width: 700px; margin: 0 auto">
    <h2>智能报修</h2>
    <p style="color: #909399; margin-bottom: 16px">
      请描述您的报修问题，系统将逐步引导您完成工单提交
    </p>

    <!-- 对话区域 -->
    <div ref="chatBox" class="chat-box">
      <!-- 系统欢迎消息 -->
      <div v-if="messages.length === 0" class="chat-msg system">
        <div class="msg-bubble system">
          👋 您好！请描述您遇到的维修问题，我会帮您生成工单。
          <br />例如：<em>"厨房水斗下水管漏水严重"</em>
          <br />如果您知道报修人姓名和电话也请一并告知。
        </div>
      </div>

      <!-- 对话消息列表 -->
      <div v-for="(msg, idx) in messages" :key="idx" :class="['chat-msg', msg.role]">
        <div v-if="msg.role === 'user'" class="msg-bubble user">{{ msg.text }}</div>
        <div v-else class="msg-bubble system" v-html="msg.html || msg.text"></div>
      </div>

      <!-- 加载动画 -->
      <div v-if="loading" class="chat-msg system">
        <div class="msg-bubble system typing">AI 正在分析中{{ typingDots }}</div>
      </div>

      <!-- 结果卡片（工单已生成） -->
      <div v-if="orderResult" class="chat-msg system">
        <div class="msg-bubble system" style="max-width: 100%">
          <el-result icon="success" title="工单已生成！" style="padding: 12px 0">
            <template #sub-title>
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="工单号">
                  <el-tag type="success">{{ orderResult.order_no }}</el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="受理时间">{{ orderResult.accept_time }}</el-descriptions-item>
                <el-descriptions-item label="报修类型">{{ orderResult.sub_category }}</el-descriptions-item>
                <el-descriptions-item label="报修项目">{{ orderResult.problem }}</el-descriptions-item>
                <el-descriptions-item label="优先级">
                  <el-tag :type="orderResult.priority === '高' ? 'danger' : 'warning'">{{ orderResult.priority }}</el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="目标部门">{{ orderResult.target_dept_semantic || '-' }}</el-descriptions-item>
                <el-descriptions-item label="物业公司">{{ orderResult.property_company }}</el-descriptions-item>
                <el-descriptions-item label="维修单位">{{ orderResult.maintenance_unit }}</el-descriptions-item>
                <el-descriptions-item label="指派工人" v-if="orderResult.worker_info">
                  <el-tag type="success">{{ orderResult.worker_info.name }}</el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="工人电话" v-if="orderResult.worker_info">
                  {{ orderResult.worker_info.phone }}
                </el-descriptions-item>
                <el-descriptions-item label="报修地址" :span="2">{{ orderResult.address || '-' }}</el-descriptions-item>
              </el-descriptions>
            </template>
            <template #extra>
              <el-button type="primary" @click="newRepair">继续报修</el-button>
              <el-button @click="$router.push(`/order/${orderResult.order_no}`)">查看详情</el-button>
            </template>
          </el-result>
        </div>
      </div>
    </div>

    <!-- 输入区域 -->
    <div class="input-area" v-if="!orderResult">
      <div style="display:flex; gap:12px; margin-bottom:10px">
        <el-input
          v-model="reporterName"
          placeholder="报修人姓名（选填）"
          size="default"
          :disabled="loading"
          style="flex:1"
          clearable
        />
        <el-input
          v-model="reporterPhone"
          placeholder="联系电话（选填）"
          size="default"
          :disabled="loading"
          style="flex:1"
          clearable
        />
      </div>
      <el-input
        ref="inputRef"
        v-model="text"
        type="textarea"
        :autosize="{ minRows: 3, maxRows: 8 }"
        placeholder="请输入您的报修问题..."
        size="large"
        @keyup.enter.exact="send"
        :disabled="loading"
      />
      <el-button
        type="primary"
        size="large"
        @click="send"
        :loading="loading"
        :disabled="!text.trim()"
        style="margin-top:8px;width:100%"
      >
        发送
      </el-button>
      <div style="margin-top: 8px; display: flex; gap: 12px; align-items: center">
        <span style="font-size: 12px; color: #909399">
          提示：如果不知道地址可以先描述问题，系统会引导您补充
        </span>
        <span style="flex: 1"></span>
        <el-button size="small" @click="reset" :disabled="loading" text type="info">重新开始</el-button>
      </div>
    </div>
  </div>
</template>

<script>
import api from '../api'

export default {
  data() {
    return {
      userId: 'user_' + Date.now(),
      reporterName: '',
      reporterPhone: '',
      text: '',
      messages: [],        // { role: 'user'|'system', text, html }
      loading: false,
      orderResult: null,
      typingTimer: null,
      typingDots: '',
      sessionAlive: false
    }
  },
  mounted() {
    // 尝试恢复已有会话
    this.checkExistingSession()
  },
  beforeUnmount() {
    if (this.typingTimer) clearInterval(this.typingTimer)
  },
  methods: {
    async checkExistingSession() {
      try {
        const data = await api.getSession(this.userId)
        if (data.has_session) {
          this.sessionAlive = true
          this.messages.push({
            role: 'system',
            text: `您之前有一个进行中的报修，已记录的问题为：<b>${data.content || '(空)'}</b>。请继续补充信息。`
          })
        }
      } catch (e) { /* ignore */ }
    },

    async send() {
      const input = this.text.trim()
      if (!input || this.loading) return

      // 添加用户消息
      this.messages.push({ role: 'user', text: input })
      this.text = ''
      this.scrollToBottom()

      this.loading = true
      this.startTyping()

      try {
        const data = await api.converse(this.userId, input, this.reporterName || undefined, this.reporterPhone || undefined)

        if (data.need_more_input) {
          this.sessionAlive = true
          // 构建系统回复，展示已提取的信息
          const ip = data.input_processor || {}
          let html = data.message_to_user || '请补充您的地址信息'
          html += '<div style="margin-top:8px;font-size:12px;color:#67C23A">'
          html += '✅ 已识别以下信息：'
          html += '<ul style="margin:4px 0;padding-left:16px">'
          if (data.content) html += `<li>问题：${this.escapeHtml(data.content)}</li>`
          if (ip.prechoice_subcategories && ip.prechoice_subcategories.length > 0) {
            html += `<li>分类：${ip.prechoice_subcategories.join('、')}</li>`
          }
          if (ip.reporter_name) html += `<li>报修人：${this.escapeHtml(ip.reporter_name)}</li>`
          if (ip.reporter_phone) html += `<li>联系电话：${this.escapeHtml(ip.reporter_phone)}</li>`
          if (ip.address) html += `<li>地址：${this.escapeHtml(ip.address)}</li>`
          if (ip.location) html += `<li>位置：${this.escapeHtml(ip.location)}</li>`
          html += '</ul></div>'
          this.messages.push({ role: 'system', html, text: data.message_to_user })
        } else if (data.work_order) {
          // 成功
          const wo = data.work_order
          this.messages.push({
            role: 'system',
            html: `
              <p>✅ 您的报修申请已成功提交。</p>
              <p>工程师将尽快与您电话联系，请保持手机畅通。后续工单进展我们会持续跟进，感谢您的耐心等待。</p>
              <p style="color:#909399;font-size:12px">工单号：${this.escapeHtml(wo.order_no)}</p>
            `,
            text: '工单已生成'
          })
          this.orderResult = {
            order_no: wo.order_no,
            accept_time: wo.accept_time,
            sub_category: wo.sub_category,
            problem: wo.problem,
            priority: wo.priority,
            target_dept_semantic: wo.target_dept_semantic || '-',
            property_company: wo.property_company,
            maintenance_unit: wo.maintenance_unit,
            address: wo.address || '-',
            worker_info: wo.worker_info || null
          }
        }
      } catch (e) {
        this.messages.push({
          role: 'system',
          text: `❌ 处理失败：${e.message || '请稍后重试'}`
        })
      } finally {
        this.loading = false
        this.stopTyping()
        this.scrollToBottom()
        this.$nextTick(() => this.$refs.inputRef?.focus())
      }
    },

    async reset() {
      try { await api.cancelSession(this.userId) } catch (e) { /* ignore */ }
      this.userId = 'user_' + Date.now()
      this.reporterName = ''
      this.reporterPhone = ''
      this.messages = []
      this.text = ''
      this.orderResult = null
      this.sessionAlive = false
      this.$nextTick(() => this.$refs.inputRef?.focus())
    },

    async newRepair() {
      try { await api.cancelSession(this.userId) } catch (e) { /* ignore */ }
      this.userId = 'user_' + Date.now()
      this.reporterName = ''
      this.reporterPhone = ''
      this.messages = []
      this.text = ''
      this.orderResult = null
      this.sessionAlive = false
    },

    startTyping() {
      this.typingDots = ''
      let dots = 0
      this.typingTimer = setInterval(() => {
        dots = (dots + 1) % 4
        this.typingDots = '.'.repeat(dots)
      }, 400)
    },

    stopTyping() {
      if (this.typingTimer) {
        clearInterval(this.typingTimer)
        this.typingTimer = null
      }
      this.typingDots = ''
    },

    scrollToBottom() {
      this.$nextTick(() => {
        const box = this.$refs.chatBox
        if (box) box.scrollTop = box.scrollHeight
      })
    },

    escapeHtml(str) {
      if (!str) return ''
      return str.replace(/&/g, '&').replace(/</g, '<').replace(/>/g, '>')
    }
  }
}
</script>

<style scoped>
.chat-box {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 16px;
  min-height: 300px;
  max-height: 500px;
  overflow-y: auto;
  background: #f9fafb;
  margin-bottom: 16px;
}

.chat-msg {
  display: flex;
  margin-bottom: 12px;
}
.chat-msg.user {
  justify-content: flex-end;
}
.chat-msg.system {
  justify-content: flex-start;
}

.msg-bubble {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}
.msg-bubble.user {
  background: #409EFF;
  color: white;
  border-bottom-right-radius: 4px;
}
.msg-bubble.system {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-bottom-left-radius: 4px;
}
.msg-bubble.typing {
  color: #909399;
  font-style: italic;
}

.msg-bubble.system ul {
  margin: 4px 0;
  padding-left: 18px;
}
.msg-bubble.system li {
  margin: 2px 0;
}

.input-area {
  position: sticky;
  bottom: 0;
  background: white;
  padding-top: 8px;
}
</style>