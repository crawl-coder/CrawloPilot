/**
 * 通用分页 composable
 * 消除多个文件中的重复分页逻辑
 */
import { ref, reactive, computed } from 'vue'

export function usePagination(defaultPageSize = 20, defaultLimitKey = 'limit') {
  const page = ref(1)
  const pageSize = ref(defaultPageSize)
  const total = ref(0)
  const loading = ref(false)

  const params = reactive({
    skip: 0,
    offset: 0,
    limit: defaultPageSize
  })

  const updateParams = () => {
    const skip = (page.value - 1) * pageSize.value
    params.skip = skip
    params.offset = skip
    params.limit = pageSize.value
  }

  const handleSizeChange = (newSize) => {
    pageSize.value = newSize
    page.value = 1
    updateParams()
  }

  const handleCurrentChange = (newPage) => {
    page.value = newPage
    updateParams()
  }

  const reset = () => {
    page.value = 1
    updateParams()
  }

  updateParams()

  return {
    page,
    pageSize,
    total,
    loading,
    params,
    updateParams,
    handleSizeChange,
    handleCurrentChange,
    reset
  }
}
