<template>
  <div class="secure-textarea">
    <div v-if="!visible" class="secure-textarea-mask">
      <div class="secure-content">
        <span v-if="modelValue" class="secure-dots">{{ masked }}</span>
        <span v-else class="secure-placeholder">{{ placeholder }}</span>
      </div>
      <el-button link type="primary" size="small" @click="visible = true">
        <el-icon><View /></el-icon>
        显示
      </el-button>
    </div>
    <template v-else>
      <el-input
        :model-value="modelValue"
        type="textarea"
        :rows="rows"
        :placeholder="placeholder"
        @update:model-value="$emit('update:modelValue', $event)"
      />
      <div class="secure-actions">
        <el-button link type="primary" size="small" @click="visible = false">
          <el-icon><Hide /></el-icon>
          隐藏
        </el-button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { View, Hide } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  rows: { type: Number, default: 4 },
  placeholder: { type: String, default: '' }
})

defineEmits(['update:modelValue'])

const visible = ref(false)
const masked = computed(() => {
  const len = Math.max(props.modelValue.length || 12, 12)
  return '•'.repeat(Math.min(len, 80))
})
</script>

<style scoped>
.secure-textarea {
  width: 100%;
}

.secure-textarea-mask {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 102px;
  padding: 8px 12px;
  border: 1px solid var(--cp-border-light);
  border-radius: var(--cp-radius-sm);
  background: var(--cp-page-bg);
}

.secure-content {
  flex: 1;
  min-width: 0;
}

.secure-dots {
  font-size: 14px;
  color: var(--cp-text-primary);
  letter-spacing: 2px;
  word-break: break-all;
}

.secure-placeholder {
  font-size: 14px;
  color: var(--el-text-color-placeholder);
}

.secure-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 4px;
}
</style>
