<template>
  <div>
    <div style="display: flex; justify-content: space-between; margin-bottom: 20px">
      <h2>项目管理</h2>
      <el-button type="primary" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon>
        创建项目
      </el-button>
    </div>
    
    <el-table :data="projects" v-loading="loading" style="width: 100%">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="项目名称" />
      <el-table-column prop="description" label="描述" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'">
            {{ row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button size="small" @click="handleEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    
    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="showCreateDialog" :title="editingProject ? '编辑项目' : '创建项目'">
      <el-form :model="projectForm" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="项目名称" prop="name">
          <el-input v-model="projectForm.name" />
        </el-form-item>
        
        <el-form-item label="描述" prop="description">
          <el-input v-model="projectForm.description" type="textarea" :rows="3" />
        </el-form-item>
        
        <el-form-item label="Git 地址" prop="git_url">
          <el-input v-model="projectForm.git_url" placeholder="https://github.com/..." />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getProjects, createProject, updateProject, deleteProject } from '@/api/project'

const projects = ref([])
const loading = ref(false)
const showCreateDialog = ref(false)
const editingProject = ref(null)
const formRef = ref(null)

const projectForm = reactive({
  name: '',
  description: '',
  git_url: '',
  team_id: 1
})

const rules = {
  name: [{ required: true, message: '请输入项目名称', trigger: 'blur' }]
}

onMounted(() => {
  loadProjects()
})

const loadProjects = async () => {
  try {
    loading.value = true
    projects.value = await getProjects()
  } catch (error) {
    ElMessage.error('加载项目列表失败')
  } finally {
    loading.value = false
  }
}

const handleEdit = (row) => {
  editingProject.value = row
  Object.assign(projectForm, row)
  showCreateDialog.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该项目吗？', '提示', {
      type: 'warning'
    })
    await deleteProject(row.id)
    ElMessage.success('删除成功')
    loadProjects()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    if (editingProject.value) {
      await updateProject(editingProject.value.id, projectForm)
      ElMessage.success('更新成功')
    } else {
      await createProject(projectForm)
      ElMessage.success('创建成功')
    }
    showCreateDialog.value = false
    resetForm()
    loadProjects()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const resetForm = () => {
  editingProject.value = null
  Object.assign(projectForm, {
    name: '',
    description: '',
    git_url: '',
    team_id: 1
  })
}
</script>
