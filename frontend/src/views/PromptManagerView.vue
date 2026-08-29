<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <h2 style="margin:0">提示词管理</h2>
      <div style="display:flex;gap:8px">
        <el-button type="success" size="small" @click="reloadPrompts" :loading="reloading">热重载</el-button>
        <el-button :type="readOnly ? 'warning' : 'danger'" size="small" @click="toggleEdit">
          {{ readOnly ? '启用编辑' : '锁定编辑' }}
        </el-button>
      </div>
    </div>

    <div v-if="loading" style="text-align:center;padding:40px">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p>加载提示词配置中...</p>
    </div>

    <div v-else>
      <el-alert :title="`配置版本: ${promptsData.version || '-'}   |   提示：点击右上角「启用编辑」后方可修改`" type="info" :closable="false" style="margin-bottom:12px" />

      <el-tabs v-model="activeTab" type="border-card">
        <!-- ========== Step1 ========== -->
        <el-tab-pane label="Step1 - SubCategory 选取" name="step1">
          <!-- system_role -->
          <el-divider content-position="left">系统角色 (system_role)</el-divider>
          <el-input
            v-model="editStep1.system_role"
            type="textarea"
            :rows="3"
            :disabled="readOnly"
            style="max-width:900px"
          />
          <div style="margin:8px 0 20px 0">
            <el-button size="small" type="primary" @click="saveField('step1.system_role', editStep1.system_role)" :disabled="readOnly">保存</el-button>
          </div>

          <!-- thinking_steps -->
          <el-divider content-position="left">思考步骤 (thinking_steps)</el-divider>
          <div v-for="(step, i) in editStep1.thinking_steps" :key="'ts-'+i" style="margin-bottom:12px;display:flex;gap:10px;align-items:flex-start;max-width:1000px">
            <span style="min-width:28px;color:#909399;line-height:32px;font-weight:bold;text-align:right">{{ i + 1 }}.</span>
            <el-input
              v-model="editStep1.thinking_steps[i]"
              type="textarea"
              :rows="step.length > 60 ? 3 : 2"
              :disabled="readOnly"
              style="flex:1"
            />
            <el-button v-if="!readOnly" size="small" type="danger" @click="removeArrayItem(editStep1.thinking_steps, i)" style="align-self:center">删除</el-button>
          </div>
          <div style="margin:8px 0;display:flex;gap:8px">
            <el-button v-if="!readOnly" size="small" @click="editStep1.thinking_steps.push('')">+ 添加思考步骤</el-button>
            <el-button v-if="!readOnly" size="small" type="primary" @click="saveField('step1.thinking_steps', editStep1.thinking_steps)">保存全部</el-button>
          </div>

          <!-- tasks -->
          <el-divider content-position="left">任务列表 (tasks) — 动态遍历，支持任意数量</el-divider>
          <div v-for="(val, key) in editStep1.tasks" :key="'tk-'+key" style="margin-bottom:12px;display:flex;gap:10px;align-items:flex-start;max-width:1000px">
            <span style="min-width:70px;font-weight:bold;color:#409EFF;line-height:32px">{{ key }}</span>
            <el-input
              v-model="editStep1.tasks[key]"
              type="textarea"
              :rows="2"
              :disabled="readOnly"
              style="flex:1"
            />
            <el-button v-if="!readOnly" size="small" type="primary" @click="saveTask(key, editStep1.tasks[key])" style="align-self:center">保存</el-button>
          </div>
          <div v-if="!readOnly" style="margin:8px 0;display:flex;gap:8px;align-items:center">
            <el-input v-model="newTaskKey" placeholder="键名，如 task5" size="small" style="max-width:140px" />
            <el-input v-model="newTaskValue" placeholder="任务描述" size="small" style="max-width:500px" />
            <el-button size="small" type="success" @click="addTask">添加任务</el-button>
          </div>

          <!-- notes -->
          <el-divider content-position="left">注意事项 (notes)</el-divider>
          <div v-for="(note, i) in editStep1.notes" :key="'nt-'+i" style="margin-bottom:12px;display:flex;gap:10px;align-items:flex-start;max-width:1000px">
            <span style="min-width:28px;color:#909399;line-height:32px;font-weight:bold;text-align:right">{{ i + 1 }}.</span>
            <el-input
              v-model="editStep1.notes[i]"
              type="textarea"
              :rows="note.length > 60 ? 3 : 2"
              :disabled="readOnly"
              style="flex:1"
            />
            <el-button v-if="!readOnly" size="small" type="danger" @click="removeArrayItem(editStep1.notes, i)" style="align-self:center">删除</el-button>
          </div>
          <div style="margin:8px 0;display:flex;gap:8px">
            <el-button v-if="!readOnly" size="small" @click="editStep1.notes.push('')">+ 添加注意事项</el-button>
            <el-button v-if="!readOnly" size="small" type="primary" @click="saveField('step1.notes', editStep1.notes)">保存全部</el-button>
          </div>
        </el-tab-pane>

        <!-- ========== Step2 ========== -->
        <el-tab-pane label="Step2 - 关键词匹配" name="step2">
          <!-- system_role -->
          <el-divider content-position="left">系统角色 (system_role)</el-divider>
          <el-input v-model="editStep2.system_role" type="textarea" :rows="3" :disabled="readOnly" style="max-width:900px" />
          <div style="margin:8px 0 20px 0">
            <el-button size="small" type="primary" @click="saveField('step2.system_role', editStep2.system_role)" :disabled="readOnly">保存</el-button>
          </div>

          <!-- thinking_step descriptions -->
          <el-divider content-position="left">思考步骤描述</el-divider>
          <div style="margin-bottom:12px;display:flex;gap:10px;align-items:center;max-width:700px">
            <span style="min-width:80px;font-weight:bold;color:#409EFF">第1步:</span>
            <el-input v-model="editStep2.thinking_step1_description" size="small" :disabled="readOnly" style="flex:1" />
          </div>
          <div style="margin-bottom:12px;display:flex;gap:10px;align-items:center;max-width:700px">
            <span style="min-width:80px;font-weight:bold;color:#409EFF">第2步:</span>
            <el-input v-model="editStep2.thinking_step2_description" size="small" :disabled="readOnly" style="flex:1" />
          </div>
          <el-button size="small" type="primary" :disabled="readOnly" @click="saveThinkingSteps">保存思考步骤</el-button>
          <div style="height:16px"></div>

          <!-- classification_rules — 每条独立、宽文本区 -->
          <el-divider content-position="left">分类规则 (classification_rules) — 共 {{ editStep2.classification_rules.length }} 条</el-divider>
          <div v-for="(rule, i) in editStep2.classification_rules" :key="'cr-'+i" style="margin-bottom:14px;display:flex;gap:10px;align-items:flex-start;max-width:1100px">
            <span style="min-width:36px;color:#909399;line-height:32px;font-weight:bold;text-align:right">#{{ i }}</span>
            <el-input
              v-model="editStep2.classification_rules[i]"
              type="textarea"
              :rows="rule.length > 80 ? 3 : 2"
              :disabled="readOnly"
              style="flex:1"
            />
            <div v-if="!readOnly" style="display:flex;flex-direction:column;gap:4px;min-width:60px">
              <el-button size="small" type="primary" @click="saveRule(i, editStep2.classification_rules[i])">保存</el-button>
              <el-button size="small" type="danger" @click="deleteRule(i)">删除</el-button>
            </div>
          </div>
          <div v-if="!readOnly" style="margin:12px 0;display:flex;gap:10px;align-items:flex-start;max-width:1100px">
            <span style="min-width:36px;color:#67C23A;font-weight:bold;line-height:32px">NEW</span>
            <el-input v-model="newRuleText" placeholder="输入新规则文本..." type="textarea" :rows="3" style="flex:1" />
            <el-button size="small" type="success" @click="addRule" style="align-self:center;min-width:60px">添加</el-button>
          </div>

          <!-- requirements -->
          <el-divider content-position="left">输出要求 (requirements)</el-divider>
          <div v-for="(req, i) in editStep2.requirements" :key="'rq-'+i" style="margin-bottom:10px;display:flex;gap:10px;align-items:center;max-width:800px">
            <span style="min-width:28px;color:#909399;font-weight:bold;text-align:right">{{ i + 1 }}.</span>
            <el-input v-model="editStep2.requirements[i]" size="small" :disabled="readOnly" style="flex:1" />
            <el-button v-if="!readOnly" size="small" type="danger" :icon="'Delete'" circle @click="removeArrayItem(editStep2.requirements, i)" />
          </div>
          <div style="display:flex;gap:8px">
            <el-button v-if="!readOnly" size="small" @click="editStep2.requirements.push('')">+ 添加要求</el-button>
            <el-button v-if="!readOnly" size="small" type="primary" @click="saveField('step2.requirements', editStep2.requirements)">保存全部</el-button>
          </div>
          <div style="height:16px"></div>

          <!-- location_selection_prompt -->
          <el-divider content-position="left">位置选择提示模板 (location_selection_prompt)</el-divider>
          <el-input v-model="editStep2.location_selection_prompt" type="textarea" :rows="3" :disabled="readOnly" style="max-width:900px" />
          <div style="margin:8px 0 20px 0">
            <el-button size="small" type="primary" @click="saveField('step2.location_selection_prompt', editStep2.location_selection_prompt)" :disabled="readOnly">保存</el-button>
          </div>

          <!-- location_requirements -->
          <el-divider content-position="left">位置选择要求 (location_requirements)</el-divider>
          <div v-for="(lr, i) in editStep2.location_requirements" :key="'lr-'+i" style="margin-bottom:10px;display:flex;gap:10px;align-items:center;max-width:800px">
            <el-input v-model="editStep2.location_requirements[i]" size="small" :disabled="readOnly" style="flex:1" />
            <el-button v-if="!readOnly" size="small" type="danger" :icon="'Delete'" circle @click="removeArrayItem(editStep2.location_requirements, i)" />
          </div>
          <div style="display:flex;gap:8px">
            <el-button v-if="!readOnly" size="small" @click="editStep2.location_requirements.push('')">+ 添加</el-button>
            <el-button v-if="!readOnly" size="small" type="primary" @click="saveField('step2.location_requirements', editStep2.location_requirements)">保存全部</el-button>
          </div>
        </el-tab-pane>

        <!-- ========== JSON 原始预览 ========== -->
        <el-tab-pane label="JSON 原始数据" name="json">
          <div style="margin-bottom:8px;display:flex;gap:8px;align-items:center">
            <el-button size="small" type="primary" @click="copyJson">复制 JSON</el-button>
            <span style="color:#909399;font-size:13px">只读预览，反映当前页面编辑内容</span>
          </div>
          <pre style="background:#f5f7fa;padding:16px;border-radius:4px;max-height:600px;overflow:auto;font-size:13px;line-height:1.6">{{ jsonPreview }}</pre>
        </el-tab-pane>
      </el-tabs>
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
  promptsData.value = data
  const s1 = data.step1 || {}
  editStep1.system_role = s1.system_role || ''
  editStep1.thinking_steps = [...(s1.thinking_steps || [])]
  editStep1.tasks = { ...(s1.tasks || {}) }
  editStep1.notes = [...(s1.notes || [])]

  const s2 = data.step2 || {}
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
    ElMessage.success(`"${path}" 已保存并持久化`)
    ElMessage.info('记得点击「热重载」使更改生效', 2000)
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.message || e))
  }
}

async function saveTask(key, value) {
  try {
    await api.updateStep1Task(key, value)
    ElMessage.success(`任务 "${key}" 已保存`)
    ElMessage.info('记得点击「热重载」使更改生效', 2000)
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
h2 { color: #303133; }
</style>