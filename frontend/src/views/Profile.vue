<template>
  <div class="profile-container">
    <div class="page-header">
      <h2>个人中心</h2>
      <span class="page-subtitle">账号信息与 Git 凭据管理</span>
    </div>

    <ProfileHero :user="userStore.user" :loading="userLoading" />
    <MyGitCredentialCard />
    <SharedGitCredentialCard v-if="userStore.isAdmin" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useUserStore } from '@/stores/user'
import ProfileHero from '@/components/profile/ProfileHero.vue'
import MyGitCredentialCard from '@/components/profile/MyGitCredentialCard.vue'
import SharedGitCredentialCard from '@/components/profile/SharedGitCredentialCard.vue'

const userStore = useUserStore()
const userLoading = ref(false)

onMounted(async () => {
  if (!userStore.user) {
    userLoading.value = true
    try {
      await userStore.fetchUser()
    } finally {
      userLoading.value = false
    }
  }
})
</script>

<style scoped>
.profile-container {
  padding: 0;
  max-width: 1080px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  gap: var(--cp-space-sm);
  margin-bottom: var(--cp-space-lg);
}

.page-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: var(--cp-text-primary);
}

.page-subtitle {
  font-size: 13px;
  color: var(--cp-text-secondary);
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
}
</style>
