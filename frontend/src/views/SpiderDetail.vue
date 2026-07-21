<template>
  <div class="spider-detail">
    <!-- 顶部操作栏 -->
    <div class="top-bar">
      <div class="top-bar-left">
        <el-button @click="$router.back()">
          <el-icon><Back /></el-icon> 返回
        </el-button>
        <h2 class="spider-title">{{ spider?.name || '爬虫详情' }}</h2>
        <el-tag :color="getSpiderTypeColor(spider?.spider_type)" size="small" style="color: white; border: none">
          {{ spider?.spider_type === 'crawlo' ? 'Crawlo⭐' : spider?.spider_type }}
        </el-tag>
        <el-tag :type="getStatusType(spider?.status)" size="small">
          {{ getStatusText(spider?.status) }}
        </el-tag>
      </div>
      <div class="top-bar-right">
        <el-button type="success" @click="handleRun" :disabled="spider?.status === 'disabled'" :loading="running">
          <el-icon><VideoPlay /></el-icon> 运行
        </el-button>
        <el-button @click="activeTab = 'code'">
          <el-icon><Document /></el-icon> 代码
        </el-button>
        <el-dropdown trigger="click">
          <el-button>
            <el-icon><More /></el-icon> 更多
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="showEditDialog">编辑信息</el-dropdown-item>
              <el-dropdown-item @click="activeTab = 'schedule'">调度配置</el-dropdown-item>
              <el-dropdown-item divided @click="handleDelete" type="danger">删除爬虫</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <!-- Tab 内容 -->
    <el-tabs v-model="activeTab" style="margin-top: 20px">
      <!-- 代码浏览 -->
      <el-tab-pane label="代码结构" name="code">
        <div class="file-browser" v-loading="fileLoading">
          <el-row :gutter="20" style="height: 600px">
            <!-- 文件树 -->
            <el-col :span="8">
              <div class="file-tree-container">
                <div class="tree-header">
                  <el-button size="small" @click="loadFileTree" :icon="Refresh">刷新</el-button>
                  <el-button size="small" type="primary" @click="showCreateDialog">新建</el-button>
                </div>
                <el-tree
                  :data="fileTree"
                  :props="treeProps"
                  node-key="path"
                  default-expand-all
                  :expand-on-click-node="false"
                  @node-click="handleNodeClick"
                >
                  <template #default="{ node, data }">
                    <span class="custom-tree-node">
                      <el-icon v-if="data.type === 'directory'"><Folder /></el-icon>
                      <el-icon v-else><Document /></el-icon>
                      <span style="margin-left: 5px">{{ node.label }}</span>
                      <span class="tree-actions">
                        <el-dropdown trigger="click" @command="(cmd) => handleFileAction(cmd, data)">
                          <el-icon @click.stop><More /></el-icon>
                          <template #dropdown>
                            <el-dropdown-menu>
                              <el-dropdown-item command="rename">重命名</el-dropdown-item>
                              <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                            </el-dropdown-menu>
                          </template>
                        </el-dropdown>
                      </span>
                    </span>
                  </template>
                </el-tree>
              </div>
            </el-col>

            <!-- 文件内容 -->
            <el-col :span="16">
              <div class="file-content-container">
                <div class="content-header" v-if="currentFile">
                  <span class="file-name">{{ currentFile.name }}</span>
                  <el-button size="small" type="primary" @click="saveFile" :loading="saving">
                    保存
                  </el-button>
                </div>
                <div v-if="currentFile && !currentFile.is_binary" class="content-editor">
                  <el-input
                    v-model="fileContent"
                    type="textarea"
                    :rows="30"
                    :autosize="false"
                    placeholder="文件内容"
                  />
                </div>
                <div v-else-if="currentFile?.is_binary" class="binary-file">
                  <el-empty description="二进制文件，无法预览" />
                </div>
                <div v-else class="empty-content">
                  <el-empty description="选择一个文件查看内容" />
                </div>
              </div>
            </el-col>
          </el-row>
        </div>
      </el-tab-pane>

      <!-- 运行监控 -->
      <el-tab-pane label="运行监控" name="monitor">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="运行状态">
            <el-tag :type="getStatusType(spider?.status)">
              {{ getStatusText(spider?.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="运行统计">
            总运行: {{ spider?.run_count }} 次 | 
            成功: {{ spider?.success_count }} | 
            失败: {{ spider?.error_count }}
          </el-descriptions-item>
          <el-descriptions-item label="最后运行">
            {{ spider?.last_run_at ? formatDate(spider.last_run_at) : '未运行' }}
          </el-descriptions-item>
          <el-descriptions-item label="最后状态">
            <el-tag v-if="spider?.last_run_status" :type="spider.last_run_status === 'success' ? 'success' : 'danger'">
              {{ spider.last_run_status }}
            </el-tag>
            <span v-else>-</span>
          </el-descriptions-item>
        </el-descriptions>

        <el-alert title="运行日志功能开发中" type="info" :closable="false" style="margin-top: 20px" />
      </el-tab-pane>

      <!-- 调度配置 -->
      <el-tab-pane label="调度配置" name="schedule">
        <div v-loading="schedulesLoading">
          <div v-if="schedules.length === 0" style="text-align: center; padding: 40px">
            <el-empty description="暂无调度任务" />
            <el-button type="primary" @click="goToCreateSchedule" style="margin-top: 16px">
              创建调度
            </el-button>
          </div>
          <el-table v-else :data="schedules" border style="width: 100%">
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column label="类型" width="100">
              <template #default="{ row }">
                <el-tag v-if="row.schedule_type === 'cron'" type="primary">Cron</el-tag>
                <el-tag v-else-if="row.schedule_type === 'interval'" type="success">间隔</el-tag>
                <el-tag v-else type="info">一次性</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="规则" width="160">
              <template #default="{ row }">
                <span v-if="row.schedule_type === 'cron'">{{ row.cron_expr }}</span>
                <span v-else-if="row.schedule_type === 'interval'">每 {{ row.interval_seconds }} 秒</span>
                <span v-else>{{ row.run_date }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="priority" label="优先级" width="80" />
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag v-if="row.enabled" type="success" size="small">启用</el-tag>
                <el-tag v-else type="info" size="small">禁用</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="下次执行" width="180">
              <template #default="{ row }">
                {{ row.next_run_time || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200">
              <template #default="{ row }">
                <el-button size="small" @click="handleToggleSchedule(row)">
                  {{ row.enabled ? '禁用' : '启用' }}
                </el-button>
                <el-button size="small" type="primary" @click="handleTriggerSchedule(row)">触发</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- Git管理 -->
      <el-tab-pane label="Git管理" name="git">
        <div class="git-manage" v-loading="gitLoading">
          <el-tabs v-model="gitActiveTab">
            <!-- Git操作 -->
            <el-tab-pane label="Git操作" name="operations">
              <el-form :model="gitForm" label-width="120px" style="max-width: 600px">
                <el-form-item label="Git地址">
                  <el-input v-model="gitForm.url" placeholder="https://github.com/user/repo.git" />
                </el-form-item>
                
                <el-form-item label="认证方式">
                  <el-radio-group v-model="gitForm.authType">
                    <el-radio label="password">密码/Token</el-radio>
                    <el-radio label="ssh">SSH密钥</el-radio>
                  </el-radio-group>
                </el-form-item>
                
                <template v-if="gitForm.authType === 'password'">
                  <el-form-item label="用户名">
                    <el-input v-model="gitForm.username" placeholder="可选" />
                  </el-form-item>
                  <el-form-item label="密码/Token">
                    <el-input v-model="gitForm.password" type="password" show-password placeholder="可选" />
                  </el-form-item>
                </template>
                
                <template v-if="gitForm.authType === 'ssh'">
                  <el-form-item label="SSH私钥">
                    <el-input v-model="gitForm.sshKey" type="textarea" :rows="5" placeholder="-----BEGIN OPENSSH PRIVATE KEY-----" />
                  </el-form-item>
                  <el-form-item label="Passphrase">
                    <el-input v-model="gitForm.passphrase" type="password" show-password placeholder="可选" />
                  </el-form-item>
                </template>
                
                <el-form-item label="分支">
                  <el-input v-model="gitForm.branch" placeholder="main" />
                </el-form-item>
                
                <el-form-item>
                  <el-button type="primary" @click="handleGitClone" :loading="gitLoading">克隆仓库</el-button>
                  <el-button @click="handleGitPull" :loading="gitLoading">拉取代码</el-button>
                  <el-button type="warning" @click="handleGitPush" :loading="gitLoading">推送代码</el-button>
                </el-form-item>
              </el-form>
            </el-tab-pane>

            <!-- 分支管理 -->
            <el-tab-pane label="分支管理" name="branches">
              <el-button size="small" @click="loadBranches" style="margin-bottom: 10px">刷新</el-button>
              <el-table :data="branches" border>
                <el-table-column prop="name" label="分支名称" />
                <el-table-column prop="is_current" label="当前" width="80">
                  <template #default="{ row }">
                    <el-tag v-if="row.is_current" type="success" size="small">是</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="100">
                  <template #default="{ row }">
                    <el-button size="small" @click="handleCheckoutBranch(row.name)" :disabled="row.is_current">
                      切换
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>

            <!-- 提交历史 -->
            <el-tab-pane label="提交历史" name="commits">
              <el-button size="small" @click="loadCommits" style="margin-bottom: 10px">刷新</el-button>
              <el-table :data="commits" border>
                <el-table-column prop="hash" label="Hash" width="100">
                  <template #default="{ row }">
                    {{ row.hash.substring(0, 7) }}
                  </template>
                </el-table-column>
                <el-table-column prop="author" label="作者" width="150" />
                <el-table-column prop="message" label="提交信息" />
                <el-table-column prop="date" label="时间" width="180" />
              </el-table>
            </el-tab-pane>

            <!-- 仓库状态 -->
            <el-tab-pane label="仓库状态" name="status">
              <el-button size="small" @click="loadStatus" style="margin-bottom: 10px">刷新</el-button>
              <el-descriptions :column="1" border>
                <el-descriptions-item label="当前分支">{{ gitStatus.branch }}</el-descriptions-item>
                <el-descriptions-item label="已修改">{{ gitStatus.modified?.length || 0 }} 个文件</el-descriptions-item>
                <el-descriptions-item label="已暂存">{{ gitStatus.staged?.length || 0 }} 个文件</el-descriptions-item>
                <el-descriptions-item label="未跟踪">{{ gitStatus.untracked?.length || 0 }} 个文件</el-descriptions-item>
              </el-descriptions>
            </el-tab-pane>
          </el-tabs>
        </div>
      </el-tab-pane>

      <!-- 基本信息 -->
      <el-tab-pane label="基本信息" name="info">
        <div style="text-align: right; margin-bottom: 16px">
          <el-button v-if="!editingInfo" type="primary" size="small" @click="editingInfo = true">
            <el-icon><Edit /></el-icon> 编辑
          </el-button>
          <template v-else>
            <el-button size="small" @click="editingInfo = false">取消</el-button>
            <el-button type="primary" size="small" @click="handleSaveInfo" :loading="savingInfo">保存</el-button>
          </template>
        </div>

        <template v-if="!editingInfo">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="爬虫名称">{{ spider?.name }}</el-descriptions-item>
            <el-descriptions-item label="类型">
              <el-tag :color="getSpiderTypeColor(spider?.spider_type)" style="color: white; border: none">
                {{ spider?.spider_type === 'crawlo' ? 'Crawlo⭐' : spider?.spider_type }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="getStatusType(spider?.status)">
                {{ getStatusText(spider?.status) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="入口文件">{{ spider?.entry_file || '-' }}</el-descriptions-item>
            <el-descriptions-item label="描述" :span="2">{{ spider?.description || '无' }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatDate(spider?.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="更新时间">{{ formatDate(spider?.updated_at) }}</el-descriptions-item>
          </el-descriptions>
        </template>
        <template v-else>
          <el-form :model="editForm" label-width="120px" style="max-width: 600px">
            <el-form-item label="爬虫名称">
              <el-input v-model="editForm.name" />
            </el-form-item>
            <el-form-item label="入口文件">
              <el-input v-model="editForm.entry_file" placeholder="spider.py" />
            </el-form-item>
            <el-form-item label="描述">
              <el-input v-model="editForm.description" type="textarea" :rows="3" />
            </el-form-item>
          </el-form>
        </template>
      </el-tab-pane>
    </el-tabs>

    <!-- 创建文件/目录对话框 -->
    <el-dialog v-model="showCreateFileDialog" :title="'新建' + (createForm.is_directory ? '目录' : '文件')" width="400px">
      <el-form :model="createForm" label-width="60px">
        <el-form-item label="路径">
          <el-input v-model="createForm.path" placeholder="example.py 或 src/example.py" />
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="createForm.is_directory">创建目录</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateFileDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Folder, Document, More, Back, VideoPlay, Delete, Edit } from '@element-plus/icons-vue'
import { getSpider, runSpider, deleteSpider, updateSpider, getSpiderFileTree, getSpiderFileContent, saveSpiderFileContent, createSpiderFileOrDir, deleteSpiderFileOrDir } from '@/api/spider'
import { getSchedules, enableSchedule, disableSchedule, triggerSchedule } from '@/api/schedule'
import { gitClone, gitPull, gitPush, gitGetBranches, gitBranchOperation, gitGetCommits, gitGetStatus } from '@/api/spider-git'

const route = useRoute()
const router = useRouter()
const spiderId = route.params.id

const spider = ref(null)
const activeTab = ref('code') // 默认显示代码结构
const running = ref(false)

// 编辑信息
const editingInfo = ref(false)
const savingInfo = ref(false)
const editForm = reactive({
  name: '',
  entry_file: '',
  description: ''
})

// 调度管理
const schedules = ref([])
const schedulesLoading = ref(false)

// Git管理
const gitActiveTab = ref('operations')
const gitLoading = ref(false)
const branches = ref([])
const commits = ref([])
const gitStatus = ref({})

const gitForm = reactive({
  url: '',
  username: '',
  password: '',
  branch: 'main',
  authType: 'password',
  sshKey: '',
  passphrase: ''
})

// 文件浏览器
const fileLoading = ref(false)
const fileTree = ref([])
const currentFile = ref(null)
const fileContent = ref('')
const saving = ref(false)

const treeProps = {
  children: 'children',
  label: 'name'
}

// 创建对话框
const showCreateFileDialog = ref(false)
const createForm = reactive({
  path: '',
  is_directory: false
})

onMounted(() => {
  loadSpider()
})

// 切换到调度Tab时自动加载
watch(activeTab, (tab) => {
  if (tab === 'schedule' && spider.value) {
    loadSchedules()
  }
})

const loadSpider = async () => {
  try {
    spider.value = await getSpider(spiderId)
  } catch (error) {
    ElMessage.error('加载爬虫信息失败')
  }
}

const loadFileTree = async () => {
  try {
    fileLoading.value = true
    const tree = await getSpiderFileTree(spiderId)
    if (tree.error) {
      ElMessage.warning(tree.error)
      fileTree.value = []
    } else {
      fileTree.value = tree.children || []
    }
  } catch (error) {
    ElMessage.error('加载文件树失败')
  } finally {
    fileLoading.value = false
  }
}

const handleNodeClick = async (data) => {
  if (data.type === 'file') {
    try {
      fileLoading.value = true
      currentFile.value = data
      const result = await getSpiderFileContent(spiderId, data.path)
      
      if (result.error) {
        ElMessage.error(result.error)
        fileContent.value = ''
      } else {
        fileContent.value = result.content
      }
    } catch (error) {
      ElMessage.error('加载文件内容失败')
    } finally {
      fileLoading.value = false
    }
  }
}

const saveFile = async () => {
  if (!currentFile.value) return
  
  try {
    saving.value = true
    await saveSpiderFileContent(spiderId, currentFile.value.path, fileContent.value)
    ElMessage.success('保存成功')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

const showCreateDialog = () => {
  createForm.path = ''
  createForm.is_directory = false
  showCreateFileDialog.value = true
}

const handleCreate = async () => {
  if (!createForm.path) {
    ElMessage.warning('请输入路径')
    return
  }
  
  try {
    await createSpiderFileOrDir(spiderId, createForm.path, createForm.is_directory)
    ElMessage.success('创建成功')
    showCreateFileDialog.value = false
    loadFileTree()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '创建失败')
  }
}

const handleFileAction = async (command, data) => {
  if (command === 'delete') {
    try {
      await ElMessageBox.confirm(`确定要删除 ${data.type === 'directory' ? '目录' : '文件'} "${data.name}" 吗？`, '提示', {
        type: 'warning'
      })
      
      await deleteSpiderFileOrDir(spiderId, data.path)
      ElMessage.success('删除成功')
      
      if (currentFile.value?.path === data.path) {
        currentFile.value = null
        fileContent.value = ''
      }
      
      loadFileTree()
    } catch (error) {
      if (error !== 'cancel') {
        ElMessage.error(error.response?.data?.detail || '删除失败')
      }
    }
  }
}

const getStatusType = (status) => {
  const typeMap = {
    draft: 'info',
    active: 'success',
    disabled: 'warning',
    error: 'danger'
  }
  return typeMap[status] || 'info'
}

const getStatusText = (status) => {
  const textMap = {
    draft: '草稿',
    active: '运行中',
    disabled: '已禁用',
    error: '错误'
  }
  return textMap[status] || status
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const getSpiderTypeColor = (type) => {
  const colorMap = {
    crawlo: '#722ED1',
    scrapy: '#FA8C16',
    selenium: '#1890FF',
    playwright: '#52C41A',
    requests: '#8C8C8C',
    custom: '#13C2C2'
  }
  return colorMap[type] || '#8C8C8C'
}

const loadSchedules = async () => {
  schedulesLoading.value = true
  try {
    const res = await getSchedules({ spider_name: spider.value?.name, limit: 100 })
    schedules.value = res.items || res || []
  } catch (error) {
    console.error('加载调度列表失败', error)
  } finally {
    schedulesLoading.value = false
  }
}

const handleToggleSchedule = async (row) => {
  try {
    if (row.enabled) {
      await disableSchedule(row.id)
      ElMessage.success('已禁用')
    } else {
      await enableSchedule(row.id)
      ElMessage.success('已启用')
    }
    loadSchedules()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const handleTriggerSchedule = async (row) => {
  try {
    await triggerSchedule(row.id)
    ElMessage.success('任务已触发')
  } catch (error) {
    ElMessage.error('触发失败')
  }
}

const goToCreateSchedule = () => {
  router.push('/schedules')
}

const handleRun = async () => {
  try {
    await ElMessageBox.confirm(`确定要运行爬虫 "${spider.value?.name}" 吗？`, '提示', {
      type: 'info'
    })
    
    running.value = true
    await runSpider(spiderId)
    ElMessage.success('爬虫运行指令已发送')
    
    // 刷新爬虫信息
    await loadSpider()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '运行失败')
    }
  } finally {
    running.value = false
  }
}

const handleDelete = async () => {
  try {
    await ElMessageBox.confirm(`确定要删除爬虫 "${spider.value?.name}" 吗？此操作不可恢复。`, '警告', {
      type: 'warning'
    })
    
    await deleteSpider(spiderId)
    ElMessage.success('删除成功')
    router.push('/spiders')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const showEditDialog = () => {
  // 准备编辑表单数据
  editForm.name = spider.value?.name || ''
  editForm.entry_file = spider.value?.entry_file || ''
  editForm.description = spider.value?.description || ''
  editingInfo.value = true
  activeTab.value = 'info'
}

const handleSaveInfo = async () => {
  savingInfo.value = true
  try {
    await updateSpider(spiderId, editForm)
    ElMessage.success('保存成功')
    editingInfo.value = false
    loadSpider()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    savingInfo.value = false
  }
}

// ==================== Git管理 ====================

const handleGitClone = async () => {
  if (!gitForm.url) {
    ElMessage.warning('请输入Git仓库地址')
    return
  }
  
  try {
    gitLoading.value = true
    await gitClone(spiderId, gitForm)
    ElMessage.success('克隆成功')
    
    // 更新爬虫信息
    spider.value.git_url = gitForm.url
    spider.value.git_branch = gitForm.branch
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '克隆失败')
  } finally {
    gitLoading.value = false
  }
}

const handleGitPull = async () => {
  try {
    gitLoading.value = true
    await gitPull(spiderId)
    ElMessage.success('拉取成功')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '拉取失败')
  } finally {
    gitLoading.value = false
  }
}

const handleGitPush = async () => {
  try {
    gitLoading.value = true
    await gitPush(spiderId)
    ElMessage.success('推送成功')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '推送失败')
  } finally {
    gitLoading.value = false
  }
}

const loadBranches = async () => {
  try {
    branches.value = await gitGetBranches(spiderId)
  } catch (error) {
    ElMessage.error('加载分支列表失败')
  }
}

const handleCheckoutBranch = async (branchName) => {
  try {
    await gitBranchOperation(spiderId, {
      branch_name: branchName,
      checkout: true
    })
    ElMessage.success('切换分支成功')
    loadBranches()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '切换分支失败')
  }
}

const loadCommits = async () => {
  try {
    commits.value = await gitGetCommits(spiderId)
  } catch (error) {
    ElMessage.error('加载提交历史失败')
  }
}

const loadStatus = async () => {
  try {
    gitStatus.value = await gitGetStatus(spiderId)
  } catch (error) {
    ElMessage.error('加载仓库状态失败')
  }
}
</script>

<style scoped>
.spider-detail {
  padding: 20px;
}

/* 顶部操作栏 */
.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.top-bar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.spider-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.top-bar-right {
  display: flex;
  gap: 10px;
}

.page-title {
  font-size: 18px;
  font-weight: bold;
}

.file-browser {
  height: 600px;
}

.file-tree-container {
  height: 100%;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  overflow: hidden;
}

.tree-header {
  padding: 10px;
  background: #f5f7fa;
  border-bottom: 1px solid #dcdfe6;
  display: flex;
  gap: 10px;
}

.custom-tree-node {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-right: 8px;
}

.tree-actions {
  display: none;
}

.custom-tree-node:hover .tree-actions {
  display: inline-block;
}

.file-content-container {
  height: 100%;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.content-header {
  padding: 10px;
  background: #f5f7fa;
  border-bottom: 1px solid #dcdfe6;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.file-name {
  font-weight: bold;
  font-size: 14px;
}

.content-editor {
  flex: 1;
  padding: 10px;
  overflow: auto;
}

.binary-file, .empty-content {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
