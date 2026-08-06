<template>
  <el-dialog
    :model-value="modelValue"
    :title="isEdit ? '编辑爬虫' : '创建爬虫'"
    width="700px"
    :close-on-click-modal="false"
    @update:model-value="$emit('update:modelValue', $event)"
    @open="handleDialogOpen"
  >
    <!-- 步骤条 -->
    <el-steps :active="currentStep" finish-status="success" v-if="!isEdit" style="margin-bottom: 30px">
      <el-step title="基本信息" />
      <el-step title="代码来源" />
      <el-step title="运行配置" />
    </el-steps>

    <el-form :model="spiderForm" :rules="rules" ref="formRef" label-width="120px">
      <!-- 步骤1: 基本信息 -->
      <div v-show="currentStep === 0">
        <div v-if="isEdit" class="form-section">
          <span class="section-bar"></span>
          <span class="section-title">基本信息</span>
        </div>

        <el-form-item label="爬虫名称" prop="name">
          <el-input ref="nameInputRef" v-model="spiderForm.name" placeholder="请输入爬虫名称" />
        </el-form-item>

        <el-form-item label="所属项目" prop="project_id">
          <el-select v-model="spiderForm.project_id" placeholder="请选择项目" style="width: 100%" :disabled="isEdit">
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
            <el-option
              v-for="t in spiderTypeOptions"
              :key="t.value"
              :label="t.label"
              :value="t.value"
            >
              <div class="type-option">
                <span class="type-name">{{ t.label }}</span>
                <span class="type-desc">{{ t.desc }}</span>
              </div>
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
          v-if="!isEdit && spiderForm.spider_type === 'crawlo'"
          type="info"
          :closable="false"
          show-icon
          style="margin-top: 4px"
        >
          <template #default>
            <div style="font-size: 13px">
              Crawlo 框架优势：分布式架构、智能反反爬、自动去重、增量采集、性能监控
            </div>
          </template>
        </el-alert>

        <!-- 编辑模式：状态归入基本信息区 -->
        <el-form-item v-if="isEdit" label="状态" style="margin-top: 18px">
          <el-select v-model="spiderForm.status" style="width: 100%">
            <el-option label="草稿" value="draft" />
            <el-option label="启用" value="active" />
            <el-option label="已禁用" value="disabled" />
          </el-select>
        </el-form-item>
      </div>

      <!-- 步骤2: 代码来源 -->
      <div v-show="currentStep === 1 && !isEdit">
        <el-form-item label="代码来源">
          <div class="source-cards">
            <div
              v-for="opt in codeSourceOptions"
              :key="opt.value"
              class="source-card"
              :class="{ active: spiderForm.code_source === opt.value }"
              @click="spiderForm.code_source = opt.value"
            >
              <el-icon :size="15" class="source-icon"><component :is="opt.icon" /></el-icon>
              <div class="source-text">
                <div class="source-title">{{ opt.title }}</div>
                <div class="source-desc">{{ opt.desc }}</div>
              </div>
            </div>
          </div>
        </el-form-item>

        <!-- Git 仓库 -->
        <div v-show="spiderForm.code_source === 'git'">
          <el-form-item label="Git地址" prop="git_url">
            <el-input v-model="spiderForm.git_url" placeholder="https://github.com/user/repo.git（创建时自动克隆）" />
          </el-form-item>

          <el-form-item v-if="hasCredOptions" label="凭据来源">
            <el-radio-group v-model="spiderForm.cred_source">
              <el-radio value="manual">手动填写</el-radio>
              <el-radio v-if="myCred.configured" value="mine">我的凭据</el-radio>
              <el-radio v-if="sharedCreds.length > 0" value="shared">团队凭据</el-radio>
            </el-radio-group>
          </el-form-item>

          <template v-if="spiderForm.cred_source === 'mine'">
            <el-form-item label="我的凭据">
              <el-tag type="success" effect="plain">
                {{ myCred.auth_type === 'ssh' ? 'SSH密钥' : '密码/Token' }}{{ myCred.username ? ` · ${myCred.username}` : '' }}
              </el-tag>
              <div class="form-tip">
                使用您在个人中心配置的 Git 凭据；<el-link type="primary" @click="goProfile">前往配置</el-link>
              </div>
            </el-form-item>
          </template>

          <template v-else-if="spiderForm.cred_source === 'shared'">
            <el-form-item label="团队凭据" prop="git_credential_id">
              <el-select v-model="spiderForm.git_credential_id" placeholder="选择共享凭据" style="width: 100%">
                <el-option
                  v-for="cred in sharedCreds"
                  :key="cred.id"
                  :label="cred.name"
                  :value="cred.id"
                >
                  <div class="type-option">
                    <span class="type-name">{{ cred.name }}</span>
                    <span class="type-desc">{{ cred.auth_type === 'ssh' ? 'SSH密钥' : '密码/Token' }}{{ cred.username ? ` · ${cred.username}` : '' }}</span>
                  </div>
                </el-option>
              </el-select>
            </el-form-item>
          </template>

          <template v-else>
            <el-form-item label="认证方式">
              <el-radio-group v-model="spiderForm.git_auth_type">
                <el-radio value="password">密码/Token</el-radio>
                <el-radio value="ssh">SSH密钥</el-radio>
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
          </template>

          <el-form-item label="分支">
            <el-input v-model="spiderForm.git_branch" placeholder="默认 main" />
          </el-form-item>
        </div>

        <!-- 本地上传 -->
        <div v-show="spiderForm.code_source === 'upload'">
          <el-form-item label="上传代码">
            <el-upload
              drag
              action="#"
              :auto-upload="false"
              :limit="1"
              accept=".zip,.tar,.tar.gz,.tgz,.tar.bz2"
              :on-change="handleFileChange"
              :before-upload="beforeUpload"
            >
              <el-icon class="el-icon--upload"><upload-filled /></el-icon>
              <div class="el-upload__text">
                拖拽文件到此处或 <em>点击上传</em>
              </div>
              <template #tip>
                <div class="el-upload__tip">
                  支持 .zip / .tar / .tar.gz / .tar.bz2，大小不超过 100MB
                </div>
              </template>
            </el-upload>
          </el-form-item>
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

      <!-- 步骤3: 运行配置（编辑模式下与基本信息同屏显示） -->
      <div v-show="currentStep === 2 || isEdit">
        <div v-if="isEdit" class="form-section">
          <span class="section-bar"></span>
          <span class="section-title">运行配置</span>
        </div>

        <el-form-item label="入口文件" prop="entry_file">
          <el-input
            v-model="spiderForm.entry_file"
            placeholder="例如: run.py，留空则使用 crawlo run"
          />
        </el-form-item>

        <!-- 爬虫名称(执行名)仅创建模式可设；编辑模式隐藏避免与基本信息重名，且保留原值 -->
        <el-form-item v-if="!isEdit" label="爬虫名称" prop="spider_name">
          <el-input
            v-model="spiderForm.spider_name"
            :placeholder="`默认与基本信息中的名称一致: ${spiderForm.name || '(未填写)'}`"
          />
          <div class="form-tip">
            用于 crawlo run 命令；留空则与基本信息中的爬虫名称一致
          </div>
        </el-form-item>

        <!-- 创建模式：完整启动方式说明；编辑模式：收敛为一行小提示 -->
        <el-alert
          v-if="!isEdit"
          title="启动方式"
          type="info"
          :closable="false"
          show-icon
          style="margin-bottom: 18px"
        >
          <template #default>
            <div style="font-size: 13px; line-height: 1.8">
              填写入口文件 → 执行 <code>python {{ spiderForm.entry_file || 'run.py' }}</code><br/>
              未填写入口文件 → 执行 <code>crawlo run {{ spiderForm.spider_name || spiderForm.name || 'spider_name' }}</code>
            </div>
          </template>
        </el-alert>
        <div v-else class="form-tip" style="margin: -10px 0 14px 120px">
          当前将执行：<code>{{ spiderForm.entry_file ? `python ${spiderForm.entry_file}` : `crawlo run ${spiderForm.spider_name || spiderForm.name || 'spider_name'}` }}</code>
        </div>

        <el-form-item label="定时调度">
          <el-switch v-model="spiderForm.schedule_enabled" />
          <span style="margin-left: 10px; color: var(--cp-text-secondary); font-size: 13px">
            {{ spiderForm.schedule_enabled ? '已开启' : '已关闭' }}
          </span>
        </el-form-item>

        <template v-if="spiderForm.schedule_enabled">
          <el-form-item label="Cron表达式">
            <el-input v-model="spiderForm.cron_expr" placeholder="例如: 0 */2 * * * (每2小时)" />
          </el-form-item>
        </template>

        <el-form-item label="超时时间">
          <el-input-number v-model="spiderForm.timeout_seconds" :min="60" :max="86400" :step="300" />
          <span style="margin-left: 10px; color: var(--cp-text-secondary); font-size: 13px">
            秒（{{ formatDuration(spiderForm.timeout_seconds) }}）
          </span>
        </el-form-item>

        <el-form-item label="重试次数">
          <el-input-number v-model="spiderForm.retry_count" :min="0" :max="10" />
          <span style="margin-left: 10px; color: var(--cp-text-secondary); font-size: 13px">
            失败后自动重试
          </span>
        </el-form-item>
      </div>

    </el-form>

    <template #footer>
      <div style="display: flex; justify-content: space-between">
        <el-button @click="$emit('update:modelValue', false)">取消</el-button>
        <div>
          <el-button v-if="currentStep > 0 && !isEdit" @click="currentStep--">上一步</el-button>
          <el-button v-if="currentStep < 2 && !isEdit" type="primary" @click="nextStep">下一步</el-button>
          <el-button v-else type="primary" @click="handleSubmit" :loading="submitting">确定</el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { UploadFilled, Link, FolderAdd } from '@element-plus/icons-vue'
import { createSpider, updateSpider, cloneSpiderGit, uploadSpiderCode } from '@/api/spider'
import { getProjects } from '@/api/project'
import { getSchedules, createSchedule } from '@/api/schedule'
import { getMyGitCredentials } from '@/api/auth'
import { getGitCredentials } from '@/api/git-credential'
import { formatDuration } from '@/utils/common'

const router = useRouter()

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  // null=创建模式；传入爬虫对象=编辑模式
  spider: { type: Object, default: null },
  // 创建时预选的项目（如从项目详情页跳转）
  defaultProjectId: { type: Number, default: null }
})

const emit = defineEmits(['update:modelValue', 'saved'])

const isEdit = computed(() => !!props.spider)

const projects = ref([])
const submitting = ref(false)
const currentStep = ref(0)
const uploadFile = ref(null)
const formRef = ref(null)
const nameInputRef = ref(null)
const existingScheduleId = ref(null)
const existingScheduleCron = ref('')

// Git 凭据来源（创建模式）
const myCred = ref({ configured: false })
const sharedCreds = ref([])
const hasCredOptions = computed(() => myCred.value.configured || sharedCreds.value.length > 0)

const spiderForm = reactive({
  name: '',
  project_id: null,
  spider_type: 'crawlo',
  description: '',
  code_source: 'git',
  git_url: '',
  cred_source: 'manual',
  git_credential_id: null,
  git_auth_type: 'password',
  git_username: '',
  git_password: '',
  git_ssh_key: '',
  git_branch: 'main',
  entry_file: 'run.py',
  spider_name: '',
  schedule_enabled: false,
  cron_expr: '',
  timeout_seconds: 3600,
  retry_count: 3,
  status: 'draft'
})

const spiderTypeOptions = [
  { value: 'crawlo', label: 'Crawlo（推荐）', desc: '分布式爬虫框架' },
  { value: 'scrapy', label: 'Scrapy', desc: 'Python 爬虫框架' },
  { value: 'selenium', label: 'Selenium', desc: '浏览器自动化' },
  { value: 'playwright', label: 'Playwright', desc: '现代浏览器自动化' },
  { value: 'requests', label: 'Requests', desc: 'HTTP 请求库' },
  { value: 'custom', label: '自定义', desc: '其他框架或脚本' }
]

const codeSourceOptions = [
  { value: 'git', title: 'Git 仓库', desc: '克隆远程仓库代码', icon: Link },
  { value: 'upload', title: '本地上传', desc: '上传 ZIP/TAR 代码包', icon: UploadFilled },
  { value: 'empty', title: '空爬虫', desc: '生成基础模板文件', icon: FolderAdd }
]

// 运行名称自动跟随爬虫名称（仅创建模式；用户手动改过则不再跟随）
let spiderNameTouched = false
watch(() => spiderForm.name, (newName, oldName) => {
  if (isEdit.value) return
  if (!spiderNameTouched || spiderForm.spider_name === oldName) {
    spiderForm.spider_name = newName
  }
})
watch(() => spiderForm.spider_name, (val) => {
  if (val && val !== spiderForm.name) spiderNameTouched = true
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
      // 仅在创建模式的 Git 来源下校验（编辑模式步骤2隐藏，不校验）
      if (!isEdit.value && spiderForm.code_source === 'git' && !value) {
        callback(new Error('请输入Git仓库地址'))
      } else {
        callback()
      }
    }
  }],
  git_credential_id: [{
    trigger: 'change',
    validator: (rule, value, callback) => {
      if (!isEdit.value && spiderForm.code_source === 'git' && spiderForm.cred_source === 'shared' && !value) {
        callback(new Error('请选择团队凭据'))
      } else {
        callback()
      }
    }
  }]
}

// 对话框打开时：初始化表单 + 清校验 + 聚焦
const handleDialogOpen = () => {
  initForm()
  loadProjects()
  loadCredOptions()
  formRef.value?.clearValidate()
  nextTick(() => nameInputRef.value?.focus())
}

// 加载凭据选项（个人凭据 + 团队共享凭据），仅创建模式需要
const loadCredOptions = async () => {
  if (isEdit.value) return
  try {
    myCred.value = await getMyGitCredentials()
  } catch (error) {
    myCred.value = { configured: false }
  }
  try {
    sharedCreds.value = await getGitCredentials()
  } catch (error) {
    sharedCreds.value = []
  }
  // 默认优先使用我的凭据
  if (myCred.value.configured) {
    spiderForm.cred_source = 'mine'
  } else if (sharedCreds.value.length > 0) {
    spiderForm.cred_source = 'shared'
  }
}

const goProfile = () => {
  emit('update:modelValue', false)
  router.push('/profile')
}

const initForm = () => {
  currentStep.value = 0
  uploadFile.value = null
  existingScheduleId.value = null
  existingScheduleCron.value = ''
  spiderNameTouched = false
  if (props.spider) {
    // 编辑模式：回填（运行配置 + git 字段保持状态真实；调度从 /schedules 读取）
    const row = props.spider
    Object.assign(spiderForm, {
      name: row.name,
      project_id: row.project_id,
      spider_type: row.spider_type,
      description: row.description,
      entry_file: row.entry_file,
      status: row.status,
      spider_name: row.spider_name || '',
      code_source: row.git_url ? 'git' : 'empty',
      git_url: row.git_url || '',
      cred_source: 'manual',
      git_credential_id: row.git_credential_id || null,
      git_auth_type: row.git_auth_type || 'password',
      git_username: '',
      git_password: '',
      git_ssh_key: '',
      git_branch: row.git_branch || 'main',
      timeout_seconds: row.config?.timeout_seconds ?? 3600,
      retry_count: row.config?.retry_count ?? 3,
      schedule_enabled: false,
      cron_expr: '0 * * * *'
    })
    loadExistingSchedule(row.id)
  } else {
    // 创建模式：重置
    Object.assign(spiderForm, {
      name: '',
      project_id: props.defaultProjectId,
      spider_type: 'crawlo',
      description: '',
      code_source: 'git',
      git_url: '',
      cred_source: 'manual',
      git_credential_id: null,
      git_auth_type: 'password',
      git_username: '',
      git_password: '',
      git_ssh_key: '',
      git_branch: 'main',
      entry_file: 'run.py',
      spider_name: '',
      schedule_enabled: false,
      cron_expr: '',
      timeout_seconds: 3600,
      retry_count: 3,
      status: 'draft'
    })
  }
}

// 编辑模式：从 /schedules 读取该爬虫的默认调度并回显
const loadExistingSchedule = async (spiderId) => {
  try {
    const list = await getSchedules({ spider_id: spiderId })
    if (list && list.length > 0) {
      const sched = list[0]
      existingScheduleId.value = sched.id
      existingScheduleCron.value = sched.cron_expr || ''
      spiderForm.schedule_enabled = !!sched.enabled
      spiderForm.cron_expr = sched.cron_expr || '0 * * * *'
    }
  } catch (error) {
    // 读取失败不阻塞编辑，保持关闭状态
  }
}

// 提交后同步调度（写 /schedules，不再写 spider.schedule_config JSON）
const syncSchedule = async (spiderId) => {
  if (spiderForm.schedule_enabled) {
    await createSchedule({
      spider_id: spiderId,
      schedule_type: 'cron',
      cron_expr: spiderForm.cron_expr,
      timezone: 'Asia/Shanghai',
      max_concurrency: 1,
      timeout_seconds: spiderForm.timeout_seconds,
      enabled: true
    })
  } else if (existingScheduleId.value) {
    // 有关联调度但用户关闭：保留行、停用（不删除配置）
    await createSchedule({
      spider_id: spiderId,
      schedule_type: 'cron',
      cron_expr: existingScheduleCron.value || '0 * * * *',
      timezone: 'Asia/Shanghai',
      enabled: false
    })
  }
}

const loadProjects = async () => {
  try {
    const response = await getProjects({ skip: 0, limit: 1000 })
    projects.value = response.items || []
  } catch (error) {
    console.error('加载项目列表失败:', error)
  }
}

// 文件上传处理
const handleFileChange = (file) => {
  uploadFile.value = file.raw
}

const beforeUpload = (file) => {
  const name = file.name.toLowerCase()
  const isAllowed = name.endsWith('.zip') || name.endsWith('.tar') ||
                    name.endsWith('.tar.gz') || name.endsWith('.tgz') || name.endsWith('.tar.bz2')
  const isLt100M = file.size / 1024 / 1024 < 100

  if (!isAllowed) {
    ElMessage.error('仅支持 .zip / .tar / .tar.gz / .tar.bz2 格式!')
  }
  if (!isLt100M) {
    ElMessage.error('上传文件大小不能超过 100MB!')
  }
  return isAllowed && isLt100M
}

// 步骤控制
const nextStep = async () => {
  try {
    if (currentStep.value === 0) {
      await formRef.value.validateField(['name', 'project_id', 'spider_type'])
    } else if (currentStep.value === 1) {
      if (spiderForm.code_source === 'git') {
        await formRef.value.validateField(['git_url', 'git_credential_id'])
      } else if (spiderForm.code_source === 'upload' && !uploadFile.value) {
        ElMessage.warning('请先选择要上传的代码包')
        return
      }
    }
    currentStep.value++
  } catch (error) {
    // 验证失败
  }
}

// 组装运行配置（调度已迁移到独立 Schedule 表，不再写 spider.schedule_config）
const buildConfigPayload = () => ({
  config: {
    timeout_seconds: spiderForm.timeout_seconds,
    retry_count: spiderForm.retry_count
  }
})

const handleSubmit = async () => {
  try {
    // 编辑模式只校验可见字段；创建模式全量校验
    if (isEdit.value) {
      await formRef.value.validateField(['name', 'project_id', 'spider_type'])
    } else {
      await formRef.value.validate()
    }
    if (!isEdit.value && spiderForm.code_source === 'upload' && !uploadFile.value) {
      ElMessage.warning('请先选择要上传的代码包')
      currentStep.value = 1
      return
    }
    submitting.value = true

    if (isEdit.value) {
      const updateData = {
        name: spiderForm.name,
        description: spiderForm.description,
        spider_type: spiderForm.spider_type,
        status: spiderForm.status,
        entry_file: spiderForm.entry_file || null,
        // 编辑模式不提交 spider_name，保留创建时的执行名（避免跟随显示名被静默修改）
        ...buildConfigPayload()
      }
      await updateSpider(props.spider.id, updateData)
      try {
        await syncSchedule(props.spider.id)
      } catch (error) {
        ElMessage.warning('爬虫已更新，但定时调度配置失败: ' + (error.response?.data?.detail || '未知错误'))
      }
      ElMessage.success('更新成功')
    } else {
      const isGit = spiderForm.code_source === 'git'
      const useShared = isGit && spiderForm.cred_source === 'shared' && spiderForm.git_credential_id
      const useMine = isGit && !useShared && spiderForm.cred_source === 'mine'
      const spiderData = {
        name: spiderForm.name,
        project_id: spiderForm.project_id,
        spider_type: spiderForm.spider_type,
        description: spiderForm.description,
        entry_file: spiderForm.entry_file || null,
        spider_name: spiderForm.spider_name || spiderForm.name,
        git_url: isGit ? spiderForm.git_url : null,
        git_auth_type: spiderForm.git_auth_type,
        git_username: useMine || useShared ? null : (spiderForm.git_username || null),
        git_password: useMine || useShared ? null : (spiderForm.git_password || null),
        git_ssh_key: useMine || useShared ? null : (spiderForm.git_ssh_key || null),
        git_branch: spiderForm.git_branch,
        use_my_git_credential: useMine,
        git_credential_id: useShared ? spiderForm.git_credential_id : null,
        ...buildConfigPayload()
      }

      const newSpider = await createSpider(spiderData)

      if (spiderForm.code_source === 'git' && spiderForm.git_url) {
        ElMessage.success('爬虫创建成功，开始克隆仓库...')
        try {
          await cloneSpiderGit(newSpider.id)
          ElMessage.success('Git 仓库克隆成功')
        } catch (error) {
          ElMessage.error(error.response?.data?.detail || 'Git 仓库克隆失败')
        }
      } else if (spiderForm.code_source === 'upload' && uploadFile.value) {
        ElMessage.success('爬虫创建成功，开始上传代码...')
        try {
          await uploadSpiderCode(newSpider.id, uploadFile.value)
          ElMessage.success('代码上传成功')
        } catch (error) {
          ElMessage.error(error.response?.data?.detail || '代码上传失败')
        }
      } else {
        ElMessage.success('爬虫创建成功')
      }
      if (spiderForm.schedule_enabled) {
        await syncSchedule(newSpider.id)
        ElMessage.success('定时调度已配置')
      }
    }

    emit('update:modelValue', false)
    emit('saved')
  } catch (error) {
    if (error.response?.data?.detail) {
      ElMessage.error(error.response.data.detail)
    }
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
/* ===== 代码来源卡片选择（紧凑横排，不喧宾夺主） ===== */
.source-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  width: 100%;
}

.source-card {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--cp-border-light);
  border-radius: var(--cp-radius-sm);
  padding: 7px 10px;
  cursor: pointer;
  transition: border-color var(--cp-motion-fast) ease,
              box-shadow var(--cp-motion-fast) ease,
              background var(--cp-motion-fast) ease;
  background: var(--cp-card-bg);
}

.source-card:hover {
  border-color: var(--cp-primary-light);
}

.source-card.active {
  border-color: var(--cp-primary);
  background: rgba(59, 124, 255, 0.05);
  box-shadow: 0 0 0 1px rgba(59, 124, 255, 0.25);
}

.source-icon {
  color: var(--cp-text-secondary);
  flex-shrink: 0;
  transition: color var(--cp-motion-fast) ease;
}

.source-card.active .source-icon {
  color: var(--cp-primary);
}

.source-text {
  min-width: 0;
}

.source-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--cp-text-primary);
  line-height: 1.3;
}

.source-desc {
  font-size: 11px;
  color: var(--cp-text-secondary);
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ===== 爬虫类型选项 ===== */
.type-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.type-name {
  font-weight: 500;
}

.type-desc {
  color: var(--cp-text-secondary);
  font-size: 12px;
}

/* ===== 表单提示 ===== */
.form-tip {
  margin-top: 5px;
  color: var(--cp-text-secondary);
  font-size: 12px;
}

.form-tip code {
  background: var(--cp-page-bg);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}

/* ===== 编辑模式分区标题 ===== */
.form-section {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 2px 0 18px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--cp-border-light);
}

.section-bar {
  width: 3px;
  height: 14px;
  background: var(--cp-primary);
  border-radius: 2px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--cp-text-primary);
  letter-spacing: 0.5px;
}
</style>
