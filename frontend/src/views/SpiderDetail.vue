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
        <el-button @click="editDialogVisible = true">
          <el-icon><Edit /></el-icon> 编辑信息
        </el-button>
        <el-button type="danger" plain @click="handleDelete">
          <el-icon><Delete /></el-icon> 删除
        </el-button>
      </div>
    </div>

    <!-- Tab 内容 -->
    <el-tabs v-model="activeTab" style="margin-top: 20px">
      <!-- 代码浏览 -->
      <el-tab-pane label="代码结构" name="code">
        <!-- Git 工具条（仅 Git 来源的爬虫显示） -->
        <div v-if="spider?.git_url" class="git-bar">
          <el-tooltip content="切换分支" placement="top">
            <div class="git-branch" @click="openBranchDialog">
              <el-icon><Share /></el-icon>
              <span>{{ gitStatus.branch || spider.git_branch || 'main' }}</span>
              <el-icon class="git-branch-caret"><ArrowDown /></el-icon>
            </div>
          </el-tooltip>

          <el-tag v-if="gitStatus.changed_count > 0" type="warning" size="small" effect="plain">
            {{ gitStatus.changed_count }} 个改动
          </el-tag>
          <el-tag v-else-if="gitStatus.is_repo" type="success" size="small" effect="plain">工作区干净</el-tag>

          <template v-if="gitStatus.ahead > 0 || gitStatus.behind > 0">
            <el-tag v-if="gitStatus.ahead > 0" size="small" type="primary" effect="plain">↑{{ gitStatus.ahead }}</el-tag>
            <el-tag v-if="gitStatus.behind > 0" size="small" type="danger" effect="plain">↓{{ gitStatus.behind }}</el-tag>
          </template>

          <div class="git-actions">
            <el-button size="small" type="primary" :disabled="!gitStatus.changed_count" @click="commitDialogVisible = true">
              <el-icon><EditPen /></el-icon> 提交
            </el-button>
            <el-button size="small" @click="handleGitPush" :loading="gitOperating === 'push'">
              <el-icon><Top /></el-icon> 推送
            </el-button>
            <el-button size="small" @click="handleGitPull" :loading="gitOperating === 'pull'">
              <el-icon><Bottom /></el-icon> 拉取
            </el-button>
            <el-button size="small" text @click="loadGitStatus" :loading="gitStatusLoading">
              <el-icon><Refresh /></el-icon>
            </el-button>
          </div>
        </div>

        <div class="file-browser" v-loading="fileLoading">
          <el-row :gutter="20" style="height: 600px">
            <!-- 文件树 -->
            <el-col :span="4">
              <div class="file-tree-container">
                <div class="tree-header">
                  <span class="tree-title">项目文件</span>
                  <el-button size="small" @click="loadFileTree" :icon="Refresh" text>刷新</el-button>
                </div>
                <el-tree
                  :data="fileTree"
                  :props="treeProps"
                  node-key="path"
                  :expand-on-click-node="true"
                  @node-click="handleNodeClick"
                  @node-expand="handleNodeExpand"
                  @node-collapse="handleNodeCollapse"
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
            <el-col :span="20">
              <div class="file-content-container">
                <div class="content-header" v-if="currentFile">
                  <span class="file-name">{{ currentFile.name }}</span>
                  <div class="header-actions">
                    <el-tag size="small" type="info">{{ getLanguage(currentFile.name) }}</el-tag>
                    <el-button size="small" type="primary" @click="toggleEdit" :icon="isEditing ? View : Edit">
                      {{ isEditing ? '预览' : '编辑' }}
                    </el-button>
                    <el-button v-if="isEditing" size="small" type="success" @click="saveFile" :loading="saving" :icon="Check">
                      保存
                    </el-button>
                  </div>
                </div>
                <div v-if="currentFile && !currentFile.is_binary" class="content-editor">
                  <!-- 编辑模式 -->
                  <el-input
                    v-if="isEditing"
                    v-model="fileContent"
                    type="textarea"
                    :rows="30"
                    :autosize="false"
                    placeholder="文件内容"
                    class="code-textarea"
                  />
                  <!-- 预览模式（高亮显示） -->
                  <div v-else class="code-preview">
                    <div class="line-numbers">
                      <span v-for="(_, index) in lineNumbers" :key="index">{{ index + 1 }}</span>
                    </div>
                    <div class="code-scroll">
                      <pre class="code-content"><code :class="'language-' + getLanguage(currentFile.name)" v-html="highlightedCode"></code></pre>
                    </div>
                  </div>
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

      <!-- 运行记录 -->
      <el-tab-pane label="运行记录" name="runs">
        <div v-loading="runsLoading">
          <el-empty v-if="runs.length === 0 && !runsLoading" description="暂无运行记录" />
          <el-table v-else :data="runs" border size="small">
            <el-table-column prop="id" label="任务ID" width="100">
              <template #default="{ row }">
                <el-link type="primary" @click="goTaskDetail(row)">#{{ row.id }}</el-link>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getTaskStatusType(row.status)" size="small">
                  {{ getTaskStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="模式" width="100">
              <template #default="{ row }">
                <el-tag size="small" type="info" effect="plain">{{ row.deploy_mode || 'local' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="节点" width="140">
              <template #default="{ row }">{{ row.node_name || '本机' }}</template>
            </el-table-column>
            <el-table-column label="指标" width="200">
              <template #default="{ row }">
                <span style="font-size: 12px; color: #606266">
                  页 {{ row.pages_crawled || 0 }} / 条 {{ row.items_scraped || 0 }} / 错 {{ row.errors_count || 0 }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="时长" width="90">
              <template #default="{ row }">
                {{ row.duration ? `${Number(row.duration).toFixed(1)}s` : '-' }}
              </template>
            </el-table-column>
            <el-table-column label="开始时间" width="170">
              <template #default="{ row }">{{ formatDate(row.started_at || row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="140">
              <template #default="{ row }">
                <el-button size="small" @click="goTaskDetail(row)">详情</el-button>
                <el-button
                  v-if="row.status === 'failed' || row.status === 'timeout'"
                  size="small"
                  type="primary"
                  @click="handleRetryRun(row)"
                >
                  重试
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-if="runsTotal > 0"
            v-model:current-page="runsPage"
            :page-size="runsPageSize"
            :total="runsTotal"
            layout="total, prev, pager, next"
            style="margin-top: 12px; justify-content: flex-end"
            @current-change="loadRecentRuns"
          />
        </div>
      </el-tab-pane>

      <!-- 基本信息 -->
      <el-tab-pane label="基本信息" name="info">
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
          <!-- 部署节点信息 -->
          <el-descriptions-item label="部署节点" :span="2">
            <template v-if="spider?.deploy_nodes && spider.deploy_nodes.length > 0">
              <div v-for="node in spider.deploy_nodes" :key="node.id" class="deploy-node-item">
                <el-tag type="success" size="small" style="margin-right: 6px">在线</el-tag>
                <span class="node-label">{{ node.name }}</span>
                <span class="node-host">{{ node.host }}:{{ node.port }}</span>
              </div>
            </template>
            <!-- 未部署到远程节点时，默认在本机运行 -->
            <div v-else class="deploy-node-item">
              <el-tag type="info" size="small" style="margin-right: 6px">默认</el-tag>
              <span class="node-label">本机</span>
              <span class="node-host">local</span>
            </div>
          </el-descriptions-item>
        </el-descriptions>
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

    <!-- 运行爬虫对话框 -->
    <el-dialog v-model="showRunDialog" title="运行爬虫" width="500px">
      <el-form label-width="100px">
        <el-form-item label="运行模式">
          <el-radio-group v-model="runForm.mode">
            <el-radio label="local">本地运行</el-radio>
            <el-radio label="node">部署到节点</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="目标节点" v-if="runForm.mode === 'node'">
          <el-select v-model="runForm.nodeId" placeholder="请选择节点" style="width: 100%" :loading="nodesLoading">
            <el-option
              v-for="node in availableNodes"
              :key="node.id"
              :label="`${node.name} (${node.ssh_host || node.host}:${node.ssh_port || node.port})`"
              :value="node.id"
            >
              <span>{{ node.name }}</span>
              <el-tag 
                :type="node.status === 'online' ? 'success' : 'danger'" 
                size="small" 
                style="margin-left: 8px"
              >
                {{ node.status === 'online' ? '在线' : '离线' }}
              </el-tag>
              <el-tag size="small" style="margin-left: 4px">
                {{ node.connect_type === 'ssh' ? 'SSH' : node.connect_type }}
              </el-tag>
            </el-option>
          </el-select>
          <div v-if="availableNodes.length === 0" style="color: #909399; font-size: 12px; margin-top: 4px">
            暂无可用节点，请先添加节点
          </div>
        </el-form-item>
        <el-form-item label="部署信息" v-if="runForm.mode === 'node' && selectedNode">
          <div style="font-size: 13px; line-height: 1.8">
            <div><strong>主机:</strong> {{ selectedNode.ssh_host || selectedNode.host }}</div>
            <div><strong>端口:</strong> {{ selectedNode.ssh_port || selectedNode.port }}</div>
            <div><strong>连接方式:</strong> {{ selectedNode.connect_type }}</div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRunDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmRun" :loading="running">确认运行</el-button>
      </template>
    </el-dialog>

    <!-- Git 提交对话框 -->
    <el-dialog v-model="commitDialogVisible" title="提交改动" width="520px" @open="commitMessage = ''">
      <el-alert type="info" :closable="false" style="margin-bottom: 12px">
        将提交 {{ gitStatus.changed_count }} 个文件到分支 <strong>{{ gitStatus.branch }}</strong>（提交人：当前登录用户）
      </el-alert>
      <div v-if="gitStatus.changed_files?.length" class="changed-files">
        <div v-for="f in gitStatus.changed_files.slice(0, 8)" :key="f" class="changed-file">{{ f }}</div>
        <div v-if="gitStatus.changed_files.length > 8" class="changed-file more">
          ... 共 {{ gitStatus.changed_files.length }} 个文件
        </div>
      </div>
      <el-input
        v-model="commitMessage"
        type="textarea"
        :rows="3"
        placeholder="提交信息，例如: fix: 修复价格解析空指针"
        style="margin-top: 12px"
      />
      <template #footer>
        <el-button @click="commitDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleGitCommit" :loading="gitOperating === 'commit'"
                   :disabled="!commitMessage.trim()">提交</el-button>
      </template>
    </el-dialog>

    <!-- Git 分支切换对话框 -->
    <el-dialog v-model="branchDialogVisible" title="切换分支" width="480px">
      <el-tabs v-model="branchTab">
        <el-tab-pane label="已有分支" name="existing">
          <el-select v-model="selectedBranch" placeholder="选择分支" style="width: 100%" filterable>
            <el-option-group label="本地分支">
              <el-option v-for="b in gitBranches.local" :key="b" :label="b" :value="b"
                         :disabled="b === gitBranches.current" />
            </el-option-group>
            <el-option-group label="远程分支">
              <el-option v-for="b in remoteBranchNames" :key="b" :label="b" :value="b" />
            </el-option-group>
          </el-select>
        </el-tab-pane>
        <el-tab-pane label="新建分支" name="create">
          <el-input v-model="newBranchName" placeholder="新分支名，基于当前分支创建" />
        </el-tab-pane>
      </el-tabs>
      <template #footer>
        <el-button @click="branchDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleGitCheckout" :loading="gitOperating === 'checkout'">切换</el-button>
      </template>
    </el-dialog>

    <!-- 编辑爬虫对话框（共享向导组件） -->
    <SpiderFormDialog
      v-if="spider"
      v-model="editDialogVisible"
      :spider="spider"
      @saved="onEditSaved"
    />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Folder, Document, More, Back, VideoPlay, Delete, Edit, View, Check, Share, ArrowDown, EditPen, Top, Bottom } from '@element-plus/icons-vue'
import { getSpider, runSpider, deleteSpider, getSpiderFileTree, getSpiderFileContent, saveSpiderFileContent, createSpiderFileOrDir, deleteSpiderFileOrDir, getGitStatus, getGitBranches, gitCommit, gitPush, gitPull, gitCheckout } from '@/api/spider'
import SpiderFormDialog from '@/components/SpiderFormDialog.vue'
import { listTasks, retryTask } from '@/api/execution'
import { getSpiderStatusType as getStatusType, getSpiderStatusText as getStatusText, getSpiderTypeColor, formatDateTime as formatDate } from '@/utils/common'
import { getTaskStatusType, getTaskStatusText } from '@/utils/common'
import { getNodes } from '@/api/node'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'

const route = useRoute()
const router = useRouter()
const spiderId = route.params.id

const spider = ref(null)
const activeTab = ref('code') // 默认显示代码结构
const running = ref(false)

// 运行对话框
const showRunDialog = ref(false)
const nodesLoading = ref(false)
const availableNodes = ref([])
const runForm = reactive({
  mode: 'local',
  nodeId: null
})
const selectedNode = computed(() => {
  if (!runForm.nodeId) return null
  return availableNodes.value.find(n => n.id === runForm.nodeId) || null
})

// 运行记录
const runs = ref([])
const runsLoading = ref(false)
const runsTotal = ref(0)
const runsPage = ref(1)
const runsPageSize = ref(10)

const loadRecentRuns = async () => {
  runsLoading.value = true
  try {
    const res = await listTasks({
      spider_id: spiderId,
      limit: runsPageSize.value,
      offset: (runsPage.value - 1) * runsPageSize.value
    })
    runs.value = res.items || []
    runsTotal.value = res.total || 0
  } catch (error) {
    ElMessage.error('加载运行记录失败')
  } finally {
    runsLoading.value = false
  }
}

const goTaskDetail = (row) => {
  router.push(`/tasks/${row.id}`)
}

const handleRetryRun = async (row) => {
  try {
    const res = await retryTask(row.id)
    ElMessage.success(`重试已提交: 新任务 #${res.task_id}`)
    loadRecentRuns()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '重试失败')
  }
}

watch(activeTab, (tab) => {
  if (tab === 'runs') {
    loadRecentRuns()
  }
})

// 文件浏览器
const fileLoading = ref(false)
const fileTree = ref([])
const currentFile = ref(null)
const fileContent = ref('')
const saving = ref(false)
const isEditing = ref(false)

const treeProps = {
  children: 'children',
  label: 'name'
}

// 代码高亮
const highlightedCode = computed(() => {
  if (!fileContent.value) return ''
  const lang = getLanguage(currentFile.value?.name || '')
  try {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(fileContent.value, { language: lang }).value
    }
    return hljs.highlightAuto(fileContent.value).value
  } catch (e) {
    return fileContent.value
  }
})

const lineNumbers = computed(() => {
  if (!fileContent.value) return []
  return fileContent.value.split('\n')
})

// 根据文件名检测语言
const getLanguage = (filename) => {
  if (!filename) return 'text'
  const ext = filename.split('.').pop().toLowerCase()
  const langMap = {
    'py': 'python',
    'js': 'javascript',
    'ts': 'typescript',
    'jsx': 'javascript',
    'tsx': 'typescript',
    'vue': 'xml',
    'html': 'html',
    'css': 'css',
    'scss': 'scss',
    'less': 'less',
    'json': 'json',
    'yaml': 'yaml',
    'yml': 'yaml',
    'xml': 'xml',
    'md': 'markdown',
    'sh': 'bash',
    'bash': 'bash',
    'sql': 'sql',
    'java': 'java',
    'go': 'go',
    'rs': 'rust',
    'rb': 'ruby',
    'php': 'php',
    'c': 'c',
    'cpp': 'cpp',
    'h': 'c',
    'ini': 'ini',
    'cfg': 'ini',
    'conf': 'ini',
    'toml': 'toml',
    'txt': 'text',
  }
  return langMap[ext] || 'text'
}

const toggleEdit = () => {
  isEditing.value = !isEditing.value
}

// 创建对话框
const showCreateFileDialog = ref(false)
const createForm = reactive({
  path: '',
  is_directory: false
})

onMounted(() => {
  loadSpider()
  loadFileTree()  // 自动加载文件树
  loadGitStatus()
})

// ==================== Git 工作流 ====================
const gitStatus = ref({ is_repo: false, branch: '', changed_count: 0, changed_files: [], ahead: 0, behind: 0 })
const gitBranches = ref({ current: '', local: [], remote: [] })
const gitStatusLoading = ref(false)
const gitOperating = ref('') // 'commit' | 'push' | 'pull' | 'checkout'
const commitDialogVisible = ref(false)
const commitMessage = ref('')
const branchDialogVisible = ref(false)
const branchTab = ref('existing')
const selectedBranch = ref('')
const newBranchName = ref('')

// 远程分支显示名（去掉 origin/ 前缀）
const remoteBranchNames = computed(() =>
  (gitBranches.value.remote || []).map(b => b.replace(/^[^/]+\//, ''))
)

const loadGitStatus = async () => {
  if (!spider.value?.git_url) return
  gitStatusLoading.value = true
  try {
    gitStatus.value = await getGitStatus(spiderId)
  } catch (e) {
    // 非仓库或读取失败时不打扰用户
    gitStatus.value = { is_repo: false, changed_count: 0 }
  } finally {
    gitStatusLoading.value = false
  }
}

const openBranchDialog = async () => {
  branchDialogVisible.value = true
  branchTab.value = 'existing'
  selectedBranch.value = ''
  newBranchName.value = ''
  try {
    gitBranches.value = await getGitBranches(spiderId)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '读取分支失败')
  }
}

const runGitOp = async (op, fn, successMsg) => {
  gitOperating.value = op
  try {
    const res = await fn()
    ElMessage.success(res?.message || successMsg)
    await Promise.all([loadGitStatus(), loadFileTree()])
    return true
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '操作失败')
    return false
  } finally {
    gitOperating.value = ''
  }
}

const handleGitCommit = () =>
  runGitOp('commit', () => gitCommit(spiderId, commitMessage.value), '提交成功')
    .then(ok => { if (ok) commitDialogVisible.value = false })

const handleGitPush = () =>
  runGitOp('push', () => gitPush(spiderId), '推送成功')

const handleGitPull = () =>
  runGitOp('pull', () => gitPull(spiderId), '拉取完成')

const handleGitCheckout = () => {
  const isCreate = branchTab.value === 'create'
  const branch = isCreate ? newBranchName.value.trim() : selectedBranch.value
  if (!branch) {
    ElMessage.warning(isCreate ? '请输入新分支名' : '请选择分支')
    return
  }
  runGitOp('checkout', () => gitCheckout(spiderId, branch, isCreate), '切换成功')
    .then(ok => { if (ok) branchDialogVisible.value = false })
}

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
      // 如果返回的是带 children 的树结构，取第一层 children 作为根节点列表
      // 如果返回的已经是数组，直接使用
      if (tree.children) {
        fileTree.value = tree.children
      } else if (Array.isArray(tree)) {
        fileTree.value = tree
      } else {
        fileTree.value = []
      }
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
      isEditing.value = false  // 默认预览模式
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

// 节点展开/折叠处理
const handleNodeExpand = (data) => {
  // 可以在这里添加展开时的处理逻辑
}

const handleNodeCollapse = (data) => {
  // 可以在这里添加折叠时的处理逻辑
}

const saveFile = async () => {
  if (!currentFile.value) return
  
  try {
    saving.value = true
    await saveSpiderFileContent(spiderId, currentFile.value.path, fileContent.value)
    ElMessage.success('保存成功')
    loadGitStatus() // 保存后刷新改动数
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

// 编辑对话框（共享向导组件，编辑模式）
const editDialogVisible = ref(false)
const onEditSaved = () => {
  loadSpider() // 编辑保存后刷新详情
}

const handleRun = async () => {
  // 加载可用节点
  try {
    nodesLoading.value = true
    const nodes = await getNodes({ limit: 100 })
    if (Array.isArray(nodes)) {
      availableNodes.value = nodes
    } else if (nodes?.items) {
      availableNodes.value = nodes.items
    } else {
      availableNodes.value = []
    }
  } catch (error) {
    availableNodes.value = []
  } finally {
    nodesLoading.value = false
  }
  
  // 打开运行对话框
  runForm.mode = 'local'
  runForm.nodeId = null
  showRunDialog.value = true
}

const confirmRun = async () => {
  try {
    running.value = true
    
    const data = {}
    if (runForm.mode === 'node' && runForm.nodeId) {
      data.node_id = runForm.nodeId
    }
    
    const res = await runSpider(spiderId, data)
    ElMessage.success('爬虫运行指令已发送')
    showRunDialog.value = false
    
    // 刷新爬虫信息
    await loadSpider()

    // 跳转到任务详情，形成「运行 → 执行详情」闭环
    if (res?.task_id) {
      router.push(`/tasks/${res.task_id}`)
    }
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

/* 修复: el-col 由 flex stretch 得到的高度不被 height:100% 子元素当作确定值，
   导致代码预览区高度链条塌陷无法滚动，显式锁定列高 */
.file-browser :deep(.el-col) {
  height: 100%;
}

.file-tree-container {
  height: 100%;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  overflow: hidden;
  background: #fafafa;
}

.tree-header {
  padding: 10px 14px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: space-between;
  user-select: none;
}

.tree-title {
  font-size: 13px;
  font-weight: 600;
  color: #606266;
}

.custom-tree-node {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 6px;
  padding: 0 8px 0 0;
  color: #303133;
  min-width: 0;
  font-size: 13px;
}

.custom-tree-node span:not(.tree-actions) {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tree-actions {
  display: none;
  flex-shrink: 0;
}

/* 覆盖 el-tree 默认样式 */
:deep(.el-tree) {
  background: #fafafa;
  --el-tree-node-hover-bg-color: #f0f0f0;
  --el-tree-text-color: #303133;
  --el-tree-expand-icon-color: #909399;
}

:deep(.el-tree-node__content) {
  height: 30px;
  background: transparent;
}

:deep(.el-tree-node__content:hover) {
  background: #f0f0f0;
}

:deep(.el-tree-node__expand-icon) {
  color: #909399;
  font-size: 12px;
}

:deep(.el-tree-node__expand-icon.is-leaf) {
  color: transparent;
}

:deep(.el-tree-node:focus > .el-tree-node__content) {
  background: #e8f4ff;
}

:deep(.el-tree__empty-block) {
  background: #fafafa;
}

.file-content-container {
  height: 100%;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.content-header {
  padding: 10px 14px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-name {
  font-weight: 600;
  font-size: 13px;
  color: #303133;
}

.content-editor {
  flex: 1;
  overflow: hidden;
  background: #fafafa;
}

.code-textarea {
  height: 100%;
}

.code-textarea :deep(.el-textarea__inner) {
  height: 100% !important;
  background: #fafafa;
  color: #303133;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  border: none;
  border-radius: 0;
  resize: none;
  padding: 16px;
}

.code-preview {
  display: flex;
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  background: #fafafa;
}

.line-numbers {
  padding: 16px 8px 16px 16px;
  background: #f5f7fa;
  border-right: 1px solid #e4e7ed;
  user-select: none;
  text-align: right;
  flex-shrink: 0;
  align-self: flex-start;
  min-width: 36px;
  position: sticky;
  left: 0;
  z-index: 1;
}

.line-numbers span {
  display: block;
  color: #c0c4cc;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  min-height: 20.8px;
}

.code-scroll {
  flex: 1;
  min-width: 0;
  align-self: flex-start;
  overflow-x: auto;
}

.code-content {
  margin: 0;
  padding: 16px 20px;
  white-space: pre;
  background: transparent;
}

.code-content code {
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  background: transparent;
  padding: 0;
}

/* highlight.js 覆盖 - 浅色模式 */
.code-content :deep(.hljs) {
  background: transparent !important;
  padding: 0 !important;
  color: #303133;
}

/* 部署节点样式 */
.deploy-node-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.node-label {
  font-weight: 500;
  color: #303133;
}

.node-host {
  color: #909399;
  font-size: 12px;
}

.no-node {
  color: #909399;
}

.binary-file, .empty-content {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* ===== Git 工具条 ===== */
.git-bar {
  display: flex;
  align-items: center;
  gap: var(--cp-space-sm);
  padding: 8px 12px;
  margin-bottom: 12px;
  background: var(--cp-card-bg);
  border: 1px solid var(--cp-border-light);
  border-radius: var(--cp-radius-sm);
}

.git-branch {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border-radius: var(--cp-radius-sm);
  background: var(--cp-page-bg);
  border: 1px solid var(--cp-border-light);
  font-size: 13px;
  font-weight: 600;
  color: var(--cp-text-primary);
  cursor: pointer;
  transition: all var(--cp-motion-fast) ease;
}

.git-branch:hover {
  border-color: var(--cp-primary);
  color: var(--cp-primary);
}

.git-branch-caret {
  font-size: 12px;
  color: var(--cp-text-secondary);
}

.git-actions {
  margin-left: auto;
  display: flex;
  gap: 6px;
}

.changed-files {
  max-height: 140px;
  overflow-y: auto;
  background: var(--cp-page-bg);
  border-radius: var(--cp-radius-sm);
  padding: 8px 12px;
}

.changed-file {
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  font-size: 12px;
  color: var(--cp-text-regular);
  line-height: 1.8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.changed-file.more {
  color: var(--cp-text-secondary);
}
</style>
