<template>
  <div>
    <h2>系统仪表盘</h2>

    <el-row :gutter="20" style="margin-bottom:20px">
      <el-col :span="6">
        <el-card>
          <el-statistic title="工单总数" :value="stats.total_orders || 0" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <el-statistic title="维修工人" :value="stats.total_workers || 0" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <el-statistic title="待审核反馈" :value="stats.pending_feedbacks || 0" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <el-statistic title="待处理工单" :value="statusCount('PENDING')" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-bottom:20px">
      <el-col :span="12">
        <el-card>
          <template #header>工单状态分布</template>
          <div v-if="statusDist.length" style="height:250px">
            <div v-for="(item,i) in statusDist" :key="i" style="margin-bottom:12px">
              <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                <span>{{ item.label }}</span>
                <span>{{ item.count }}</span>
              </div>
              <el-progress :percentage="item.percent" :color="item.color" :stroke-width="16" />
            </div>
          </div>
          <el-empty v-else description="暂无数据" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>子类别工单分布（Top8）</template>
          <div v-if="subDist.length" style="height:250px">
            <div v-for="(item,i) in subDist.slice(0,8)" :key="i" style="margin-bottom:8px">
              <div style="display:flex;justify-content:space-between;margin-bottom:2px">
                <span style="font-size:13px">{{ item.sub_category }}</span>
                <span style="font-size:13px">{{ item.count }}</span>
              </div>
              <el-progress :percentage="item.percent" :color="colors[i%colors.length]" :stroke-width="12" />
            </div>
          </div>
          <el-empty v-else description="暂无数据" />
        </el-card>
      </el-col>
    </el-row>

    <el-card>
      <template #header>规则数据完整性</template>
      <el-table :data="rulesData" stripe size="small">
        <el-table-column prop="key" label="数据项" width="200" />
        <el-table-column prop="value" label="数量">
          <template #default="{row}">
            <el-tag :type="row.value > 0 ? 'success' : 'danger'">{{ row.value }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script>
import api from '../api'

export default {
  data() {
    return {
      stats: {},
      rules: {},
      colors: ['#409EFF', '#67C23A', '#E6A23C', '#F56C6C', '#909399', '#00D4AA', '#FF85C0', '#A78BFA']
    }
  },
  computed: {
    statusDist() {
      const d = this.stats.status_distribution || {}
      const total = this.stats.total_orders || 1
      return [
        { label: '待处理', count: d.PENDING || 0, percent: Math.round((d.PENDING||0)/total*100), color: '#E6A23C' },
        { label: '处理中', count: d.processing || 0, percent: Math.round((d.processing||0)/total*100), color: '#409EFF' },
        { label: '工人完成处理', count: d.worker_completed || 0, percent: Math.round((d.worker_completed||0)/total*100), color: '#00D4AA' },
        { label: '已完成', count: d.completed || 0, percent: Math.round((d.completed||0)/total*100), color: '#67C23A' }
      ]
    },
    subDist() {
      const d = this.stats.subcategory_distribution || []
      const max = d.length > 0 ? d[0].count : 1
      return d.map(item => ({ ...item, percent: Math.round(item.count/max*100) }))
    },
    rulesData() {
      const r = this.rules
      return [
        { key: '子类别定义 (subcategories)', value: r.subcategories_count || 0 },
        { key: '分类规则 (categories)', value: r.categories_count || 0 },
        { key: '触发关键词 (keywords)', value: r.keywords_count || 0 },
        { key: '触发位置 (locations)', value: r.locations_count || 0 },
        { key: '地址映射', value: r.address_mappings_count || 0 },
        { key: '工单总数', value: r.work_orders_count || 0 },
        { key: '维修工人', value: r.workers_count || 0 }
      ]
    }
  },
  methods: {
    statusCount(s) { return (this.stats.status_distribution||{})[s] || 0 }
  },
  async mounted() {
    try { this.stats = await api.getStats() } catch (e) { /* ignore */ }
    try { this.rules = await api.checkRulesCompleteness() } catch (e) { /* ignore */ }
  }
}
</script>