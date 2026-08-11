import { ref, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getGitCredentials,
  createGitCredential,
  updateGitCredential,
  deleteGitCredential
} from '@/api/git-credential'

const emptyForm = () => ({
  name: '',
  description: '',
  auth_type: 'password',
  username: '',
  password: '',
  ssh_key: '',
  default_branch: ''
})

export function useSharedGitCredential() {
  const list = ref([])
  const loading = ref(false)
  const dialogVisible = ref(false)
  const saving = ref(false)
  const editing = ref(null)
  const form = reactive(emptyForm())

  const load = async () => {
    loading.value = true
    try {
      list.value = await getGitCredentials({ include_inactive: true })
    } catch (error) {
      const detail = error.response?.data?.detail
      ElMessage.error(detail || '加载共享凭据失败')
      list.value = []
    } finally {
      loading.value = false
    }
  }

  const resetForm = (values = emptyForm()) => {
    Object.assign(form, values)
  }

  const openCreate = () => {
    editing.value = null
    resetForm()
    dialogVisible.value = true
  }

  const openEdit = (row) => {
    editing.value = row
    resetForm({
      name: row.name,
      description: row.description || '',
      auth_type: row.auth_type || 'password',
      username: row.username || '',
      password: '',
      ssh_key: '',
      default_branch: row.default_branch || ''
    })
    dialogVisible.value = true
  }

  const save = async () => {
    saving.value = true
    try {
      const payload = {
        name: form.name.trim(),
        description: form.description?.trim() || null,
        auth_type: form.auth_type,
        username: form.username?.trim() || null,
        password: form.password?.trim() || null,
        ssh_key: form.ssh_key?.trim() || null,
        default_branch: form.default_branch?.trim() || null
      }
      if (editing.value) {
        await updateGitCredential(editing.value.id, payload)
        ElMessage.success('凭据已更新')
      } else {
        await createGitCredential(payload)
        ElMessage.success('凭据已创建')
      }
      dialogVisible.value = false
      await load()
      return true
    } catch (error) {
      const detail = error.response?.data?.detail
      ElMessage.error(detail || '保存失败')
      return false
    } finally {
      saving.value = false
    }
  }

  const toggle = async (row) => {
    const action = row.is_active ? '停用' : '启用'
    try {
      await ElMessageBox.confirm(`确定${action}共享凭据「${row.name}」？`, '确认', { type: 'warning' })
    } catch {
      return false
    }
    try {
      await updateGitCredential(row.id, { is_active: !row.is_active })
      ElMessage.success(`已${action}`)
      await load()
      return true
    } catch (error) {
      const detail = error.response?.data?.detail
      ElMessage.error(detail || `${action}失败`)
      return false
    }
  }

  const remove = async (row) => {
    try {
      await ElMessageBox.confirm(
        `确定删除共享凭据「${row.name}」？被引用的凭据将无法删除。`,
        '删除确认',
        { type: 'warning' }
      )
    } catch {
      return false
    }
    try {
      await deleteGitCredential(row.id)
      ElMessage.success('删除成功')
      await load()
      return true
    } catch (error) {
      const detail = error.response?.data?.detail
      ElMessage.error(detail || '删除失败')
      return false
    }
  }

  return {
    list,
    loading,
    dialogVisible,
    saving,
    editing,
    form,
    load,
    openCreate,
    openEdit,
    save,
    toggle,
    remove
  }
}
