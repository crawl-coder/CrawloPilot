<template>
  <el-card class="profile-card profile-hero cp-animate-in" shadow="never" v-loading="loading">
    <div class="hero">
      <div class="hero-avatar" :style="avatarStyle">{{ initial }}</div>
      <div class="hero-info">
        <div class="hero-name-row">
          <span class="hero-name">{{ user?.username || '未知用户' }}</span>
          <el-tag
            v-for="role in user?.roles || []"
            :key="role.id"
            :type="role.name === 'admin' ? 'primary' : 'info'"
            effect="light"
            size="small"
            round
          >
            {{ role.name }}
          </el-tag>
        </div>
        <div class="hero-meta">
          <span class="meta-item">
            <el-icon><Message /></el-icon>
            {{ user?.email || '未设置邮箱' }}
          </span>
          <span class="meta-item">
            <el-icon><User /></el-icon>
            {{ user?.full_name || '未设置姓名' }}
          </span>
          <span class="meta-item">
            <el-icon><Calendar /></el-icon>
            注册于 {{ formatDateTime(user?.created_at) }}
          </span>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'
import { Message, User, Calendar } from '@element-plus/icons-vue'
import { formatDateTime } from '@/utils/common'

const props = defineProps({
  user: { type: Object, default: null },
  loading: { type: Boolean, default: false }
})

const initial = computed(() => (props.user?.username || '?').charAt(0).toUpperCase())

function stringToHue(str) {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash)
  }
  return Math.abs(hash % 360)
}

const avatarStyle = computed(() => {
  const hue = stringToHue(props.user?.username || '')
  return {
    background: `linear-gradient(135deg, hsl(${hue}, 72%, 56%) 0%, hsl(${(hue + 45) % 360}, 72%, 62%) 100%)`
  }
})
</script>

<style scoped>
@import './profile-shared.css';

.hero {
  display: flex;
  align-items: center;
  gap: var(--cp-space-lg);
  padding: var(--cp-space-xs) var(--cp-space-sm);
}

.hero-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  font-weight: 600;
  color: #fff;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.15);
  flex-shrink: 0;
}

.hero-name-row {
  display: flex;
  align-items: center;
  gap: var(--cp-space-xs);
  margin-bottom: var(--cp-space-xs);
  flex-wrap: wrap;
}

.hero-name {
  font-size: 18px;
  font-weight: 600;
  color: var(--cp-text-primary);
}

.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--cp-space-xs) var(--cp-space-lg);
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  color: var(--cp-text-secondary);
}

.meta-item .el-icon {
  font-size: 14px;
}

@media (max-width: 768px) {
  .hero {
    flex-direction: column;
    align-items: flex-start;
    text-align: left;
  }
}
</style>
