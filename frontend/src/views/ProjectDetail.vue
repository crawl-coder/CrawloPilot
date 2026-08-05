<template>
  <div class="project-detail">
    <el-page-header @back="$router.back()" :title="'返回'">
      <template #content>
        <span class="page-title">{{ project?.name || '项目详情' }}</span>
      </template>
    </el-page-header>

    <el-row :gutter="20" style="margin-top: 20px">
      <!-- 项目信息 -->
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>项目信息</span>
          </template>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="项目名称">{{ project?.name }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="project?.status === 'active' ? 'success' : 'info'">
                {{ project?.status }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="描述" :span="2">{{ project?.description || '无' }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatDate(project?.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="更新时间">{{ formatDate(project?.updated_at) }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <!-- 爬虫列表 -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>爬虫列表</span>
              <el-button type="primary" size="small" @click="goToCreateSpider">
                创建爬虫
              </el-button>
            </div>
          </template>

          <el-table :data="spiders" v-loading="loading" border>
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="name" label="爬虫名称" width="180" />
            <el-table-column label="类型" width="120">
              <template #default="{ row }">
                <el-tag size="small">{{ row.spider_type }}</el-tag>
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
                  <div>成功: {{ row.success_count }} / 失败: {{ row.error_count }}</div>
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
            <el-table-column label="操作" width="140" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="primary" @click="viewSpider(row)">详情</el-button>
                <el-button size="small" type="success" @click="handleRun(row)" :disabled="row.status === 'disabled'">运行</el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-empty v-if="!loading && spiders.length === 0" description="暂无爬虫，请点击创建">
            <el-button type="primary" @click="goToCreateSpider">创建爬虫</el-button>
          </el-empty>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getProject } from '@/api/project'
import { getSpiders, runSpider } from '@/api/spider'

const route = useRoute()
const router = useRouter()
const projectId = route.params.id

const project = ref(null)
const spiders = ref([])
const loading = ref(false)

onMounted(() => {
  loadProject()
  loadSpiders()
})

const loadProject = async () => {
  try {
    project.value = await getProject(projectId)
  } catch (error) {
    ElMessage.error('加载项目信息失败')
  }
}

const loadSpiders = async () => {
  try {
    loading.value = true
    spiders.value = await getSpiders({ project_id: projectId })
  } catch (error) {
    ElMessage.error('加载爬虫列表失败')
  } finally {
    loading.value = false
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
    active: '启用',
    disabled: '已禁用',
    error: '错误'
  }
  return textMap[status] || status
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const viewSpider = (spider) => {
  router.push(`/spiders/${spider.id}`)
}

const goToCreateSpider = () => {
  router.push(`/spiders?project_id=${projectId}&action=create`)
}

const handleRun = async (spider) => {
  try {
    const res = await runSpider(spider.id)
    ElMessage.success('爬虫运行指令已发送')
    if (res?.task_id) {
      router.push(`/tasks/${res.task_id}`)
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '运行失败')
  }
}
</script>

<style scoped>
.project-detail {
  padding: 20px;
}

.page-title {
  font-size: 18px;
  font-weight: bold;
}
</style>
