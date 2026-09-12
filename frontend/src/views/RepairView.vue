<template>
  <div class="repair page">
    <div class="repair__head page-head">
      <h2 class="page-title">智能报修</h2>
      <p class="page-desc">描述问题即可自动生成工单，缺失信息系统会主动追问</p>
    </div>

    <section class="console card">
      <!-- 对话区 -->
      <div ref="chatBox" class="chat">
        <!-- 空态 -->
        <div v-if="!messages.length && !orderResult" class="chat__welcome">
          <div class="chat__welcome-icon"><el-icon><Tools /></el-icon></div>
          <h3>您好，请描述遇到的维修问题</h3>
          <p>尽量说清「哪里 + 什么故障」，例如：厨房水斗下水管漏水严重</p>
          <div class="chat__samples">
            <button
              v-for="s in samples"
              :key="s"
              class="sample"
              :disabled="loading"
              @click="useSample(s)"
            >{{ s }}</button>
          </div>
        </div>

        <!-- 消息流 -->
        <div
          v-for="msg in messages"
          :key="msg.id"
          class="msg anim-fade-up"
          :class="msg.role === 'user' ? 'msg--me' : 'msg--ai'"
        >
          <div v-if="msg.role !== 'user'" class="msg__avatar">AI</div>
          <div class="msg__bubble">
            <p class="msg__text">{{ msg.text }}</p>

            <!-- 已识别信息 -->
            <div v-if="msg.chips && msg.chips.length" class="facts">
              <span class="facts__title">已识别信息</span>
              <div class="facts__grid">
                <div v-for="(f, i) in msg.chips" :key="i" class="facts__item">
                  <span class="facts__key">{{ f.label }}</span>
                  <span class="facts__val">{{ f.value }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 思考中 -->
        <div v-if="loading" class="msg msg--ai anim-fade-up">
          <div class="msg__avatar">AI</div>
          <div class="msg__bubble msg__bubble--typing">
            <span>正在分析</span>
            <i class="dot" /><i class="dot" /><i class="dot" />
          </div>
        </div>

        <!-- 工单结果 -->
        <div v-if="orderResult" class="result anim-pop">
          <div class="result__top">
            <div class="result__check">
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5" /></svg>
            </div>
            <div>
              <h3>工单已生成</h3>
              <p>工程师会尽快与您联系，请保持电话畅通</p>
            </div>
            <span class="chip chip--ok">{{ orderResult.order_no }}</span>
          </div>

          <div class="result__grid">
            <div class="kv"><span>受理时间</span><b>{{ orderResult.accept_time || '-' }}</b></div>
            <div class="kv"><span>报修类型</span><b>{{ orderResult.sub_category || '-' }}</b></div>
            <div class="kv"><span>报修项目</span><b>{{ orderResult.problem || '-' }}</b></div>
            <div class="kv">
              <span>优先级</span>
              <b><span class="chip" :class="orderResult.priority === '高' ? 'chip--danger' : 'chip--warn'">{{ orderResult.priority }}</span></b>
            </div>
            <div class="kv"><span>物业公司</span><b>{{ orderResult.property_company || '-' }}</b></div>
            <div class="kv"><span>维修单位</span><b>{{ orderResult.maintenance_unit || '-' }}</b></div>
            <div class="kv"><span>目标部门</span><b>{{ orderResult.target_dept_semantic || '-' }}</b></div>
            <div class="kv">
              <span>指派工人</span>
              <b v-if="orderResult.worker_info">{{ orderResult.worker_info.name }} · {{ orderResult.worker_info.phone || '-' }}</b>
              <b v-else class="muted">待指派</b>
            </div>
            <div class="kv kv--wide"><span>报修地址</span><b>{{ orderResult.address || '-' }}</b></div>
          </div>

          <div class="result__actions">
            <el-button type="primary" @click="newRepair">继续报修</el-button>
            <el-button @click="$router.push(`/order/${orderResult.order_no}`)">查看工单详情</el-button>
          </div>
        </div>
      </div>

      <!-- 输入区 -->
      <div v-if="!orderResult" class="composer">
        <div class="composer__meta">
          <el-input v-model="reporterName" placeholder="报修人（选填）" :disabled="loading" clearable size="default" />
          <el-input v-model="reporterPhone" placeholder="联系电话（选填）" :disabled="loading" clearable size="default" />
        </div>
        <div class="composer__row">
          <el-input
            ref="inputRef"
            v-model="text"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 6 }"
            placeholder="描述您遇到的问题，Enter 发送 / Shift+Enter 换行"
            :disabled="loading"
            @keydown.enter.exact.prevent="send"
          />
          <el-button
            class="composer__send"
            type="primary"
            :loading="loading"
            :disabled="!text.trim()"
            @click="send"
          >
            <span v-if="!loading">发送</span>
          </el-button>
        </div>
        <div class="composer__foot">
          <span>地址不详也可以先提交，系统会引导补充</span>
          <button class="linkbtn" :disabled="loading" @click="reset">重新开始</button>
        </div>
      </div>
    </section>
  </div>
</template>

<script>
import api from '../api'

export default {
  name: 'RepairView',
  data() {
    return {
      userId: 'user_' + Date.now(),
      reporterName: '',
      reporterPhone: '',
      text: '',
      messages: [],   // { role: 'user'|'system', text, chips }
      loading: false,
      orderResult: null,
      sessionAlive: false,
      msgSeq: 0,
      samples: [
        '厨房水斗下水管漏水严重',
        '卫生间马桶堵塞，污水外溢',
        '楼道照明灯不亮',
        '卧室空调制冷效果差'
      ]
    }
  },
  mounted() {
    this.checkExistingSession()
  },
  methods: {
    // 统一出口：给每条消息一个稳定 id，避免用数组下标做 key
    // （下标在列表增删时会错位，导致 Vue 复用错节点、动画串位）
    pushMsg(role, text, chips) {
      this.messages.push({ id: ++this.msgSeq, role, text, chips: chips || [] })
      return this.messages[this.messages.length - 1]
    },

    async checkExistingSession() {
      try {
        const data = await api.getSession(this.userId)
        if (data && data.has_session) {
          this.sessionAlive = true
          this.pushMsg(
            'system',
            `检测到您有一个未完成的报修${data.content ? '，已记录：' + data.content : ''}。请继续补充信息。`,
            data.content ? [{ label: '问题', value: data.content }] : []
          )
        }
      } catch (e) { /* 无会话，忽略 */ }
    },

    // 读取会话中已提取的结构化信息（后端 /converse 的 MISS 分支不返回 input_processor）
    async fetchFacts() {
      try {
        const data = await api.getSessionHistory(this.userId)
        if (!data || !data.has_session) return []
        const chips = []
        if (data.content) chips.push({ label: '问题', value: data.content })
        if (data.address) chips.push({ label: '地址', value: data.address })
        if (data.prechoice_subcategories && data.prechoice_subcategories.length) {
          chips.push({ label: '分类', value: data.prechoice_subcategories.join('、') })
        }
        if (data.trigger_keyword) chips.push({ label: '关键词', value: data.trigger_keyword })
        return chips
      } catch (e) {
        return []
      }
    },

    useSample(s) {
      this.text = s
      this.$nextTick(() => this.$refs.inputRef?.focus())
    },

    async send() {
      const input = this.text.trim()
      if (!input || this.loading) return

      this.messages.push({ role: 'user', text: input })
      this.text = ''
      this.scrollToBottom()

      this.loading = true
      try {
        const data = await api.converse(
          this.userId,
          input,
          this.reporterName || undefined,
          this.reporterPhone || undefined
        )

        if (data.need_more_input) {
          this.sessionAlive = true
          const chips = await this.fetchFacts()
          this.messages.push({
            role: 'system',
            text: data.message_to_user || '还需要补充一点信息才能生成工单。',
            chips
          })
        } else if (data.work_order) {
          const wo = data.work_order
          this.messages.push({
            role: 'system',
            text: '报修已受理，工单信息如下。'
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
        } else {
          this.pushMsg('system', '系统返回了未知结果，请重试或重新开始。')
        }
      } catch (e) {
        this.pushMsg('system', `处理失败：${e.message || '请稍后重试'}。内容已保留在输入框，可直接重发。`)
        // 失败时把刚发的内容放回输入框，避免用户重新打一遍
        if (!this.text.trim()) this.text = input
      } finally {
        this.loading = false
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
      this.msgSeq = 0
      this.text = ''
      this.orderResult = null
      this.sessionAlive = false
      this.$nextTick(() => this.$refs.inputRef?.focus())
    },

    async newRepair() {
      await this.reset()
    },

    scrollToBottom() {
      this.$nextTick(() => {
        const box = this.$refs.chatBox
        if (box) box.scrollTop = box.scrollHeight
      })
    }
  }
}
</script>

<style scoped>
.repair {
  max-width: 900px;
  margin: 0 auto;
}

.console {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ---------- 对话区 ---------- */
.chat {
  flex: 1;
  min-height: 340px;
  max-height: min(58vh, 560px);
  overflow-y: auto;
  padding: 22px 22px 8px;
  background:
    radial-gradient(circle at 12% 8%, rgba(99, 102, 241, 0.05), transparent 42%),
    radial-gradient(circle at 88% 0%, rgba(139, 92, 246, 0.05), transparent 40%),
    #fbfcfe;
  scroll-behavior: smooth;
}

.chat__welcome {
  padding: 34px 10px 30px;
  text-align: center;
  animation: fade-up 0.4s var(--ease) both;
}
.chat__welcome-icon {
  font-size: 30px;
  margin-bottom: 10px;
}
.chat__welcome h3 {
  font-size: 16px;
  margin-bottom: 6px;
}
.chat__welcome p {
  color: var(--ink-500);
  font-size: 13px;
}
.chat__samples {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  margin-top: 18px;
}
.sample {
  padding: 7px 13px;
  border: 1px solid var(--line);
  border-radius: 99px;
  background: #fff;
  color: var(--ink-700);
  font: inherit;
  font-size: 12.5px;
  cursor: pointer;
  transition: all 0.18s var(--ease);
}
.sample:hover {
  border-color: var(--brand);
  color: var(--brand);
  background: var(--brand-soft);
  transform: translateY(-1px);
}

/* ---------- 消息 ---------- */
.msg {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}
.msg--me { justify-content: flex-end; }

.msg__avatar {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  flex: none;
  border-radius: 9px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.msg__bubble {
  max-width: 78%;
  padding: 11px 15px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid var(--line);
  box-shadow: var(--shadow-sm);
  font-size: 14px;
  line-height: 1.65;
  word-break: break-word;
}
.msg--me .msg__bubble {
  background: linear-gradient(135deg, #4f46e5, #6366f1);
  border-color: transparent;
  color: #fff;
  border-bottom-right-radius: 6px;
  box-shadow: 0 6px 16px rgba(79, 70, 229, 0.24);
}
.msg--ai .msg__bubble { border-bottom-left-radius: 6px; }

.msg__text { white-space: pre-wrap; }

.msg__bubble--typing {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--ink-500);
  font-size: 13px;
}
.dot {
  width: 5px;
  height: 5px;
  border-radius: 99px;
  background: var(--ink-400);
  animation: blink 1.1s ease-in-out infinite;
}
.dot:nth-child(2) { animation-delay: 0.1s; }
.dot:nth-child(3) { animation-delay: 0.2s; }
.dot:nth-child(4) { animation-delay: 0.3s; }

/* 已识别信息 */
.facts {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--line);
}
.facts__title {
  display: block;
  margin-bottom: 7px;
  color: var(--ok);
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: 0.03em;
}
.facts__grid { display: grid; gap: 6px; }
.facts__item {
  display: flex;
  gap: 8px;
  font-size: 13px;
}
.facts__key {
  flex: none;
  min-width: 52px;
  color: var(--ink-400);
}
.facts__val { color: var(--ink-800); word-break: break-word; }

/* ---------- 结果卡 ---------- */
.result {
  margin: 6px 0 16px;
  padding: 20px;
  border: 1px solid #a7f3d0;
  border-radius: var(--r-lg);
  background: linear-gradient(180deg, #f0fdf6, #ffffff);
}
.result__top {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.result__check {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  flex: none;
  border-radius: 12px;
  background: var(--ok);
  color: #fff;
  box-shadow: 0 6px 16px rgba(16, 185, 129, 0.32);
  animation: pop-in 0.4s var(--ease) both;
}
.result__top h3 { font-size: 15px; }
.result__top p { color: var(--ink-500); font-size: 12.5px; }
.result__top .chip { margin-left: auto; font-family: ui-monospace, Consolas, monospace; }

.result__grid {
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
  gap: 10px;
  padding: 10px 14px;
  background: #fff;
  font-size: 13px;
}
.kv--wide { grid-column: 1 / -1; }
.kv span { flex: none; width: 68px; color: var(--ink-400); font-size: 12.5px; }
.kv b { font-weight: 500; color: var(--ink-800); word-break: break-word; }
.muted { color: var(--ink-400) !important; font-weight: 400 !important; }

.result__actions {
  display: flex;
  gap: 10px;
  margin-top: 16px;
}

/* ---------- 输入区 ---------- */
.composer {
  border-top: 1px solid var(--line-soft);
  padding: 14px 18px 16px;
  background: #fff;
}
.composer__meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 10px;
}
.composer__row {
  display: flex;
  align-items: flex-end;
  gap: 10px;
}
.composer__send {
  height: 42px;
  min-width: 88px;
  border-radius: var(--r-md);
}
.composer__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 9px;
  color: var(--ink-400);
  font-size: 12px;
}
.linkbtn {
  border: 0;
  background: none;
  color: var(--ink-500);
  font: inherit;
  font-size: 12px;
  cursor: pointer;
  padding: 0;
  transition: color 0.18s var(--ease);
}
.linkbtn:hover { color: var(--brand); }

@media (max-width: 720px) {
  .msg__bubble { max-width: 88%; }
  .result__grid { grid-template-columns: 1fr; }
  .composer__meta { grid-template-columns: 1fr; }
}
</style>
