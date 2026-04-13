<template>
  <el-pagination
    v-if="total > 0"
    :current-page="localCurrentPage"
    :page-size="localPageSize"
    :page-sizes="pageSizes"
    :total="total"
    :layout="layout"
    :background="background"
    style="margin-top: 20px; justify-content: flex-end"
    @size-change="handleSizeChange"
    @current-change="handleCurrentChange"
  />
</template>

<script setup>
import { ref, watch } from 'vue'

/**
 * 通用分页组件
 * 
 * 使用示例:
 * <Pagination
 *   v-model:current-page="currentPage"
 *   v-model:page-size="pageSize"
 *   :total="total"
 *   @change="loadData"
 * />
 */

const props = defineProps({
  // 当前页码
  currentPage: {
    type: Number,
    default: 1
  },
  // 每页数量
  pageSize: {
    type: Number,
    default: 10
  },
  // 总记录数
  total: {
    type: Number,
    default: 0
  },
  // 每页数量选项
  pageSizes: {
    type: Array,
    default: () => [10, 20, 50, 100]
  },
  // 分页布局
  layout: {
    type: String,
    default: 'total, sizes, prev, pager, next, jumper'
  },
  // 是否带背景色
  background: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['update:currentPage', 'update:pageSize', 'change'])

// 本地变量
const localCurrentPage = ref(props.currentPage)
const localPageSize = ref(props.pageSize)

// 监听 props 变化
watch(() => props.currentPage, (newVal) => {
  localCurrentPage.value = newVal
})

watch(() => props.pageSize, (newVal) => {
  localPageSize.value = newVal
})

const handleSizeChange = (size) => {
  localPageSize.value = size
  localCurrentPage.value = 1
  emit('update:pageSize', size)
  emit('update:currentPage', 1) // 重置到第一页
  emit('change', { page: 1, size })
}

const handleCurrentChange = (page) => {
  localCurrentPage.value = page
  emit('update:currentPage', page)
  emit('change', { page, size: localPageSize.value })
}
</script>
