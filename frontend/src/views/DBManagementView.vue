<template>
  <div class="page">
    <div class="page-head db-head">
      <div>
        <h2 class="page-title">数据库管理</h2>
        <p class="page-desc">规则库、地址映射与人员信息维护</p>
      </div>
      <el-button :type="readOnly ? 'warning' : 'danger'" size="small" plain @click="toggleEdit">
        {{ readOnly ? '启用编辑' : '锁定编辑' }}
      </el-button>
    </div>

    <div class="card">
      <div class="card-head">
        <div class="search">
          <el-icon class="search__icon"><Search /></el-icon>
          <input
            v-model="searchKeyword"
            class="search__input"
            placeholder="全局模糊搜索，匹配任意列"
            @keyup.enter="doSearch"
          />
          <button v-if="searchKeyword" class="search__clear" @click="clearSearch">×</button>
        </div>
        <span v-if="searchKeyword" class="card-head__hint">
          匹配 {{ filteredCount }} / {{ rawCount }} 条
        </span>
      </div>

      <div class="tabs">
        <button
          v-for="t in tabList"
          :key="t.key"
          class="tab"
          :class="{ 'is-active': activeTab === t.key }"
          @click="switchTab(t.key)"
        >{{ t.label }}</button>
      </div>

      <div class="table-bar">
        <span class="card-head__hint">共 {{ filteredCount }} 条</span>
        <el-button type="primary" size="small" @click="openAdd" :disabled="readOnly">新增</el-button>
      </div>

      <el-table
        :data="currentList"
        v-loading="currentLoading"
        :max-height="tableMaxHeight"
        size="small"
      >
        <el-table-column
          v-for="c in currentColumns"
          :key="c.prop"
          :prop="c.prop"
          :label="c.label"
          :width="c.width"
          :min-width="c.minWidth"
          :align="c.align"
          :show-overflow-tooltip="c.tooltip"
          :formatter="c.formatter"
        />
        <el-table-column label="操作" width="140" fixed="right" align="right">
          <template #default="{ row }">
            <div class="ops">
              <el-button link type="primary" size="small" :disabled="readOnly" @click="openEdit(row)">编辑</el-button>
              <el-button link type="danger" size="small" :disabled="readOnly" @click="openDelete(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty">
            <div class="empty__icon"><el-icon><Coin /></el-icon></div>
            <div class="empty__text">{{ searchKeyword ? '没有匹配的记录' : '暂无数据' }}</div>
          </div>
        </template>
      </el-table>
    </div>

    <!-- 新增 / 编辑 对话框 -->
    <el-dialog
      v-model="dialog.visible"
      :title="dialog.title"
      width="520px"
      :close-on-click-modal="false"
    >
      <el-form :model="dialog.form" label-width="110px">
        <el-form-item
          v-for="f in currentFields"
          :key="f.prop"
          :label="f.label"
          :required="f.required"
        >
          <el-input-number
            v-if="f.type === 'number'"
            v-model="dialog.form[f.prop]"
            :min="1"
            style="width:100%"
          />
          <el-select v-else-if="f.type === 'select'" v-model="dialog.form[f.prop]" style="width:100%">
            <el-option v-for="o in f.options" :key="o" :label="o" :value="o" />
          </el-select>
          <el-input
            v-else
            v-model="dialog.form[f.prop]"
            :type="f.type === 'textarea' ? 'textarea' : 'text'"
            :rows="f.rows || 3"
            :disabled="f.disabledInEdit && dialog.mode === 'edit'"
            :placeholder="f.placeholder"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" @click="saveCurrent" :loading="dialog.saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import api from '../api'

const LEN = arr => (Array.isArray(arr) ? arr.length : 0)

export default {
  name: 'DBManagementView',
  data() {
    return {
      activeTab: 'subcategories',
      readOnly: true,
      searchKeyword: '',
      tableMaxHeight: 460,
      subcategories: [], subLoading: false,
      categories: [], catLoading: false,
      keywords: [], kwLoading: false,
      locations: [], locLoading: false,
      addressItems: [], addrLoading: false,
      workers: [], wrkLoading: false,
      dialog: { visible: false, title: '', mode: 'add', saving: false, editId: null, form: {} },
      ruleOptions: [],
      deletingId: null,
      tabList: [
        { key: 'subcategories', label: '子类别定义' },
        { key: 'categories', label: '分类规则' },
        { key: 'keywords', label: '触发关键词' },
        { key: 'locations', label: '触发位置' },
        { key: 'address', label: '地址映射' },
        { key: 'workers', label: '人员管理' }
      ],
      // 每类资源的列、字段、接口配置
      config: {
        subcategories: {
          list: 'subcategories', loading: 'subLoading',
          columns: [
            { prop: 'id', label: 'ID', width: 64 },
            { prop: 'sub_category', label: '子类别名称', width: 180 },
            { prop: 'description', label: '描述', minWidth: 200, tooltip: true }
          ],
          fields: [
            { prop: 'sub_category', label: '子类别名称', required: true },
            { prop: 'description', label: '描述', type: 'textarea', rows: 4 }
          ],
          add: d => api.adminAddSubcategory(d),
          update: (id, d) => api.adminUpdateSubcategory(id, d),
          del: id => api.adminDeleteSubcategory(id),
          empty: { sub_category: '', description: '' },
          nameOf: r => r.sub_category
        },
        categories: {
          list: 'categories', loading: 'catLoading',
          columns: [
            { prop: 'id', label: 'ID', width: 64 },
            { prop: 'rule_id', label: '规则ID', width: 80 },
            { prop: 'category', label: '类别', width: 100 },
            { prop: 'sub_category', label: '子类别', width: 120 },
            { prop: 'problem', label: '问题', minWidth: 160, tooltip: true },
            { prop: 'priority', label: '优先级', width: 90 },
            { prop: 'target_dept_semantic', label: '目标部门', minWidth: 130 },
            { prop: 'trigger_keywords', label: '关键词数', width: 90, align: 'center', formatter: r => LEN(r.trigger_keywords) },
            { prop: 'trigger_location', label: '位置数', width: 80, align: 'center', formatter: r => LEN(r.trigger_location) }
          ],
          fields: [
            { prop: 'rule_id', label: '规则ID', type: 'number', required: true },
            { prop: 'category', label: '维修类别', type: 'select', options: ['应急维修', '日常维修'], required: true },
            { prop: 'sub_category', label: '子类别', required: true },
            { prop: 'problem', label: '问题', required: true },
            { prop: 'priority', label: '优先级' },
            { prop: 'required_cert', label: '资质证书' },
            { prop: 'target_dept_semantic', label: '目标部门' },
            { prop: 'description', label: '详细描述', type: 'textarea', rows: 3 }
          ],
          add: d => api.adminAddCategory(d),
          update: (id, d) => api.adminUpdateCategory(id, d),
          del: id => api.adminDeleteCategory(id),
          empty: { rule_id: 0, category: '应急维修', sub_category: '', problem: '', priority: '', required_cert: '', target_dept_semantic: '', description: '' },
          nameOf: r => r.problem
        },
        keywords: {
          list: 'keywords', loading: 'kwLoading',
          columns: [
            { prop: 'id', label: 'ID', width: 64 },
            { prop: 'keyword', label: '关键词', width: 200 },
            { prop: 'category_id', label: '分类规则ID', width: 110 },
            { prop: 'sub_category', label: '子类别', width: 130 },
            { prop: 'problem', label: '关联问题', minWidth: 160, tooltip: true }
          ],
          fields: [
            { prop: 'keyword', label: '关键词', required: true },
            { prop: 'category_id', label: '关联分类规则ID', type: 'number', required: true, disabledInEdit: true }
          ],
          add: d => api.adminAddKeyword({ category_id: d.category_id, keyword: d.keyword }),
          update: (id, d) => api.adminUpdateKeyword(id, { keyword: d.keyword }),
          del: id => api.adminDeleteKeyword(id),
          empty: { keyword: '', category_id: 0 },
          nameOf: r => r.keyword
        },
        locations: {
          list: 'locations', loading: 'locLoading',
          columns: [
            { prop: 'id', label: 'ID', width: 64 },
            { prop: 'location', label: '位置', width: 200 },
            { prop: 'category_id', label: '分类规则ID', width: 110 },
            { prop: 'sub_category', label: '子类别', width: 130 },
            { prop: 'problem', label: '关联问题', minWidth: 160, tooltip: true }
          ],
          fields: [
            { prop: 'location', label: '位置', required: true },
            { prop: 'category_id', label: '关联分类规则', type: 'rule', required: true, disabledInEdit: true }
          ],
          add: d => api.adminAddLocation({ category_id: d.category_id, location: d.location }),
          update: (id, d) => api.adminUpdateLocation(id, { location: d.location }),
          del: id => api.adminDeleteLocation(id),
          empty: { location: '', category_id: 0 },
          nameOf: r => r.location
        },
        address: {
          list: 'addressItems', loading: 'addrLoading',
          columns: [
            { prop: 'id', label: 'ID', width: 64 },
            { prop: 'community', label: '小区名称', minWidth: 160 },
            { prop: 'street', label: '街道', minWidth: 130 },
            { prop: 'property_company', label: '物业公司', minWidth: 160, tooltip: true },
            { prop: 'maintenance_unit', label: '维修单位', minWidth: 160, tooltip: true },
            { prop: 'district', label: '区县', minWidth: 100 }
          ],
          fields: [
            { prop: 'community', label: '小区名称', required: true, disabledInEdit: true },
            { prop: 'street', label: '街道' },
            { prop: 'property_company', label: '物业公司', required: true },
            { prop: 'maintenance_unit', label: '维修单位' }
          ],
          add: d => api.addAddressMapping(d),
          update: (id, d) => api.updateAddressMapping(id, {
            street: d.street,
            property_company: d.property_company,
            maintenance_unit: d.maintenance_unit
          }),
          del: id => api.deleteAddressMapping(id),
          empty: { community: '', street: '', property_company: '', maintenance_unit: '' },
          nameOf: r => r.community
        },
        workers: {
          list: 'workers', loading: 'wrkLoading',
          columns: [
            { prop: 'id', label: 'ID', width: 64 },
            { prop: 'name', label: '姓名', minWidth: 110 },
            { prop: 'phone', label: '电话', minWidth: 130 },
            { prop: 'company', label: '所属公司', minWidth: 160, tooltip: true },
            { prop: 'department', label: '部门', minWidth: 130, tooltip: true },
            { prop: 'certs', label: '资质证书', minWidth: 160, tooltip: true }
          ],
          fields: [
            { prop: 'name', label: '姓名', required: true },
            { prop: 'phone', label: '电话' },
            { prop: 'company', label: '所属公司' },
            { prop: 'department', label: '部门' },
            { prop: 'certs', label: '资质证书', type: 'textarea', rows: 2 }
          ],
          add: d => api.adminAddWorker(d),
          update: (id, d) => api.adminUpdateWorker(id, d),
          del: id => api.adminDeleteWorker(id),
          empty: { name: '', phone: '', company: '', department: '', certs: '' },
          nameOf: r => r.name
        }
      }
    }
  },
  computed: {
    cfg() { return this.config[this.activeTab] },
    currentColumns() { return this.cfg.columns },
    currentFields() { return this.cfg.fields },
    currentLoading() { return this[this.cfg.loading] },
    currentList() {
      const list = this[this.cfg.list] || []
      if (!this.searchKeyword) return list
      const kw = this.searchKeyword.toLowerCase()
      return list.filter(item =>
        Object.values(item).some(v => {
          if (v === null || v === undefined) return false
          if (Array.isArray(v)) return v.some(x => String(x).toLowerCase().includes(kw))
          return String(v).toLowerCase().includes(kw)
        })
      )
    },
    filteredCount() { return this.currentList.length },
    rawCount() { return (this[this.cfg.list] || []).length }
  },
  mounted() {
    // 支持 /database?tab=workers 这类带页签参数的跳转
    const q = this.$route.query
    if (q.tab && this.tabList.some(t => t.key === q.tab)) this.activeTab = String(q.tab)
    this.calcHeight()
    window.addEventListener('resize', this.calcHeight)
    this.loadCurrent()
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.calcHeight)
  },
  methods: {
    calcHeight() {
      this.tableMaxHeight = Math.max(280, window.innerHeight - 340)
    },
    toggleEdit() {
      this.readOnly = !this.readOnly
      if (!this.readOnly) this.$message.warning('已启用编辑模式，请谨慎操作')
    },
    switchTab(key) {
      if (this.activeTab === key) return
      this.activeTab = key
      this.loadCurrent()
    },
    doSearch() { /* 搜索由 computed 驱动 */ },
    clearSearch() { this.searchKeyword = '' },
    async loadCurrent() {
      const key = this.activeTab
      this[this.cfg.loading] = true
      try {
        if (key === 'subcategories') this.subcategories = (await api.adminListSubcategories()) || []
        else if (key === 'categories') this.categories = (await api.adminListCategories()) || []
        else if (key === 'keywords') this.keywords = (await api.adminListKeywords()) || []
        else if (key === 'locations') this.locations = (await api.adminListLocations()) || []
        else if (key === 'address') this.addressItems = (await api.listAddressMappings()) || []
        else if (key === 'workers') this.workers = (await api.adminListWorkers()) || []
      } catch (e) {
        this.$message.error(e.message || '加载失败')
      } finally {
        this[this.cfg.loading] = false
      }
    },
    openAdd() {
      this.dialog = {
        visible: true,
        mode: 'add',
        title: '新增' + this.tabList.find(t => t.key === this.activeTab).label.replace(/定义|管理/, ''),
        saving: false,
        editId: null,
        form: { ...this.cfg.empty }
      }
    },
    openEdit(row) {
      const form = { ...this.cfg.empty }
      Object.keys(form).forEach(k => { if (row[k] !== undefined && row[k] !== null) form[k] = row[k] })
      this.dialog = {
        visible: true,
        mode: 'edit',
        title: '编辑记录',
        saving: false,
        editId: row.id,
        form
      }
    },
    async saveCurrent() {
      const { mode, editId, form } = this.dialog
      const required = this.currentFields.filter(f => f.required)
      const missing = required.find(f => {
        const v = form[f.prop]
        return v === undefined || v === null || v === '' || v === 0
      })
      if (missing) {
        this.$message.warning(`请填写「${missing.label}」`)
        return
      }
      this.dialog.saving = true
      try {
        if (mode === 'add') {
          await this.cfg.add(form)
          this.$message.success('添加成功')
        } else {
          await this.cfg.update(editId, form)
          this.$message.success('更新成功')
        }
        this.dialog.visible = false
        this.loadCurrent()
      } catch (e) {
        this.$message.error(e.message || '保存失败')
      } finally {
        this.dialog.saving = false
      }
    },
    async openDelete(row) {
      if (this.deletingId !== null) return
      const name = this.cfg.nameOf(row) || `#${row.id}`
      try {
        await this.$confirm(`确认删除「${name}」？该操作不可撤销。`, '确认删除', { type: 'warning' })
      } catch (e) {
        return
      }
      this.deletingId = row.id
      try {
        await this.cfg.del(row.id)
        this.$message.success('已删除')
        await this.loadCurrent()
      } catch (e) {
        this.$message.error(e.message || '删除失败')
      } finally {
        this.deletingId = null
      }
    }
  }
}
</script>

<style scoped>
.db-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.search {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  max-width: 420px;
  height: 34px;
  padding: 0 12px;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: #fafbfd;
  transition: box-shadow var(--dur) var(--ease), border-color var(--dur) var(--ease);
}
.search:focus-within {
  border-color: var(--brand);
  background: #fff;
  box-shadow: 0 0 0 3px var(--brand-ring);
}
.search__icon { color: var(--ink-400); }
.search__input {
  flex: 1;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--ink-800);
  font: inherit;
  font-size: 13px;
}
.search__clear {
  border: 0;
  background: none;
  color: var(--ink-400);
  font-size: 17px;
  line-height: 1;
  cursor: pointer;
}
.search__clear:hover { color: var(--ink-700); }

.tabs {
  display: flex;
  gap: 4px;
  padding: 10px 16px 0;
  border-bottom: 1px solid var(--line-soft);
  overflow-x: auto;
}
.tab {
  position: relative;
  padding: 8px 14px 12px;
  border: 0;
  background: none;
  color: var(--ink-500);
  font: inherit;
  font-size: 13px;
  white-space: nowrap;
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

.table-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
}
.card-head__hint { color: var(--ink-400); font-size: 12px; }
.ops { display: flex; justify-content: flex-end; gap: 2px; }
</style>
