<template>
  <el-card shadow="never" class="stat-card-wrapper cp-animate-in">
    <div class="stat-card">
      <div class="stat-icon" :style="{ background: color, boxShadow: `0 8px 20px -6px ${color}` }">
        <el-icon :size="28"><component :is="icon" /></el-icon>
      </div>
      <div class="stat-info">
        <div class="stat-value">{{ value }}<span v-if="suffix" class="stat-suffix">{{ suffix }}</span></div>
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
  color: { type: String, default: 'var(--cp-primary)' },
  suffix: { type: String, default: '' }
})
</script>

<style scoped>
.stat-card-wrapper {
  transition: transform var(--cp-motion-base) var(--cp-ease-out),
              box-shadow var(--cp-motion-base) var(--cp-ease-out);
}
.stat-card-wrapper:hover {
  transform: translateY(-3px);
  box-shadow: var(--cp-shadow-2);
}
.stat-card {
  display: flex;
  align-items: center;
  gap: var(--cp-space-md);
}
.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: var(--cp-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
}
.stat-info { flex: 1; min-width: 0; }
.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--cp-text-primary);
  line-height: 1.1;
  margin-bottom: 4px;
  font-variant-numeric: tabular-nums;
}
.stat-suffix {
  font-size: 14px;
  font-weight: 500;
  color: var(--cp-text-secondary);
  margin-left: 2px;
}
.stat-label {
  font-size: 13px;
  color: var(--cp-text-secondary);
}
</style>
