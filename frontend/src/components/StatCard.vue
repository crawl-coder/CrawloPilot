<template>
  <el-card shadow="hover" class="stat-card-wrapper">
    <div class="stat-card">
      <div class="stat-icon" :style="{ background: color }">
        <el-icon :size="30"><component :is="icon" /></el-icon>
      </div>
      <div class="stat-info">
        <div class="stat-value">{{ value }}</div>
        <div class="stat-label">{{ label }}</div>
      </div>
    </div>
  </el-card>
</template>

<script setup>
defineProps({
  icon: { type: [Object, String], required: true },
  value: { type: [Number, String], default: 0 },
  label: { type: String, required: true },
  color: { type: String, default: '#409EFF' }
})
</script>

<style scoped>
.stat-card {
  display: flex;
  align-items: center;
  gap: 15px;
}
.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}
.stat-info { flex: 1; }
.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
  line-height: 1;
  margin-bottom: 5px;
}
.stat-label {
  font-size: 14px;
  color: #909399;
}
</style>
