<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <h2 style="margin:0">数据库管理</h2>
      <el-button :type="readOnly ? 'warning' : 'danger'" size="small" @click="toggleEdit">
        {{ readOnly ? '启用编辑' : '锁定编辑' }}
      </el-button>
    </div>
    <div style="margin-bottom:12px">
      <el-input v-model="searchKeyword" placeholder="全局模糊搜索（匹配任意列，回车 / 点击按钮搜索）" clearable size="default"
        style="max-width:520px" @keyup.enter="doSearch" @clear="doSearch">
        <template #append><el-button @click="doSearch" :icon="'Search'">搜索</el-button></template>
      </el-input>
      <span v-if="searchKeyword" style="margin-left:12px;color:#409EFF;font-size:13px">
        搜索 "{{ searchKeyword }}" — 当前显示 {{ filteredCount }} / {{ rawCount }} 条
      </span>
    </div>
    <el-tabs v-model="activeTab" type="border-card" @tab-change="onTabChange">
      <el-tab-pane label="子类别定义" name="subcategories">
        <div style="margin-bottom:12px;display:flex;justify-content:space-between">
          <span style="color:#909399;font-size:13px">共 {{ filteredSubcategories.length }} 条</span>
          <el-button type="primary" size="small" @click="showSubcategoryDialog('add')" :disabled="readOnly">新增</el-button>
        </div>
        <el-table :data="filteredSubcategories" stripe size="small" v-loading="subLoading" :max-height="tableMaxHeight" style="width:100%">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="sub_category" label="子类别名称" width="160" />
          <el-table-column prop="description" label="描述" show-overflow-tooltip />
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{row}">
              <el-button link type="primary" size="small" @click="showSubcategoryDialog('edit', row)" :disabled="readOnly">编辑</el-button>
              <el-button link type="danger" size="small" @click="delSubcategory(row)" :disabled="readOnly">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="分类规则" name="categories">
        <div style="margin-bottom:12px;display:flex;justify-content:space-between">
          <span style="color:#909399;font-size:13px">共 {{ filteredCategories.length }} 条</span>
          <el-button type="primary" size="small" @click="showCategoryDialog('add')" :disabled="readOnly">新增</el-button>
        </div>
        <el-table :data="filteredCategories" stripe size="small" v-loading="catLoading" :max-height="tableMaxHeight" style="width:100%">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="rule_id" label="规则ID" width="70" />
          <el-table-column prop="category" label="类别" width="90" />
          <el-table-column prop="sub_category" label="子类别" width="110" />
          <el-table-column prop="problem" label="问题" min-width="100" show-overflow-tooltip />
          <el-table-column prop="priority" label="优先级" width="80" />
          <el-table-column prop="required_cert" label="资质" min-width="100" show-overflow-tooltip />
          <el-table-column prop="target_dept_semantic" label="目标部门" min-width="100" />
          <el-table-column prop="description" label="描述" show-overflow-tooltip />
          <el-table-column label="关键词数" width="80" align="center">
            <template #default="{row}">{{ (row.trigger_keywords || []).length }}</template>
          </el-table-column>
          <el-table-column label="位置数" width="80" align="center">
            <template #default="{row}">{{ (row.trigger_location || []).length }}</template>
          </el-table-column>
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{row}">
              <el-button link type="primary" size="small" @click="showCategoryDialog('edit', row)" :disabled="readOnly">编辑</el-button>
              <el-button link type="danger" size="small" @click="delCategory(row)" :disabled="readOnly">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="触发关键词" name="keywords">
        <div style="margin-bottom:12px;display:flex;justify-content:space-between">
          <span style="color:#909399;font-size:13px">共 {{ filteredKeywords.length }} 条</span>
          <el-button type="primary" size="small" @click="showKeywordDialog('add')" :disabled="readOnly">新增</el-button>
        </div>
        <el-table :data="filteredKeywords" stripe size="small" v-loading="kwLoading" :max-height="tableMaxHeight" style="width:100%">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="keyword" label="关键词" width="200" />
          <el-table-column prop="category_id" label="分类规则ID" width="100" />
          <el-table-column prop="sub_category" label="子类别" width="120" />
          <el-table-column prop="problem" label="关联问题" show-overflow-tooltip />
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{row}">
              <el-button link type="primary" size="small" @click="showKeywordDialog('edit', row)" :disabled="readOnly">编辑</el-button>
              <el-button link type="danger" size="small" @click="delKeyword(row)" :disabled="readOnly">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="触发位置" name="locations">
        <div style="margin-bottom:12px;display:flex;justify-content:space-between">
          <span style="color:#909399;font-size:13px">共 {{ filteredLocations.length }} 条</span>
          <el-button type="primary" size="small" @click="showLocationDialog('add')" :disabled="readOnly">新增</el-button>
        </div>
        <el-table :data="filteredLocations" stripe size="small" v-loading="locLoading" :max-height="tableMaxHeight" style="width:100%">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="location" label="位置" width="200" />
          <el-table-column prop="category_id" label="分类规则ID" width="100" />
          <el-table-column prop="sub_category" label="子类别" width="120" />
          <el-table-column prop="problem" label="关联问题" show-overflow-tooltip />
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{row}">
              <el-button link type="primary" size="small" @click="showLocationDialog('edit', row)" :disabled="readOnly">编辑</el-button>
              <el-button link type="danger" size="small" @click="delLocation(row)" :disabled="readOnly">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="地址映射" name="address">
        <div style="margin-bottom:12px;display:flex;justify-content:space-between">
          <span style="color:#909399;font-size:13px">共 {{ filteredAddresses.length }} 条</span>
          <el-button type="primary" size="small" @click="showAddrDialog('add')" :disabled="readOnly">新增</el-button>
        </div>
        <el-table :data="filteredAddresses" stripe v-loading="addrLoading" size="small" :max-height="tableMaxHeight" style="width:100%">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="community" label="小区名称" min-width="150" />
          <el-table-column prop="street" label="街道" min-width="120" />
          <el-table-column prop="property_company" label="物业公司" min-width="150" show-overflow-tooltip />
          <el-table-column prop="maintenance_unit" label="维修单位" min-width="150" show-overflow-tooltip />
          <el-table-column prop="district" label="区县" />
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{row}">
              <el-button link type="primary" size="small" @click="showAddrDialog('edit', row)" :disabled="readOnly">编辑</el-button>
              <el-button link type="danger" size="small" @click="delAddr(row)" :disabled="readOnly">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="人员管理" name="workers">
        <div style="margin-bottom:12px;display:flex;justify-content:space-between">
          <span style="color:#909399;font-size:13px">共 {{ filteredWorkers.length }} 条</span>
          <el-button type="primary" size="small" @click="showWorkerDialog('add')" :disabled="readOnly">新增</el-button>
        </div>
        <el-table :data="filteredWorkers" stripe size="small" v-loading="wrkLoading" :max-height="tableMaxHeight" style="width:100%">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="name" label="姓名" min-width="100" />
          <el-table-column prop="phone" label="电话" min-width="120" />
          <el-table-column prop="company" label="所属公司" min-width="150" show-overflow-tooltip />
          <el-table-column prop="department" label="部门" min-width="120" show-overflow-tooltip />
          <el-table-column prop="certs" label="资质证书" show-overflow-tooltip />
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{row}">
              <el-button link type="primary" size="small" @click="showWorkerDialog('edit', row)" :disabled="readOnly">编辑</el-button>
              <el-button link type="danger" size="small" @click="delWorker(row)" :disabled="readOnly">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="subDialog.visible" :title="subDialog.title" width="500px">
      <el-form :model="subDialog.form">
        <el-form-item label="子类别名称" required><el-input v-model="subDialog.form.sub_category" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="subDialog.form.description" type="textarea" :rows="4" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="subDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="saveSubcategory" :loading="subDialog.saving">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="catDialog.visible" :title="catDialog.title" width="600px">
      <el-form :model="catDialog.form" label-width="110px">
        <el-form-item label="规则ID" required><el-input-number v-model="catDialog.form.rule_id" :min="1" /></el-form-item>
        <el-form-item label="维修类别" required><el-select v-model="catDialog.form.category" style="width:100%"><el-option label="应急维修" value="应急维修" /><el-option label="日常维修" value="日常维修" /></el-select></el-form-item>
        <el-form-item label="子类别" required><el-input v-model="catDialog.form.sub_category" /></el-form-item>
        <el-form-item label="问题" required><el-input v-model="catDialog.form.problem" /></el-form-item>
        <el-form-item label="优先级"><el-input v-model="catDialog.form.priority" /></el-form-item>
        <el-form-item label="资质证书"><el-input v-model="catDialog.form.required_cert" /></el-form-item>
        <el-form-item label="目标部门"><el-input v-model="catDialog.form.target_dept_semantic" /></el-form-item>
        <el-form-item label="详细描述"><el-input v-model="catDialog.form.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="catDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="saveCategory" :loading="catDialog.saving">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="kwDialog.visible" :title="kwDialog.title" width="500px">
      <el-form :model="kwDialog.form">
        <el-form-item label="关键词" required><el-input v-model="kwDialog.form.keyword" /></el-form-item>
        <el-form-item label="关联分类规则ID" required v-if="kwDialog.mode === 'add'"><el-input-number v-model="kwDialog.form.category_id" :min="1" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="kwDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="saveKeyword" :loading="kwDialog.saving">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="locDialog.visible" :title="locDialog.title" width="500px">
      <el-form :model="locDialog.form">
        <el-form-item label="位置" required><el-input v-model="locDialog.form.location" /></el-form-item>
        <el-form-item label="关联分类规则ID" required v-if="locDialog.mode === 'add'"><el-input-number v-model="locDialog.form.category_id" :min="1" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="locDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="saveLocation" :loading="locDialog.saving">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="addrDialog.visible" :title="addrDialog.mode === 'add' ? '新增地址映射' : '编辑地址映射'" width="500px">
      <el-form :model="addrDialog.form">
        <el-form-item label="小区名称" required v-if="addrDialog.mode === 'add'"><el-input v-model="addrDialog.form.community" /></el-form-item>
        <el-form-item label="街道"><el-input v-model="addrDialog.form.street" /></el-form-item>
        <el-form-item label="物业公司" required><el-input v-model="addrDialog.form.property_company" /></el-form-item>
        <el-form-item label="维修单位"><el-input v-model="addrDialog.form.maintenance_unit" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addrDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="saveAddr" :loading="addrDialog.saving">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="wrkDialog.visible" :title="wrkDialog.title" width="500px">
      <el-form :model="wrkDialog.form">
        <el-form-item label="姓名" required><el-input v-model="wrkDialog.form.name" /></el-form-item>
        <el-form-item label="电话"><el-input v-model="wrkDialog.form.phone" /></el-form-item>
        <el-form-item label="所属公司"><el-input v-model="wrkDialog.form.company" /></el-form-item>
        <el-form-item label="部门"><el-input v-model="wrkDialog.form.department" /></el-form-item>
        <el-form-item label="资质证书"><el-input v-model="wrkDialog.form.certs" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="wrkDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="saveWorker" :loading="wrkDialog.saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import api from '../api'

export default {
  computed: {
    tableMaxHeight() { return window.innerHeight - 310 },
    filteredSubcategories() { return this.filterList(this.subcategories) },
    filteredCategories() { return this.filterList(this.categories) },
    filteredKeywords() { return this.filterList(this.keywords) },
    filteredLocations() { return this.filterList(this.locations) },
    filteredAddresses() { return this.filterList(this.addressItems) },
    filteredWorkers() { return this.filterList(this.workers) },
    filteredCount() {
      const map = { subcategories: this.filteredSubcategories, categories: this.filteredCategories, keywords: this.filteredKeywords, locations: this.filteredLocations, address: this.filteredAddresses, workers: this.filteredWorkers }
      return (map[this.activeTab] || []).length
    },
    rawCount() {
      const map = { subcategories: this.subcategories, categories: this.categories, keywords: this.keywords, locations: this.locations, address: this.addressItems, workers: this.workers }
      return (map[this.activeTab] || []).length
    }
  },
  data() {
    return {
      activeTab: 'subcategories',
      readOnly: true,
      searchKeyword: '',
      subcategories: [], subLoading: false,
      subDialog: { visible: false, title: '', mode: 'add', saving: false, editId: null, form: { sub_category: '', description: '' } },
      categories: [], catLoading: false,
      catDialog: { visible: false, title: '', mode: 'add', saving: false, editId: null, form: { rule_id: 0, category: '应急维修', sub_category: '', problem: '', priority: '', required_cert: '', target_dept_semantic: '', description: '' } },
      keywords: [], kwLoading: false,
      kwDialog: { visible: false, title: '', mode: 'add', saving: false, editId: null, form: { keyword: '', category_id: 0 } },
      locations: [], locLoading: false,
      locDialog: { visible: false, title: '', mode: 'add', saving: false, editId: null, form: { location: '', category_id: 0 } },
      addressItems: [], addrLoading: false,
      addrDialog: { visible: false, mode: 'add', saving: false, editId: null, form: { community: '', street: '', property_company: '', maintenance_unit: '' } },
      workers: [], wrkLoading: false,
      wrkDialog: { visible: false, title: '', mode: 'add', saving: false, editId: null, form: { name: '', phone: '', company: '', department: '', certs: '' } }
    }
  },
  mounted() { this.loadSubcategories() },
  methods: {
    toggleEdit() { this.readOnly = !this.readOnly; if (!this.readOnly) this.$message.warning('已启用编辑模式，请谨慎操作') },
    doSearch() { /* 搜索由 computed 属性自动驱动，此方法用于按钮点击反馈 */ },
    filterList(list) {
      if (!this.searchKeyword) return list
      if (!list || !list.length) return list
      const kw = this.searchKeyword.toLowerCase()
      return list.filter(item => {
        return Object.values(item).some(v => {
          if (v === null || v === undefined) return false
          if (Array.isArray(v)) return v.some(x => String(x).toLowerCase().includes(kw))
          return String(v).toLowerCase().includes(kw)
        })
      })
    },
    onTabChange(name) {
      if (name === 'subcategories') this.loadSubcategories()
      else if (name === 'categories') this.loadCategories()
      else if (name === 'keywords') this.loadKeywords()
      else if (name === 'locations') this.loadLocations()
      else if (name === 'address') this.loadAddresses()
      else if (name === 'workers') this.loadWorkers()
    },
    // --- 子类别 ---
    async loadSubcategories() { this.subLoading = true; try { this.subcategories = await api.adminListSubcategories() } catch (e) { this.$message.error(e.message) } finally { this.subLoading = false } },
    showSubcategoryDialog(mode, row) { this.subDialog.mode = mode; this.subDialog.editId = mode === 'edit' ? row.id : null; this.subDialog.title = mode === 'add' ? '新增子类别' : '编辑子类别'; this.subDialog.form = mode === 'add' ? { sub_category: '', description: '' } : { sub_category: row.sub_category || '', description: row.description || '' }; this.subDialog.visible = true },
    async saveSubcategory() { const { mode, editId, form } = this.subDialog; if (!form.sub_category) { this.$message.warning('请输入子类别名称'); return } this.subDialog.saving = true; try { if (mode === 'add') { await api.adminAddSubcategory(form); this.$message.success('添加成功') } else { await api.adminUpdateSubcategory(editId, form); this.$message.success('更新成功') } this.subDialog.visible = false; this.loadSubcategories() } catch (e) { this.$message.error(e.message) } finally { this.subDialog.saving = false } },
    async delSubcategory(row) { try { await this.$confirm(`确认删除子类别 "${row.sub_category}"？`, '确认', { type: 'warning' }); await api.adminDeleteSubcategory(row.id); this.$message.success('已删除'); this.loadSubcategories() } catch (e) { if (e !== 'cancel') this.$message.error(e.message) } },
    // --- 分类规则 ---
    async loadCategories() { this.catLoading = true; try { this.categories = await api.adminListCategories() } catch (e) { this.$message.error(e.message) } finally { this.catLoading = false } },
    showCategoryDialog(mode, row) { this.catDialog.mode = mode; this.catDialog.editId = mode === 'edit' ? row.id : null; this.catDialog.title = mode === 'add' ? '新增分类规则' : '编辑分类规则'; this.catDialog.form = mode === 'add' ? { rule_id: 0, category: '应急维修', sub_category: '', problem: '', priority: '', required_cert: '', target_dept_semantic: '', description: '' } : { rule_id: row.rule_id, category: row.category || '', sub_category: row.sub_category || '', problem: row.problem || '', priority: row.priority || '', required_cert: row.required_cert || '', target_dept_semantic: row.target_dept_semantic || '', description: row.description || '' }; this.catDialog.visible = true },
    async saveCategory() { const { mode, editId, form } = this.catDialog; if (!form.rule_id || !form.category || !form.sub_category || !form.problem) { this.$message.warning('请填写必填项'); return } this.catDialog.saving = true; try { if (mode === 'add') { await api.adminAddCategory(form); this.$message.success('添加成功') } else { await api.adminUpdateCategory(editId, form); this.$message.success('更新成功') } this.catDialog.visible = false; this.loadCategories() } catch (e) { this.$message.error(e.message) } finally { this.catDialog.saving = false } },
    async delCategory(row) { try { await this.$confirm(`确认删除分类规则"${row.problem}"？将同时删除关联的关键词和位置。`, '确认', { type: 'warning' }); await api.adminDeleteCategory(row.id); this.$message.success('已删除'); this.loadCategories() } catch (e) { if (e !== 'cancel') this.$message.error(e.message) } },
    // --- 关键词 ---
    async loadKeywords() { this.kwLoading = true; try { this.keywords = await api.adminListKeywords() } catch (e) { this.$message.error(e.message) } finally { this.kwLoading = false } },
    showKeywordDialog(mode, row) { this.kwDialog.mode = mode; this.kwDialog.editId = mode === 'edit' ? row.id : null; this.kwDialog.title = mode === 'add' ? '新增关键词' : '编辑关键词'; this.kwDialog.form = mode === 'add' ? { keyword: '', category_id: 0 } : { keyword: row.keyword || '', category_id: row.category_id }; this.kwDialog.visible = true },
    async saveKeyword() { const { mode, editId, form } = this.kwDialog; if (!form.keyword) { this.$message.warning('请输入关键词'); return } if (mode === 'add' && !form.category_id) { this.$message.warning('请输入关联分类规则ID'); return } this.kwDialog.saving = true; try { if (mode === 'add') { await api.adminAddKeyword({ category_id: form.category_id, keyword: form.keyword }); this.$message.success('添加成功') } else { await api.adminUpdateKeyword(editId, { keyword: form.keyword }); this.$message.success('更新成功') } this.kwDialog.visible = false; this.loadKeywords() } catch (e) { this.$message.error(e.message) } finally { this.kwDialog.saving = false } },
    async delKeyword(row) { try { await this.$confirm(`确认删除关键词 "${row.keyword}"？`, '确认', { type: 'warning' }); await api.adminDeleteKeyword(row.id); this.$message.success('已删除'); this.loadKeywords() } catch (e) { if (e !== 'cancel') this.$message.error(e.message) } },
    // --- 位置 ---
    async loadLocations() { this.locLoading = true; try { this.locations = await api.adminListLocations() } catch (e) { this.$message.error(e.message) } finally { this.locLoading = false } },
    showLocationDialog(mode, row) { this.locDialog.mode = mode; this.locDialog.editId = mode === 'edit' ? row.id : null; this.locDialog.title = mode === 'add' ? '新增位置' : '编辑位置'; this.locDialog.form = mode === 'add' ? { location: '', category_id: 0 } : { location: row.location || '', category_id: row.category_id }; this.locDialog.visible = true },
    async saveLocation() { const { mode, editId, form } = this.locDialog; if (!form.location) { this.$message.warning('请输入位置'); return } if (mode === 'add' && !form.category_id) { this.$message.warning('请输入关联分类规则ID'); return } this.locDialog.saving = true; try { if (mode === 'add') { await api.adminAddLocation({ category_id: form.category_id, location: form.location }); this.$message.success('添加成功') } else { await api.adminUpdateLocation(editId, { location: form.location }); this.$message.success('更新成功') } this.locDialog.visible = false; this.loadLocations() } catch (e) { this.$message.error(e.message) } finally { this.locDialog.saving = false } },
    async delLocation(row) { try { await this.$confirm(`确认删除位置 "${row.location}"？`, '确认', { type: 'warning' }); await api.adminDeleteLocation(row.id); this.$message.success('已删除'); this.loadLocations() } catch (e) { if (e !== 'cancel') this.$message.error(e.message) } },
    // --- 地址映射 ---
    async loadAddresses() { this.addrLoading = true; try { this.addressItems = await api.listAddressMappings() } catch (e) { this.$message.error(e.message) } finally { this.addrLoading = false } },
    showAddrDialog(mode, row) { this.addrDialog.mode = mode; this.addrDialog.editId = mode === 'edit' ? row.id : null; this.addrDialog.form = mode === 'add' ? { community: '', street: '', property_company: '', maintenance_unit: '' } : { community: row.community || '', street: row.street || '', property_company: row.property_company || '', maintenance_unit: row.maintenance_unit || '' }; this.addrDialog.visible = true },
    async saveAddr() { const { mode, editId, form } = this.addrDialog; if (mode === 'add' && (!form.community || !form.property_company)) { this.$message.warning('请填写必填项'); return } this.addrDialog.saving = true; try { if (mode === 'add') { await api.addAddressMapping(form); this.$message.success('添加成功') } else { await api.updateAddressMapping(editId, { street: form.street, property_company: form.property_company, maintenance_unit: form.maintenance_unit }); this.$message.success('更新成功') } this.addrDialog.visible = false; this.loadAddresses() } catch (e) { this.$message.error(e.message) } finally { this.addrDialog.saving = false } },
    async delAddr(row) { try { await this.$confirm(`确认删除映射 ${row.community}？`, '确认', { type: 'warning' }); await api.deleteAddressMapping(row.id); this.$message.success('已删除'); this.loadAddresses() } catch (e) { if (e !== 'cancel') this.$message.error(e.message) } },
    // --- 人员管理 ---
    async loadWorkers() { this.wrkLoading = true; try { this.workers = await api.adminListWorkers() } catch (e) { this.$message.error(e.message) } finally { this.wrkLoading = false } },
    showWorkerDialog(mode, row) { this.wrkDialog.mode = mode; this.wrkDialog.editId = mode === 'edit' ? row.id : null; this.wrkDialog.title = mode === 'add' ? '新增工人' : '编辑工人'; this.wrkDialog.form = mode === 'add' ? { name: '', phone: '', company: '', department: '', certs: '' } : { name: row.name || '', phone: row.phone || '', company: row.company || '', department: row.department || '', certs: row.certs || '' }; this.wrkDialog.visible = true },
    async saveWorker() { const { mode, editId, form } = this.wrkDialog; if (!form.name) { this.$message.warning('请输入姓名'); return } this.wrkDialog.saving = true; try { if (mode === 'add') { await api.adminAddWorker(form); this.$message.success('添加成功') } else { await api.adminUpdateWorker(editId, form); this.$message.success('更新成功') } this.wrkDialog.visible = false; this.loadWorkers() } catch (e) { this.$message.error(e.message) } finally { this.wrkDialog.saving = false } },
    async delWorker(row) { try { await this.$confirm(`确认删除工人 "${row.name}"？`, '确认', { type: 'warning' }); await api.adminDeleteWorker(row.id); this.$message.success('已删除'); this.loadWorkers() } catch (e) { if (e !== 'cancel') this.$message.error(e.message) } }
  }
}
</script>