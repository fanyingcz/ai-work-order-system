<template>
  <div class="page">
    <div class="page-head pm-head">
      <div>
        <h2 class="page-title">提示词管理</h2>
        <p class="page-desc">版本 {{ promptsData.version || '-' }} · 修改后需热重载才会对运行中的服务生效</p>
      </div>
      <div class="pm-head__actions">
        <el-button type="success" size="small" plain @click="reloadPrompts" :loading="reloading">热重载</el-button>
        <el-button :type="readOnly ? 'warning' : 'danger'" size="small" plain @click="toggleEdit">
          {{ readOnly ? '启用编辑' : '锁定编辑' }}
        </el-button>
      </div>
    </div>

    <div v-if="loading" class="card card--pad loading-box">
      <el-icon class="is-loading" :size="26"><Loading /></el-icon>
      <p>正在加载提示词配置…</p>
    </div>

    <div v-else class="card">
      <div class="tabs">
        <button
          v-for="t in tabs"
          :key="t.key"
          class="tab"
          :class="{ 'is-active': activeTab === t.key }"
          @click="activeTab = t.key"
        >{{ t.label }}</button>
      </div>

      <div class="card-body pm-body">
        <!-- Step1 -->
        <div v-show="activeTab === 'step1'" class="anim-fade-up">
          <section class="section">
            <header class="section__head">
              <h4>系统角色</h4>
              <el-button size="small" type="primary" :disabled="readOnly" @click="saveField('step1.system_role', editStep1.system_role)">保存</el-button>
            </header>
            <el-input v-model="editStep1.system_role" type="textarea" :rows="3" :disabled="readOnly" />
          </section>

          <section class="section">
            <header class="section__head">
              <h4>思考步骤 · {{ editStep1.thinking_steps.length }} 条</h4>
              <div class="section__tools">
                <el-button size="small" v-if="!readOnly" @click="editStep1.thinking_steps.push('')">添加</el-button>
                <el-button size="small" type="primary" v-if="!readOnly" @click="saveField('step1.thinking_steps', editStep1.thinking_steps)">保存全部</el-button>
              </div>
            </header>
            <div v-for="(step, i) in editStep1.thinking_steps" :key="'ts-' + i" class="row">
              <span class="row__idx">{{ i + 1 }}</span>
              <el-input v-model="editStep1.thinking_steps[i]" type="textarea" :rows="2" :disabled="readOnly" />
              <el-button v-if="!readOnly" size="small" type="danger" plain @click="removeArrayItem(editStep1.thinking_steps, i)">删除</el-button>
            </div>
          </section>

          <section class="section">
            <header class="section__head">
              <h4>任务列表 · {{ Object.keys(editStep1.tasks).length }} 条</h4>
            </header>
            <div v-for="(val, key) in editStep1.tasks" :key="'tk-' + key" class="row">
              <span class="row__key">{{ key }}</span>
              <el-input v-model="editStep1.tasks[key]" type="textarea" :rows="2" :disabled="readOnly" />
              <el-button size="small" type="primary" v-if="!readOnly" @click="saveTask(key, editStep1.tasks[key])">保存</el-button>
            </div>
            <div v-if="!readOnly" class="row row--new">
              <el-input v-model="newTaskKey" placeholder="键名，如 task5" size="small" class="row__newkey" />
              <el-input v-model="newTaskValue" placeholder="任务描述" size="small" />
              <el-button size="small" type="success" @click="addTask">添加任务</el-button>
            </div>
          </section>

          <section class="section">
            <header class="section__head">
              <h4>注意事项 · {{ editStep1.notes.length }} 条</h4>
              <div class="section__tools">
                <el-button size="small" v-if="!readOnly" @click="editStep1.notes.push('')">添加</el-button>
                <el-button size="small" type="primary" v-if="!readOnly" @click="saveField('step1.notes', editStep1.notes)">保存全部</el-button>
              </div>
            </header>
            <div v-for="(note, i) in editStep1.notes" :key="'nt-' + i" class="row">
              <span class="row__idx">{{ i + 1 }}</span>
              <el-input v-model="editStep1.notes[i]" type="textarea" :rows="2" :disabled="readOnly" />
              <el-button v-if="!readOnly" size="small" type="danger" plain @click="removeArrayItem(editStep1.notes, i)">删除</el-button>
            </div>
          </section>
        </div>

        <!-- Step2 -->
        <div v-show="activeTab === 'step2'" class="anim-fade-up">
          <section class="section">
            <header class="section__head">
              <h4>系统角色</h4>
              <el-button size="small" type="primary" :disabled="readOnly" @click="saveField('step2.system_role', editStep2.system_role)">保存</el-button>
            </header>
            <el-input v-model="editStep2.system_role" type="textarea" :rows="3" :disabled="readOnly" />
          </section>

          <section class="section">
            <header class="section__head">
              <h4>思考步骤</h4>
              <el-button size="small" type="primary" :disabled="readOnly" @click="saveThinkingSteps">保存</el-button>
            </header>
            <div class="row">
              <span class="row__key">第1步</span>
              <el-input v-model="editStep2.thinking_step1_description" size="small" :disabled="readOnly" />
            </div>
            <div class="row">
              <span class="row__key">第2步</span>
              <el-input v-model="editStep2.thinking_step2_description" size="small" :disabled="readOnly" />
            </div>
          </section>

          <section class="section">
            <header class="section__head">
              <h4>分类规则 · {{ editStep2.classification_rules.length }} 条</h4>
            </header>
            <div v-for="(rule, i) in editStep2.classification_rules" :key="'cr-' + i" class="row">
              <span class="row__idx">#{{ i }}</span>
              <el-input v-model="editStep2.classification_rules[i]" type="textarea" :rows="2" :disabled="readOnly" />
              <div v-if="!readOnly" class="row__ops">
                <el-button size="small" type="primary" @click="saveRule(i, editStep2.classification_rules[i])">保存</el-button>
                <el-button size="small" type="danger" plain @click="deleteRule(i)">删除</el-button>
              </div>
            </div>
            <div v-if="!readOnly" class="row row--new">
              <span class="row__idx row__idx--new">NEW</span>
              <el-input v-model="newRuleText" placeholder="输入新规则文本…" type="textarea" :rows="2" />
              <el-button size="small" type="success" @click="addRule">添加</el-button>
            </div>
          </section>

          <section class="section">
            <header class="section__head">
              <h4>输出要求 · {{ editStep2.requirements.length }} 条</h4>
              <div class="section__tools">
                <el-button size="small" v-if="!readOnly" @click="editStep2.requirements.push('')">添加</el-button>
                <el-button size="small" type="primary" v-if="!readOnly" @click="saveField('step2.requirements', editStep2.requirements)">保存全部</el-button>
              </div>
            </header>
            <div v-for="(req, i) in editStep2.requirements" :key="'rq-' + i" class="row row--tight">
              <span class="row__idx">{{ i + 1 }}</span>
              <el-input v-model="editStep2.requirements[i]" size="small" :disabled="readOnly" />
              <el-button v-if="!readOnly" size="small" type="danger" plain @click="removeArrayItem(editStep2.requirements, i)">删除</el-button>
            </div>
          </section>

          <section class="section">
            <header class="section__head">
              <h4>位置选择提示模板</h4>
              <el-button size="small" type="primary" :disabled="readOnly" @click="saveField('step2.location_selection_prompt', editStep2.location_selection_prompt)">保存</el-button>
            </header>
            <el-input v-model="editStep2.location_selection_prompt" type="textarea" :rows="3" :disabled="readOnly" />
          </section>

          <section class="section">
            <header class="section__head">
              <h4>位置选择要求 · {{ editStep2.location_requirements.length }} 条</h4>
              <div class="section__tools">
                <el-button size="small" v-if="!readOnly" @click="editStep2.location_requirements.push('')">添加</el-button>
                <el-button size="small" type="primary" v-if="!readOnly" @click="saveField('step2.location_requirements', editStep2.location_requirements)">保存全部</el-button>
              </div>
            </header>
            <div v-for="(lr, i) in editStep2.location_requirements" :key="'lr-' + i" class="row row--tight">
              <span class="row__idx">{{ i + 1 }}</span>
              <el-input v-model="editStep2.location_requirements[i]" size="small" :disabled="readOnly" />
              <el-button v-if="!readOnly" size="small" type="danger" plain @click="removeArrayItem(editStep2.location_requirements, i)">删除</el-button>
            </div>
          </section>
        </div>

        <!-- JSON -->
        <div v-show="activeTab === 'json'" class="anim-fade-up">
          <div class="json-bar">
            <el-button size="small" type="primary" @click="copyJson">复制 JSON</el-button>
            <span class="card-head__hint">只读预览，反映当前页面编辑内容</span>
          </div>
          <pre class="json-view">{{ jsonPreview }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import api from '../api/index.js'

const readOnly = ref(true)
const loading = ref(true)
const reloading = ref(false)
const activeTab = ref('step1')
const promptsData = ref({})
const newRuleText = ref('')
const newTaskKey = ref('')
const newTaskValue = ref('')

const tabs = [
  { key: 'step1', label: 'Step1 · 类别选取' },
  { key: 'step2', label: 'Step2 · 关键词匹配' },
  { key: 'json', label: 'JSON 原始数据' }
]

const editStep1 = reactive({
  system_role: '',
  thinking_steps: [],
  tasks: {},
  notes: []
})

const editStep2 = reactive({
  system_role: '',
  thinking_step1_description: '',
  thinking_step2_description: '',
  classification_rules: [],
  requirements: [],
  location_selection_prompt: '',
  location_requirements: []
})

const jsonPreview = computed(() => {
  const data = {
    version: promptsData.value.version || '1.0.0',
    description: promptsData.value.description || '',
    step1: {
      system_role: editStep1.system_role,
      thinking_steps: [...editStep1.thinking_steps],
      tasks: { ...editStep1.tasks },
      notes: [...editStep1.notes]
    },
    step2: {
      system_role: editStep2.system_role,
      thinking_step1_description: editStep2.thinking_step1_description,
      thinking_step2_description: editStep2.thinking_step2_description,
      classification_rules: [...editStep2.classification_rules],
      requirements: [...editStep2.requirements],
      location_selection_prompt: editStep2.location_selection_prompt,
      location_requirements: [...editStep2.location_requirements]
    }
  }
  return JSON.stringify(data, null, 2)
})

function toggleEdit() {
  readOnly.value = !readOnly.value
}

function syncFromData(data) {
  const src = data || {}
  promptsData.value = src
  const s1 = src.step1 || {}
  editStep1.system_role = s1.system_role || ''
  editStep1.thinking_steps = [...(s1.thinking_steps || [])]
  editStep1.tasks = { ...(s1.tasks || {}) }
  editStep1.notes = [...(s1.notes || [])]

  const s2 = src.step2 || {}
  editStep2.system_role = s2.system_role || ''
  editStep2.thinking_step1_description = s2.thinking_step1_description || ''
  editStep2.thinking_step2_description = s2.thinking_step2_description || ''
  editStep2.classification_rules = [...(s2.classification_rules || [])]
  editStep2.requirements = [...(s2.requirements || [])]
  editStep2.location_selection_prompt = s2.location_selection_prompt || ''
  editStep2.location_requirements = [...(s2.location_requirements || [])]
}

async function refreshAll() {
  loading.value = true
  try {
    const data = await api.getPrompts()
    syncFromData(data)
  } catch (e) {
    ElMessage.error('加载失败: ' + (e.message || e))
  } finally {
    loading.value = false
  }
}

async function reloadPrompts() {
  reloading.value = true
  try {
    await api.reloadPrompts()
    // 重载后回读最新配置，避免页面停留在旧内容
    await refreshAll()
    ElMessage.success('提示词配置已热重载，运行中的服务已生效')
  } catch (e) {
    ElMessage.error('重载失败: ' + (e.message || e))
  } finally {
    reloading.value = false
  }
}

async function saveField(path, value) {
  try {
    await api.updatePromptField(path, value)
    ElMessage.success(`「${path}」已保存`)
    ElMessage.info('点击「热重载」后生效', 2000)
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.message || e))
  }
}

async function saveTask(key, value) {
  try {
    await api.updateStep1Task(key, value)
    ElMessage.success(`任务「${key}」已保存`)
    ElMessage.info('点击「热重载」后生效', 2000)
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.message || e))
  }
}

async function addTask() {
  if (!newTaskKey.value.trim() || !newTaskValue.value.trim()) {
    ElMessage.warning('请输入键名和描述')
    return
  }
  try {
    await api.updateStep1Task(newTaskKey.value.trim(), newTaskValue.value.trim())
    editStep1.tasks[newTaskKey.value.trim()] = newTaskValue.value.trim()
    newTaskKey.value = ''
    newTaskValue.value = ''
    ElMessage.success('新任务已添加')
  } catch (e) {
    ElMessage.error('添加失败: ' + (e.message || e))
  }
}

async function saveThinkingSteps() {
  try {
    await api.updatePromptField('step2.thinking_step1_description', editStep2.thinking_step1_description)
    await api.updatePromptField('step2.thinking_step2_description', editStep2.thinking_step2_description)
    ElMessage.success('思考步骤已保存')
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.message || e))
  }
}

async function saveRule(index, ruleText) {
  try {
    await api.updateStep2Rule(index, ruleText)
    ElMessage.success(`规则 #${index} 已保存`)
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.message || e))
  }
}

async function addRule() {
  if (!newRuleText.value.trim()) {
    ElMessage.warning('请输入规则文本')
    return
  }
  try {
    await api.addStep2Rule(newRuleText.value.trim())
    editStep2.classification_rules.push(newRuleText.value.trim())
    newRuleText.value = ''
    ElMessage.success('规则已添加')
  } catch (e) {
    ElMessage.error('添加失败: ' + (e.message || e))
  }
}

async function deleteRule(index) {
  try {
    await ElMessageBox.confirm(`确定要删除规则 #${index}？`, '确认删除', { type: 'warning' })
    await api.deleteStep2Rule(index)
    editStep2.classification_rules.splice(index, 1)
    ElMessage.success('规则已删除')
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败: ' + (e.message || e))
    }
  }
}

function removeArrayItem(arr, index) {
  arr.splice(index, 1)
}

async function copyJson() {
  try {
    await navigator.clipboard.writeText(jsonPreview.value)
    ElMessage.success('JSON 已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
}

onMounted(() => {
  refreshAll()
})
</script>

<style scoped>
.pm-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.pm-head__actions { display: flex; gap: 8px; }

.loading-box {
  display: grid;
  place-items: center;
  gap: 10px;
  padding: 56px;
  color: var(--ink-500);
}

.tabs {
  display: flex;
  gap: 4px;
  padding: 10px 18px 0;
  border-bottom: 1px solid var(--line-soft);
}
.tab {
  position: relative;
  padding: 8px 14px 12px;
  border: 0;
  background: none;
  color: var(--ink-500);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
  transition: color 0.18s var(--ease);
}
.tab:hover { color: var(--ink-800); }
.tab.is-active { color: var(--brand); font-weight: 600; }
.tab.is-active::after {
  content: '';
  position: absolute;
  left: 14px;
  right: 14px;
  bottom: -1px;
  height: 2px;
  border-radius: 2px;
  background: var(--brand);
}

.pm-body { display: grid; gap: 26px; }

.section { display: grid; gap: 10px; }
.section__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--line-soft);
}
.section__head h4 { font-size: 13.5px; color: var(--ink-900); }
.section__tools { display: flex; gap: 8px; }

.row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}
.row--tight { align-items: center; }
.row--new { margin-top: 4px; }
.row__idx {
  flex: none;
  min-width: 34px;
  padding-top: 6px;
  color: var(--ink-400);
  font-size: 12.5px;
  font-weight: 600;
  text-align: right;
}
.row__idx--new { color: var(--ok); }
.row__key {
  flex: none;
  min-width: 72px;
  padding-top: 6px;
  color: var(--brand);
  font-size: 12.5px;
  font-weight: 600;
}
.row--tight .row__idx, .row--tight .row__key { padding-top: 0; }
.row__newkey { max-width: 150px; flex: none; }
.row__ops { display: flex; flex-direction: column; gap: 6px; flex: none; }
.row :deep(.el-textarea), .row :deep(.el-input) { flex: 1; }
.row__ops :deep(.el-button) { margin-left: 0 !important; }

.json-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.json-view {
  max-height: 560px;
  overflow: auto;
  margin: 0;
  padding: 16px;
  border: 1px solid var(--line-soft);
  border-radius: var(--r-md);
  background: #fafbfd;
  font-family: ui-monospace, Consolas, monospace;
  font-size: 12.5px;
  line-height: 1.65;
  color: var(--ink-700);
}
</style>
