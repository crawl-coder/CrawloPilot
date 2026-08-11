import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getMyGitCredentials,
  saveMyGitCredentials,
  deleteMyGitCredentials
} from '@/api/auth'

export function useMyGitCredential() {
  const myCred = ref({ configured: false })
  const loading = ref(false)
  const saving = ref(false)

  const load = async () => {
    loading.value = true
    try {
      myCred.value = await getMyGitCredentials()
    } catch (error) {
      const detail = error.response?.data?.detail
      ElMessage.error(detail || '加载个人 Git 凭据失败')
      myCred.value = { configured: false }
    } finally {
      loading.value = false
    }
  }

  const save = async (form) => {
    saving.value = true
    try {
      const res = await saveMyGitCredentials({
        auth_type: form.auth_type,
        username: form.username?.trim() || null,
        password: form.password?.trim() || null,
        ssh_key: form.ssh_key?.trim() || null,
        default_branch: form.default_branch?.trim() || null
      })
      myCred.value = res
      ElMessage.success('个人 Git 凭据已保存')
      return true
    } catch (error) {
      const detail = error.response?.data?.detail
      ElMessage.error(detail || '保存失败')
      return false
    } finally {
      saving.value = false
    }
  }

  const clear = async () => {
    try {
      await deleteMyGitCredentials()
      myCred.value = { configured: false }
      ElMessage.success('已清除个人 Git 凭据')
      return true
    } catch (error) {
      const detail = error.response?.data?.detail
      ElMessage.error(detail || '清除失败')
      return false
    }
  }

  return {
    myCred,
    loading,
    saving,
    load,
    save,
    clear
  }
}
