<template>
  <div class="alerts-container">
    <el-tabs v-model="activeTab">
      <!-- 活跃告警 -->
      <el-tab-pane label="活跃告警" name="active">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>活跃告警</span>
              <el-badge :value="alerts.length" :max="99">
                <el-button @click="loadAlerts" :loading="loading" size="small">
                  <el-icon><Refresh /></el-icon>
                  刷新
                </el-button>
              </el-badge>
            </div>
          </template>
          
          <el-table :data="alerts" v-loading="loading">
            <el-table-column prop="rule_name" label="规则名称" />
            <el-table-column label="严重程度" width="120">
              <template #default="{ row }">
                <el-tag :type="getSeverityType(row.severity)">
                  {{ getSeverityLabel(row.severity) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="当前值" width="120">
              <template #default="{ row }">
                {{ row.value }}
              </template>
            </el-table-column>
            <el-table-column label="阈值" width="120">
              <template #default="{ row }">
                {{ row.threshold }}
              </template>
            </el-table-column>
            <el-table-column label="触发次数" width="120">
              <template #default="{ row }">
                {{ row.trigger_count }}
              </template>
            </el-table-column>
            <el-table-column label="触发时间" width="180">
              <template #default="{ row }">
                {{ row.triggered_at }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="primary" @click="handleResolve(row)">
                  解决
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          
          <el-empty v-if="alerts.length === 0" description="暂无活跃告警" />
        </el-card>
      </el-tab-pane>

      <!-- 告警规则 -->
      <el-tab-pane label="告警规则" name="rules">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>告警规则</span>
              <el-button type="primary" @click="handleCreateRule" size="small">
                <el-icon><Plus /></el-icon>
                创建规则
              </el-button>
            </div>
          </template>
          
          <el-table :data="rules" v-loading="loading">
            <el-table-column prop="name" label="规则名称" />
            <el-table-column prop="metric" label="指标" />
            <el-table-column label="条件" width="150">
              <template #default="{ row }">
                {{ row.operator }} {{ row.threshold }}
              </template>
            </el-table-column>
            <el-table-column label="严重程度" width="120">
              <template #default="{ row }">
                <el-tag :type="getSeverityType(row.severity)">
                  {{ getSeverityLabel(row.severity) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="持续时长" width="120">
              <template #default="{ row }">
                {{ row.duration }}s
              </template>
            </el-table-column>
            <el-table-column label="通知渠道" width="200">
              <template #default="{ row }">
                <el-tag
                  v-for="channel in row.notification_channels"
                  :key="channel"
                  size="small"
                  style="margin-right: 5px"
                >
                  {{ channel }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-switch
                  v-model="row.enabled"
                  @change="handleToggleRule(row)"
                />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="handleEditRule(row)">编辑</el-button>
                <el-button size="small" type="danger" @click="handleDeleteRule(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 告警统计 -->
      <el-tab-pane label="告警统计" name="stats">
        <el-row :gutter="20">
          <el-col :span="8" v-for="stat in alertStats" :key="stat.label">
            <el-card shadow="hover">
              <el-statistic :title="stat.label" :value="stat.value">
                <template #suffix>{{ stat.suffix }}</template>
              </el-statistic>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>

    <!-- 创建/编辑规则对话框 -->
    <el-dialog v-model="ruleDialogVisible" :title="ruleDialogTitle" width="600px">
      <el-form :model="ruleForm" :rules="ruleRules" ref="ruleFormRef" label-width="120px">
        <el-form-item label="规则名称" prop="name">
          <el-input v-model="ruleForm.name" placeholder="输入规则名称" />
        </el-form-item>
        <el-form-item label="监控指标" prop="metric">
          <el-select v-model="ruleForm.metric" placeholder="选择指标">
            <el-option label="CPU 使用率" value="node_cpu_usage_percent" />
            <el-option label="内存使用率" value="node_memory_usage_percent" />
            <el-option label="磁盘使用率" value="node_disk_usage_percent" />
            <el-option label="爬虫成功率" value="spider_success_rate" />
          </el-select>
        </el-form-item>
        <el-form-item label="操作符" prop="operator">
          <el-select v-model="ruleForm.operator">
            <el-option label="大于" value=">" />
            <el-option label="小于" value="<" />
            <el-option label="大于等于" value=">=" />
            <el-option label="小于等于" value="<=" />
            <el-option label="等于" value="==" />
          </el-select>
        </el-form-item>
        <el-form-item label="阈值" prop="threshold">
          <el-input-number v-model="ruleForm.threshold" :precision="2" />
        </el-form-item>
        <el-form-item label="严重程度" prop="severity">
          <el-select v-model="ruleForm.severity">
            <el-option label="警告" value="warning" />
            <el-option label="严重" value="critical" />
            <el-option label="紧急" value="emergency" />
          </el-select>
        </el-form-item>
        <el-form-item label="持续时长(秒)">
          <el-input-number v-model="ruleForm.duration" :min="0" :step="60" />
        </el-form-item>
        <el-form-item label="通知渠道">
          <el-checkbox-group v-model="ruleForm.notification_channels">
            <el-checkbox label="email">邮件</el-checkbox>
            <el-checkbox label="dingtalk">钉钉</el-checkbox>
            <el-checkbox label="wechat">企业微信</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="ruleForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ruleDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveRule" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Plus } from '@element-plus/icons-vue'
import { 
  getActiveAlerts, 
  getAlertRules, 
  getAlertStats,
  createAlertRule,
  updateAlertRule,
  deleteAlertRule,
  resolveAlert
} from '@/api/monitoring'

const activeTab = ref('active')
const loading = ref(false)
const submitting = ref(false)
const alerts = ref([])
const rules = ref([])
const alertStats = ref([])

const ruleDialogVisible = ref(false)
const ruleDialogTitle = ref('创建规则')
const ruleFormRef = ref(null)

const ruleForm = reactive({
  name: '',
  metric: '',
  operator: '>',
  threshold: 80,
  severity: 'warning',
  duration: 300,
  enabled: true,
  notification_channels: ['email']
})

const ruleRules = {
  name: [{ required: true, message: '请输入规则名称', trigger: 'blur' }],
  metric: [{ required: true, message: '请选择监控指标', trigger: 'change' }],
  operator: [{ required: true, message: '请选择操作符', trigger: 'change' }],
  threshold: [{ required: true, message: '请输入阈值', trigger: 'blur' }]
}

const loadAlerts = async () => {
  loading.value = true
  try {
    if (activeTab.value === 'active') {
      alerts.value = await getActiveAlerts()
    } else if (activeTab.value === 'rules') {
      rules.value = await getAlertRules()
    } else if (activeTab.value === 'stats') {
      const stats = await getAlertStats()
      alertStats.value = [
        { label: '总告警数', value: stats.total || 0, suffix: '个' },
        { label: '警告', value: stats.by_severity?.warning || 0, suffix: '个' },
        { label: '严重', value: stats.by_severity?.critical || 0, suffix: '个' }
      ]
    }
  } catch (error) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

const handleResolve = async (row) => {
  try {
    await ElMessageBox.confirm('确定要解决该告警吗？', '提示', {
      type: 'warning'
    })
    await resolveAlert(row.rule_id)
    ElMessage.success('告警已解决')
    loadAlerts()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('解决失败')
    }
  }
}

const handleCreateRule = () => {
  ruleDialogTitle.value = '创建规则'
  Object.assign(ruleForm, {
    name: '',
    metric: '',
    operator: '>',
    threshold: 80,
    severity: 'warning',
    duration: 300,
    enabled: true,
    notification_channels: ['email']
  })
  ruleDialogVisible.value = true
}

const handleEditRule = (row) => {
  ruleDialogTitle.value = '编辑规则'
  Object.assign(ruleForm, row)
  ruleDialogVisible.value = true
}

const handleSaveRule = async () => {
  await ruleFormRef.value.validate()
  submitting.value = true
  
  try {
    if (ruleDialogTitle.value === '创建规则') {
      await createAlertRule(ruleForm)
      ElMessage.success('创建成功')
    } else {
      await updateAlertRule(ruleForm.id, ruleForm)
      ElMessage.success('更新成功')
    }
    ruleDialogVisible.value = false
    loadAlerts()
  } catch (error) {
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

const handleDeleteRule = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该规则吗？', '提示', {
      type: 'warning'
    })
    await deleteAlertRule(row.id)
    ElMessage.success('删除成功')
    loadAlerts()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const handleToggleRule = async (row) => {
  try {
    await updateAlertRule(row.id, { enabled: row.enabled })
    ElMessage.success(row.enabled ? '规则已启用' : '规则已禁用')
  } catch (error) {
    ElMessage.error('操作失败')
    row.enabled = !row.enabled
  }
}

const getSeverityType = (severity) => {
  const map = {
    'warning': 'warning',
    'critical': 'danger',
    'emergency': 'danger'
  }
  return map[severity] || 'info'
}

const getSeverityLabel = (severity) => {
  const map = {
    'warning': '警告',
    'critical': '严重',
    'emergency': '紧急'
  }
  return map[severity] || severity
}

onMounted(() => {
  loadAlerts()
})
</script>

<style scoped>
.alerts-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
