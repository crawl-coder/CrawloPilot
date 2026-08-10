<template>
  <div class="spiders-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>爬虫管理</span>
          <div style="display: flex; gap: 10px; align-items: center">
            <!-- 视图切换(主视图) -->
            <el-radio-group v-model="viewMode" size="small">
              <el-radio-button value="card">
                <el-icon><Grid /></el-icon> 卡片
              </el-radio-button>
              <el-radio-button value="list">
                <el-icon><List /></el-icon> 列表
              </el-radio-button>
            </el-radio-group>
            <el-button type="primary" @click="showCreateDialog">
              <el-icon><Plus /></el-icon> 创建爬虫
            </el-button>
          </div>
        </div>
      </template>

      <!-- 搜索栏 -->
      <el-form :inline="true" :model="searchForm" style="margin-bottom: 20px">
        <el-form-item label="项目">
          <el-select v-model="searchForm.project_id" placeholder="全部" clearable style="width: 200px">
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 150px">
            <el-option label="启用" value="active" />
            <el-option label="已禁用" value="disabled" />
            <el-option label="错误" value="error" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadSpiders">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 爬虫列表 -->
      <div v-loading="loading">
        <!-- 统计信息 -->
        <div v-if="total > 0" style="margin-bottom: 15px; color: #909399; font-size: 13px">
          共 {{ total }} 个爬虫
        </div>
        <!-- 卡片视图 -->
        <div v-if="viewMode === 'card'" class="card-view">
          <el-row :gutter="20">
            <el-col :xs="24" :sm="12" :md="8" :lg="6" v-for="spider in spiders" :key="spider.id">
              <el-card class="spider-card" shadow="hover" @click="viewSpider(spider)">
                <div class="card-header-row">
                  <div class="spider-title">
                    <el-tag 
                      :color="getSpiderTypeColor(spider.spider_type)" 
                      size="small" 
                      style="color: white; border: none; flex-shrink: 0"
                    >
                      {{ spider.spider_type === 'crawlo' ? 'Crawlo⭐' : spider.spider_type }}
                    </el-tag>
                    <el-tooltip :content="spider.name" placement="top" :show-after="300">
                      <span class="spider-name">{{ spider.name }}</span>
                    </el-tooltip>
                  </div>
                  <el-tag :type="getStatusType(spider.status)" size="small" style="flex-shrink: 0">
                    {{ getStatusText(spider.status) }}
                  </el-tag>
                </div>

                <div class="card-info">
                  <div class="info-item">
                    <span class="label">所属项目:</span>
                    <span class="value">{{ getProjectName(spider.project_id) }}</span>
                  </div>
                  <div class="info-item">
                    <span class="label">运行统计:</span>
                    <span class="value">
                      {{ spider.run_count }}次 
                      <span v-if="spider.run_count > 0" style="color: #67C23A">
                        (成功率 {{ ((spider.success_count / spider.run_count) * 100).toFixed(1) }}%)
                      </span>
                    </span>
                  </div>
                  <div class="info-item">
                    <span class="label">最后运行:</span>
                    <span class="value">
                      <template v-if="spider.last_run_at">
                        {{ formatRelativeTime(spider.last_run_at) }}
                        <el-icon :color="spider.last_run_status === 'success' ? '#67C23A' : '#F56C6C'">
                          <component :is="spider.last_run_status === 'success' ? 'CircleCheck' : 'CircleClose'" />
                        </el-icon>
                      </template>
                      <span v-else style="color: #909399">未运行</span>
                    </span>
                  </div>
                </div>

                <div class="card-actions" @click.stop>
                  <el-button size="small" type="success" @click="handleRun(spider)" :disabled="spider.status === 'disabled'">
                    <el-icon><VideoPlay /></el-icon> 运行
                  </el-button>
                  <el-button size="small" @click="viewSpider(spider)">
                    <el-icon><Document /></el-icon> 代码
                  </el-button>
                  <el-dropdown trigger="click" @command="(cmd) => handleCardAction(cmd, spider)">
                    <el-button size="small">
                      <el-icon><More /></el-icon>
                    </el-button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="edit">编辑</el-dropdown-item>
                        <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>
              </el-card>
            </el-col>
          </el-row>

          <el-empty v-if="spiders.length === 0" description="暂无爬虫数据" />
        </div>

        <!-- 仪表盘视图 -->
        <el-table v-else :data="spiders" border stripe>
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="name" label="爬虫名称" width="180" />
          <el-table-column label="所属项目" width="180">
            <template #default="{ row }">
              {{ getProjectName(row.project_id) }}
            </template>
          </el-table-column>
          <el-table-column label="类型" width="140">
            <template #default="{ row }">
              <el-tag 
                :color="getSpiderTypeColor(row.spider_type)" 
                size="small" 
                style="color: white; border: none"
              >
                {{ row.spider_type === 'crawlo' ? 'Crawlo⭐' : row.spider_type }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="getStatusType(row.status)" size="small">
                {{ getStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="运行统计" width="200">
            <template #default="{ row }">
              <div style="font-size: 12px">
                <div>总运行: {{ row.run_count }} 次</div>
                <div v-if="row.run_count > 0">
                  成功: {{ row.success_count }} / 失败: {{ row.error_count }}
                  <el-progress 
                    :percentage="Number(((row.success_count / row.run_count) * 100).toFixed(1))"
                    :stroke-width="4"
                    :show-text="false"
                    style="margin-top: 4px"
                  />
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="最后运行" width="180">
            <template #default="{ row }">
              <div v-if="row.last_run_at">
                <div>{{ formatDate(row.last_run_at) }}</div>
                <el-tag :type="row.last_run_status === 'success' ? 'success' : 'danger'" size="small">
                  {{ row.last_run_status }}
                </el-tag>
              </div>
              <span v-else style="color: #999">未运行</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="350" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="primary" @click="viewSpider(row)">详情</el-button>
              <el-button size="small" type="success" @click="handleRun(row)" :disabled="row.status === 'disabled'">运行</el-button>
              <el-button size="small" @click="showEditDialog(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        
        <!-- 分页组件 -->
        <el-pagination
          v-if="total > 0"
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="pageSizes"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          style="margin-top: 20px; justify-content: flex-end"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <!-- 创建/编辑对话框 - 分步向导（共享组件） -->
    <SpiderFormDialog
      v-model="showDialog"
      :spider="editingSpider"
      :default-project-id="route.query.project_id ? parseInt(route.query.project_id) : null"
      @saved="loadSpiders"
    />

    <!-- 运行爬虫对话框 - 选择节点 -->
    <el-dialog
      v-model="runDialogVisible"
      title="运行爬虫"
      width="420px"
      :close-on-click-modal="false"
    >
      <div style="padding: 10px 0">
        <p style="margin-bottom: 15px; font-size: 14px; color: #606266">
          请选择要运行爬虫 <strong>{{ runningSpider?.name }}</strong> 的目标节点：
        </p>
        <el-select v-model="selectedNodeId" placeholder="请选择节点" style="width: 100%" clearable>
          <el-option :value="null" label="本地运行（不通过远程节点）" />
          <el-option
            v-for="node in nodes"
            :key="node.id"
            :value="node.id"
            :disabled="node.status !== 'online'"
          >
            <span style="display: flex; align-items: center; gap: 6px">
              <el-tag size="small" :type="node.status === 'online' ? 'success' : 'danger'" style="flex-shrink: 0">
                {{ node.status === 'online' ? '在线' : '离线' }}
              </el-tag>
              {{ node.name }}
              <span style="color: #909399; font-size: 12px">({{ node.host }})</span>
            </span>
          </el-option>
        </el-select>

        <!-- 资源限制：Docker 节点生效，本地/SSH/Agent 节点忽略 -->
        <template v-if="selectedNode">
          <el-divider style="margin: 16px 0" />
          <p style="margin-bottom: 10px; font-size: 13px; color: #909399">
            资源限制（仅 Docker 节点生效）
          </p>
          <div style="display: flex; gap: 12px">
            <el-form-item label="内存" label-width="52px" style="margin-bottom: 0">
              <el-select v-model="memoryLimit" style="width: 130px" placeholder="512m">
                <el-option v-for="m in memoryOptions" :key="m" :value="m" :label="m" />
              </el-select>
            </el-form-item>
            <el-form-item label="CPU(核)" label-width="58px" style="margin-bottom: 0">
              <el-input-number
                v-model="cpuLimit"
                :min="0.1"
                :max="32"
                :step="0.5"
                :precision="1"
                style="width: 130px"
                placeholder="1"
              />
            </el-form-item>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="runDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="runLoading" @click="confirmRun">确定运行</el-button>
      </template>
    </el-dialog>


  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Grid, List, VideoPlay, Document, More, CircleCheck, CircleClose, Loading } from '@element-plus/icons-vue'
import { getSpiders, deleteSpider, runSpider } from '@/api/spider'
import { getProjects } from '@/api/project'
import { getNodes } from '@/api/node'
import { getSpiderStatusType as getStatusType, getSpiderStatusText as getStatusText, getSpiderTypeColor, formatDateTime as formatDate, formatRelativeTime, formatDuration as formatTime } from '@/utils/common'
import SpiderFormDialog from '@/components/SpiderFormDialog.vue'

const router = useRouter()
const route = useRoute()
const spiders = ref([])
const projects = ref([])
const loading = ref(false)
const showDialog = ref(false)
const editingSpider = ref(null)
const total = ref(0) // 总数
const currentPage = ref(1) // 当前页
// 每页数量按视图模式初始化：卡片 8（2行×4列），列表 10
const pageSize = ref(localStorage.getItem('spiderViewMode') === 'list' ? 10 : 8)

// 运行爬虫 - 节点选择
const nodes = ref([])
const runDialogVisible = ref(false)
const runningSpider = ref(null)
const selectedNodeId = ref(null)
const runLoading = ref(false)

// 运行资源限制（Docker 节点生效）
const memoryOptions = ['256m', '512m', '1g', '2g', '4g']
const memoryLimit = ref('')
const cpuLimit = ref(1)
const selectedNode = computed(() =>
  nodes.value.find((n) => n.id === selectedNodeId.value) || null
)

const loadNodes = async () => {
  try {
    const res = await getNodes()
    nodes.value = Array.isArray(res) ? res : []
  } catch (e) {
    nodes.value = []
  }
}

// 视图模式 - 从localStorage读取或根据数据量智能选择
const viewMode = ref(localStorage.getItem('spiderViewMode') || null) // null 表示需要根据数据量选择

// 视图选择阈值
const VIEW_THRESHOLD = 12 // 超过12个爬虫时默认使用列表视图

// 智能选择视图模式
const calculateViewMode = (count) => {
  return count > VIEW_THRESHOLD ? 'list' : 'card'
}

// 监听爬虫数据变化,自动调整视图(仅首次)
let isViewModeInitialized = false
watch(spiders, (newSpiders) => {
  if (!isViewModeInitialized && newSpiders.length > 0) {
    const savedMode = localStorage.getItem('spiderViewMode')
    if (!savedMode) {
      const smartMode = calculateViewMode(newSpiders.length)
      if (smartMode !== viewMode.value) {
        viewMode.value = smartMode
        // 智能切换导致每页数量变化时，按新 pageSize 重新加载
        loadSpiders()
      }
    }
    isViewModeInitialized = true
  }
})

// 监听视图模式变化,保存到localStorage
watch(viewMode, (newMode) => {
  localStorage.setItem('spiderViewMode', newMode)
  // 视图切换时调整每页数量：卡片视图 8（2行×4列），列表视图 10
  pageSize.value = newMode === 'card' ? 8 : 10
  currentPage.value = 1
  if (isViewModeInitialized) loadSpiders()
})

// 分页选项随视图模式变化
const pageSizes = computed(() => viewMode.value === 'card' ? [8, 16, 24, 48] : [10, 20, 50, 100])

const searchForm = reactive({
  project_id: null,
  status: null
})

onMounted(() => {
  loadProjects()
  loadNodes()

  // 从URL参数中读取project_id
  if (route.query.project_id) {
    searchForm.project_id = parseInt(route.query.project_id)
  }

  loadSpiders()
})

const loadProjects = async () => {
  try {
    const response = await getProjects({ skip: 0, limit: 1000 })
    // API 返回格式: {items: [...], total: N}
    projects.value = response.items || []
  } catch (error) {
    console.error('加载项目列表失败:', error)
    ElMessage.error('加载项目列表失败')
  }
}

const loadSpiders = async () => {
  try {
    loading.value = true
    const skip = (currentPage.value - 1) * pageSize.value
    const params = {
      ...searchForm,
      skip,
      limit: pageSize.value
    }
    const response = await getSpiders(params)
    spiders.value = response.items || []
    total.value = response.total || 0
  } catch (error) {
    ElMessage.error('加载爬虫列表失败')
  } finally {
    loading.value = false
  }
}

// 分页处理
const handleSizeChange = (size) => {
  pageSize.value = size
  currentPage.value = 1 // 重置到第一页
  loadSpiders()
}

const handleCurrentChange = (page) => {
  currentPage.value = page
  loadSpiders()
}

const resetSearch = () => {
  searchForm.project_id = null
  searchForm.status = null
  currentPage.value = 1 // 重置到第一页
  loadSpiders()
}

const getProjectName = (projectId) => {
  const project = projects.value.find(p => p.id === projectId)
  return project ? project.name : '-'
}

// 卡片操作
const handleCardAction = (command, spider) => {
  if (command === 'edit') {
    showEditDialog(spider)
  } else if (command === 'delete') {
    handleDelete(spider)
  }
}

// 创建/编辑对话框（向导逻辑在 SpiderFormDialog 组件内）
const showCreateDialog = () => {
  editingSpider.value = null
  showDialog.value = true
}

const showEditDialog = (row) => {
  editingSpider.value = row
  showDialog.value = true
}

const viewSpider = (row) => {
  router.push(`/spiders/${row.id}`)
}

const handleRun = async (row) => {
  // 加载节点列表（如果还没加载）
  if (nodes.value.length === 0) {
    await loadNodes()
  }
  runningSpider.value = row
  selectedNodeId.value = null
  memoryLimit.value = ''
  cpuLimit.value = 1
  runDialogVisible.value = true
}

const confirmRun = async () => {
  const spider = runningSpider.value
  if (!spider) return
  runLoading.value = true
  try {
    const payload = { node_id: selectedNodeId.value }
    // 仅 Docker 节点透传资源限制；本地/SSH/Agent 节点忽略
    if (selectedNode.value?.connect_type === 'docker') {
      if (memoryLimit.value) payload.memory_limit = memoryLimit.value
      if (cpuLimit.value) payload.cpu_limit = cpuLimit.value
    }
    await runSpider(spider.id, payload)
    ElMessage.success('爬虫运行指令已发送')
    runDialogVisible.value = false
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '运行失败')
  } finally {
    runLoading.value = false
  }
}


const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要删除爬虫 "${row.name}" 吗？此操作不可恢复。`, '警告', {
      type: 'warning'
    })

    await deleteSpider(row.id)
    ElMessage.success('删除成功')
    loadSpiders()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}
</script>

<style scoped>
.spiders-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 卡片视图样式 */
.card-view {
  min-height: 400px;
}

.spider-card {
  margin-bottom: 20px;
  cursor: pointer;
  transition: all 0.3s;
  height: 100%; /* 确保卡片高度一致 */
  display: flex;
  flex-direction: column;
}

.spider-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

:deep(.spider-card .el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.spider-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0; /* 重要: 允许flex子项收缩 */
}

.spider-name {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: pointer;
  min-width: 0; /* 重要: 允许文本截断 */
}

.card-info {
  margin-bottom: 15px;
}

.info-item {
  display: flex;
  margin-bottom: 8px;
  font-size: 13px;
}

.info-item .label {
  color: #909399;
  min-width: 70px;
  flex-shrink: 0;
}

.info-item .value {
  color: #606266;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-actions {
  display: flex;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--cp-border-light);
}

.card-actions .el-button {
  flex: 1;
}

</style>
