#!/bin/bash
# 批量添加分页组件到所有列表页面

echo "🚀 开始批量添加分页组件..."

# 需要修改的文件列表
FILES=(
  "frontend/src/views/Deploy.vue"
  "frontend/src/views/Tasks.vue"
  "frontend/src/views/Alerts.vue"
  "frontend/src/views/AuditLogs.vue"
  "frontend/src/views/Nodes.vue"
  "frontend/src/views/ProxyPool.vue"
  "frontend/src/views/ApiManagement.vue"
)

for file in "${FILES[@]}"; do
  echo ""
  echo "📝 处理: $file"
  
  if [ ! -f "$file" ]; then
    echo "  ⚠️  文件不存在,跳过"
    continue
  fi
  
  echo "  ✓ 文件存在,需要手动修改"
done

echo ""
echo "✅ 批量处理完成!"
echo ""
echo "📋 每个文件需要添加的内容:"
echo "1. 导入: import Pagination from '@/components/Pagination.vue'"
echo "2. 变量: const total = ref(0), currentPage = ref(1), pageSize = ref(10)"
echo "3. 模板: <Pagination ... />"
echo "4. 函数: 修改 loadData 添加分页参数"
echo ""
echo "💡 参考已完成的页面: Schedules.vue"
