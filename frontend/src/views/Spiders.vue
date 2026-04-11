<template>
  <div class="spiders-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>爬虫管理</span>
          <div style="display: flex; gap: 10px; align-items: center">
            <!-- 视图切换 -->
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
            <el-option label="草稿" value="draft" />
            <el-option label="运行中" value="active" />
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
                      style="color: white; border: none"
                    >
                      {{ spider.spider_type === 'crawlo' ? 'Crawlo⭐' : spider.spider_type }}
                    </el-tag>
                    <span class="spider-name">{{ spider.name }}</span>
                  </div>
                  <el-tag :type="getStatusType(spider.status)" size="small">
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

        <!-- 列表视图 -->
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
                    :percentage="((row.success_count / row.run_count) * 100).toFixed(1)" 
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
          <el-table-column label="操作" width="280" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="primary" @click="viewSpider(row)">详情</el-button>
              <el-button size="small" type="success" @click="handleRun(row)" :disabled="row.status === 'disabled'">运行</el-button>
              <el-button size="small" @click="showEditDialog(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <!-- 创建/编辑对话框 - 分步向导 -->
    <el-dialog
      v-model="showDialog"
      :title="editingSpider ? '编辑爬虫' : '创建爬虫'"
      width="700px"
      :close-on-click-modal="false"
    >
      <!-- 步骤条 -->
      <el-steps :active="currentStep" finish-status="success" v-if="!editingSpider" style="margin-bottom: 30px">
        <el-step title="基本信息" />
        <el-step title="代码来源" />
        <el-step title="运行配置" />
      </el-steps>

      <el-form :model="spiderForm" :rules="rules" ref="formRef" label-width="120px">
        <!-- 步骤1: 基本信息 -->
        <div v-show="currentStep === 0">
          <el-form-item label="爬虫名称" prop="name">
            <el-input v-model="spiderForm.name" placeholder="请输入爬虫名称" />
          </el-form-item>

          <el-form-item label="所属项目" prop="project_id">
            <el-select v-model="spiderForm.project_id" placeholder="请选择项目" style="width: 100%">
              <el-option
                v-for="project in projects"
                :key="project.id"
                :label="project.name"
                :value="project.id"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="爬虫类型" prop="spider_type">
            <el-select v-model="spiderForm.spider_type" style="width: 100%">
              <el-option label="Crawlo ⭐推荐" value="crawlo">
                <span style="float: left">Crawlo</span>
                <span style="float: right; color: #8492a6; font-size: 13px; margin-left: 10px">⭐推荐 - 分布式爬虫框架</span>
              </el-option>
              <el-option label="Scrapy" value="scrapy">
                <span style="float: left">Scrapy</span>
                <span style="float: right; color: #8492a6; font-size: 13px; margin-left: 10px">Python爬虫框架</span>
              </el-option>
              <el-option label="Selenium" value="selenium">
                <span style="float: left">Selenium</span>
                <span style="float: right; color: #8492a6; font-size: 13px; margin-left: 10px">浏览器自动化</span>
              </el-option>
              <el-option label="Playwright" value="playwright">
                <span style="float: left">Playwright</span>
                <span style="float: right; color: #8492a6; font-size: 13px; margin-left: 10px">现代浏览器自动化</span>
              </el-option>
              <el-option label="Requests" value="requests">
                <span style="float: left">Requests</span>
                <span style="float: right; color: #8492a6; font-size: 13px; margin-left: 10px">HTTP请求库</span>
              </el-option>
              <el-option label="自定义" value="custom">
                <span style="float: left">自定义</span>
                <span style="float: right; color: #8492a6; font-size: 13px; margin-left: 10px">其他框架或脚本</span>
              </el-option>
            </el-select>
          </el-form-item>

          <el-form-item label="描述">
            <el-input
              v-model="spiderForm.description"
              type="textarea"
              :rows="3"
              placeholder="请输入爬虫描述"
            />
          </el-form-item>

          <el-alert
            title="提示"
            type="info"
            :closable="false"
            show-icon
            style="margin-top: 10px"
          >
            <template #default>
              <div style="font-size: 13px">
                <strong>Crawlo 框架优势:</strong> 分布式架构、智能反反爬、自动去重、增量采集、性能监控
              </div>
            </template>
          </el-alert>
        </div>

        <!-- 步骤2: 代码来源 -->
        <div v-show="currentStep === 1 && !editingSpider">
          <el-form-item label="代码来源">
            <el-radio-group v-model="spiderForm.code_source" @change="onCodeSourceChange">
              <el-radio-button value="git">Git 仓库</el-radio-button>
              <el-radio-button value="upload">本地上传</el-radio-button>
              <el-radio-button value="empty">空爬虫</el-radio-button>
            </el-radio-group>
          </el-form-item>

          <!-- Git 仓库 -->
          <div v-show="spiderForm.code_source === 'git'">
            <el-form-item label="Git地址" prop="git_url">
              <el-input v-model="spiderForm.git_url" placeholder="https://github.com/user/repo.git" />
            </el-form-item>

            <el-form-item label="认证方式">
              <el-radio-group v-model="spiderForm.git_auth_type">
                <el-radio label="password">密码/Token</el-radio>
                <el-radio label="ssh">SSH密钥</el-radio>
              </el-radio-group>
            </el-form-item>

            <template v-if="spiderForm.git_auth_type === 'password'">
              <el-form-item label="用户名">
                <el-input v-model="spiderForm.git_username" placeholder="可选" />
              </el-form-item>
              <el-form-item label="密码/Token">
                <el-input v-model="spiderForm.git_password" type="password" show-password placeholder="可选" />
              </el-form-item>
            </template>

            <template v-if="spiderForm.git_auth_type === 'ssh'">
              <el-form-item label="SSH私钥">
                <el-input v-model="spiderForm.git_ssh_key" type="textarea" :rows="4" placeholder="-----BEGIN OPENSSH PRIVATE KEY-----" />
              </el-form-item>
            </template>

            <el-form-item label="分支">
              <el-input v-model="spiderForm.git_branch" placeholder="main" />
            </el-form-item>

            <el-alert
              title="提示"
              type="info"
              :closable="false"
              show-icon
            >
              <template #default>
                <div style="font-size: 13px">
                  创建时将自动克隆仓库代码。请确保仓库包含完整的爬虫项目文件。
                </div>
              </template>
            </el-alert>
          </div>

          <!-- 本地上传 -->
          <div v-show="spiderForm.code_source === 'upload'">
            <el-form-item label="上传代码">
              <el-upload
                drag
                action="#"
                :auto-upload="false"
                :limit="1"
                accept=".zip"
                :on-change="handleFileChange"
                :before-upload="beforeUpload"
              >
                <el-icon class="el-icon--upload"><upload-filled /></el-icon>
                <div class="el-upload__text">
                  拖拽文件到此处或 <em>点击上传</em>
                </div>
                <template #tip>
                  <div class="el-upload__tip">
                    仅支持 .zip 格式文件，大小不超过 100MB
                  </div>
                </template>
              </el-upload>
            </el-form-item>

            <el-alert
              title="提示"
              type="info"
              :closable="false"
              show-icon
            >
              <template #default>
                <div style="font-size: 13px">
                  请上传包含完整爬虫项目的 ZIP 文件。系统会自动解压并识别项目结构。
                </div>
              </template>
            </el-alert>
          </div>

          <!-- 空爬虫 -->
          <div v-show="spiderForm.code_source === 'empty'">
            <el-alert
              title="创建空爬虫"
              type="success"
              :closable="false"
              show-icon
            >
              <template #default>
                <div style="font-size: 13px">
                  系统将创建基础目录结构和模板文件。您可以在创建后通过代码编辑器编写爬虫逻辑。
                  <br/><br/>
                  <strong>自动生成的文件:</strong>
                  <ul style="margin: 5px 0; padding-left: 20px">
                    <li>main.py - 爬虫入口文件</li>
                    <li>config.json - 配置文件</li>
                    <li>README.md - 说明文档</li>
                  </ul>
                </div>
              </template>
            </el-alert>
          </div>
        </div>

        <!-- 步骤3: 运行配置 -->
        <div v-show="currentStep === 2 && !editingSpider">
          <el-form-item label="入口文件" prop="entry_file">
            <el-input v-model="spiderForm.entry_file" placeholder="例如: main.py 或 spiders/example.py" />
          </el-form-item>

          <el-form-item label="定时调度">
            <el-switch v-model="spiderForm.schedule_enabled" />
            <span style="margin-left: 10px; color: #909399; font-size: 13px">
              {{ spiderForm.schedule_enabled ? '已开启' : '已关闭' }}
            </span>
          </el-form-item>

          <template v-if="spiderForm.schedule_enabled">
            <el-form-item label="Cron表达式">
              <el-input v-model="spiderForm.cron_expr" placeholder="例如: 0 */2 * * * (每2小时)" />
            </el-form-item>
          </template>

          <el-form-item label="超时时间(秒)">
            <el-input-number v-model="spiderForm.timeout_seconds" :min="60" :max="86400" :step="300" />
            <span style="margin-left: 10px; color: #909399; font-size: 13px">
              {{ formatTime(spiderForm.timeout_seconds) }}
            </span>
          </el-form-item>

          <el-form-item label="重试次数">
            <el-input-number v-model="spiderForm.retry_count" :min="0" :max="10" />
            <span style="margin-left: 10px; color: #909399; font-size: 13px">
              失败后自动重试次数
            </span>
          </el-form-item>
        </div>

        <!-- 编辑模式下的状态选择 -->
        <el-form-item v-if="editingSpider" label="状态">
          <el-select v-model="spiderForm.status" style="width: 100%">
            <el-option label="草稿" value="draft" />
            <el-option label="运行中" value="active" />
            <el-option label="已禁用" value="disabled" />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <div style="display: flex; justify-content: space-between">
          <el-button @click="showDialog = false">取消</el-button>
          <div>
            <el-button v-if="currentStep > 0 && !editingSpider" @click="currentStep--">上一步</el-button>
            <el-button v-if="currentStep < 2 && !editingSpider" type="primary" @click="nextStep">下一步</el-button>
            <el-button v-else type="primary" @click="handleSubmit" :loading="submitting">确定</el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, UploadFilled, Grid, List, VideoPlay, Document, More, CircleCheck, CircleClose } from '@element-plus/icons-vue'
import { getSpiders, createSpider, updateSpider, deleteSpider, runSpider } from '@/api/spider'
import { getProjects } from '@/api/project'

const router = useRouter()
const route = useRoute()
const spiders = ref([])
const projects = ref([])
const loading = ref(false)
const submitting = ref(false)
const showDialog = ref(false)
const editingSpider = ref(null)
const formRef = ref(null)

// 分步向导
const currentStep = ref(0)
const uploadFile = ref(null)

// 视图模式
const viewMode = ref('card') // 'card' 或 'list'

const searchForm = reactive({
  project_id: null,
  status: null
})

const spiderForm = reactive({
  // 步骤1
  name: '',
  project_id: null,
  spider_type: 'crawlo', // 默认 Crawlo
  description: '',
  
  // 步骤2
  code_source: 'git',
  git_url: '',
  git_auth_type: 'password',
  git_username: '',
  git_password: '',
  git_ssh_key: '',
  git_branch: 'main',
  
  // 步骤3
  entry_file: 'main.py',
  schedule_enabled: false,
  cron_expr: '',
  timeout_seconds: 3600,
  retry_count: 3,
  
  status: 'draft'
})

const rules = {
  name: [{ required: true, message: '请输入爬虫名称', trigger: 'blur' }],
  project_id: [{ required: true, message: '请选择项目', trigger: 'change' }],
  spider_type: [{ required: true, message: '请选择爬虫类型', trigger: 'change' }],
  git_url: [{ 
    required: true, 
    message: '请输入Git仓库地址', 
    trigger: 'blur',
    validator: (rule, value, callback) => {
      if (spiderForm.code_source === 'git' && !value) {
        callback(new Error('请输入Git仓库地址'))
      } else {
        callback()
      }
    }
  }]
}

onMounted(() => {
  loadProjects()
  
  // 从URL参数中读取project_id
  if (route.query.project_id) {
    searchForm.project_id = parseInt(route.query.project_id)
    spiderForm.project_id = parseInt(route.query.project_id)
  }
  
  loadSpiders()
})

const loadProjects = async () => {
  try {
    projects.value = await getProjects()
  } catch (error) {
    ElMessage.error('加载项目列表失败')
  }
}

const loadSpiders = async () => {
  try {
    loading.value = true
    spiders.value = await getSpiders(searchForm)
  } catch (error) {
    ElMessage.error('加载爬虫列表失败')
  } finally {
    loading.value = false
  }
}

const resetSearch = () => {
  searchForm.project_id = null
  searchForm.status = null
  loadSpiders()
}

const getProjectName = (projectId) => {
  const project = projects.value.find(p => p.id === projectId)
  return project ? project.name : '-'
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

const formatRelativeTime = (dateStr) => {
  if (!dateStr) return '未运行'
  
  const now = new Date()
  const date = new Date(dateStr)
  const diff = Math.floor((now - date) / 1000) // 秒
  
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
  if (diff < 604800) return `${Math.floor(diff / 86400)}天前`
  
  return formatDate(dateStr)
}

const formatTime = (seconds) => {
  if (seconds >= 3600) {
    return `${Math.floor(seconds / 3600)}小时`
  } else if (seconds >= 60) {
    return `${Math.floor(seconds / 60)}分钟`
  }
  return `${seconds}秒`
}

// 获取爬虫类型颜色
const getSpiderTypeColor = (type) => {
  const colorMap = {
    crawlo: '#722ED1',    // 紫色 - Crawlo
    scrapy: '#FA8C16',    // 橙色
    selenium: '#1890FF',  // 蓝色
    playwright: '#52C41A', // 绿色
    requests: '#8C8C8C',  // 灰色
    custom: '#13C2C2'     // 青色
  }
  return colorMap[type] || '#8C8C8C'
}

// 卡片操作
const handleCardAction = (command, spider) => {
  if (command === 'edit') {
    showEditDialog(spider)
  } else if (command === 'delete') {
    handleDelete(spider)
  }
}

// 代码来源切换
const onCodeSourceChange = (value) => {
  // 根据代码来源设置默认入口文件
  if (value === 'git' || value === 'upload') {
    spiderForm.entry_file = 'main.py'
  } else {
    spiderForm.entry_file = 'main.py'
  }
}

// 文件上传处理
const handleFileChange = (file) => {
  uploadFile.value = file.raw
}

const beforeUpload = (file) => {
  const isZip = file.type === 'application/zip' || file.name.endsWith('.zip')
  const isLt100M = file.size / 1024 / 1024 < 100

  if (!isZip) {
    ElMessage.error('只能上传 ZIP 格式的文件!')
  }
  if (!isLt100M) {
    ElMessage.error('上传文件大小不能超过 100MB!')
  }
  return isZip && isLt100M
}

// 步骤控制
const nextStep = async () => {
  try {
    // 验证当前步骤
    if (currentStep.value === 0) {
      await formRef.value.validateField(['name', 'project_id', 'spider_type'])
    } else if (currentStep.value === 1) {
      if (spiderForm.code_source === 'git') {
        await formRef.value.validateField(['git_url'])
      }
    }
    currentStep.value++
  } catch (error) {
    // 验证失败
  }
}

const showCreateDialog = () => {
  editingSpider.value = null
  currentStep.value = 0
  Object.assign(spiderForm, {
    name: '',
    project_id: route.query.project_id ? parseInt(route.query.project_id) : null,
    spider_type: 'crawlo', // 默认 Crawlo
    description: '',
    code_source: 'git',
    git_url: '',
    git_auth_type: 'password',
    git_username: '',
    git_password: '',
    git_ssh_key: '',
    git_branch: 'main',
    entry_file: 'main.py',
    schedule_enabled: false,
    cron_expr: '',
    timeout_seconds: 3600,
    retry_count: 3,
    status: 'draft'
  })
  uploadFile.value = null
  showDialog.value = true
}

const showEditDialog = (row) => {
  editingSpider.value = row
  currentStep.value = 0
  Object.assign(spiderForm, {
    name: row.name,
    project_id: row.project_id,
    spider_type: row.spider_type,
    entry_file: row.entry_file,
    description: row.description,
    status: row.status
  })
  showDialog.value = true
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    submitting.value = true

    if (editingSpider.value) {
      await updateSpider(editingSpider.value.id, spiderForm)
      ElMessage.success('更新成功')
    } else {
      // 创建爬虫
      const spiderData = {
        name: spiderForm.name,
        project_id: spiderForm.project_id,
        spider_type: spiderForm.spider_type,
        description: spiderForm.description,
        entry_file: spiderForm.entry_file,
        // Git 配置
        git_url: spiderForm.code_source === 'git' ? spiderForm.git_url : null,
        git_auth_type: spiderForm.git_auth_type,
        git_username: spiderForm.git_username || null,
        git_password: spiderForm.git_password || null,
        git_ssh_key: spiderForm.git_ssh_key || null,
        git_branch: spiderForm.git_branch,
      }
      
      const newSpider = await createSpider(spiderData)
      
      // 如果是 Git 仓库，触发克隆
      if (spiderForm.code_source === 'git' && spiderForm.git_url) {
        ElMessage.success('爬虫创建成功，开始克隆仓库...')
        // TODO: 调用 git clone API
      } else if (spiderForm.code_source === 'upload' && uploadFile.value) {
        ElMessage.success('爬虫创建成功，开始上传代码...')
        // TODO: 调用文件上传 API
      } else {
        ElMessage.success('爬虫创建成功')
      }
    }

    showDialog.value = false
    loadSpiders()
  } catch (error) {
    if (error.response?.data?.detail) {
      ElMessage.error(error.response.data.detail)
    }
  } finally {
    submitting.value = false
  }
}

const viewSpider = (row) => {
  router.push(`/spiders/${row.id}`)
}

const handleRun = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要运行爬虫 "${row.name}" 吗？`, '提示', {
      type: 'info'
    })

    await runSpider(row.id)
    ElMessage.success('爬虫运行指令已发送')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '运行失败')
    }
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
}

.spider-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
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
  overflow: hidden;
}

.spider-name {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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
  border-top: 1px solid #EBEEF5;
}

.card-actions .el-button {
  flex: 1;
}
</style>
