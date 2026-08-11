<template>
  <div class="agent-token-box">
    <div v-if="nodeName || nodeId" class="atb-meta">
      <span v-if="nodeName">节点：{{ nodeName }}</span>
      <span v-if="nodeId">节点 ID：{{ nodeId }}</span>
    </div>

    <div class="atb-label">在节点服务器上运行：</div>

    <div class="atb-command" :class="{ copied }" @click="copy">
      <code>{{ command }}</code>
      <span class="atb-copy-hint">{{ copied ? '已复制 ✓' : '点击复制' }}</span>
    </div>

    <div class="atb-actions">
      <el-button type="primary" size="small" :icon="copied ? Check : CopyDocument" @click="copy">
        {{ copied ? '已复制到剪贴板' : '复制命令' }}
      </el-button>
    </div>

    <div class="atb-tip">令牌用于节点 agent 注册，请妥善保管；agent 启动后会自动注册并上线。</div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Check, CopyDocument } from '@element-plus/icons-vue'

const props = defineProps({
  token: { type: String, required: true },
  serverUrl: { type: String, default: '' },
  nodeName: { type: String, default: '' },
  nodeId: { type: [Number, String], default: null }
})

const copied = ref(false)
const command = computed(() => `python crawlo_agent.py --server ${props.serverUrl} --token ${props.token}`)

const copy = async () => {
  const text = command.value
  let ok = false
  try {
    await navigator.clipboard.writeText(text)
    ok = true
  } catch (e) {
    try {
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      ok = document.execCommand('copy')
      document.body.removeChild(ta)
    } catch (e2) {
      ok = false
    }
  }
  copied.value = ok
  if (ok) setTimeout(() => (copied.value = false), 2500)
}
</script>

<style scoped>
.agent-token-box {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 4px 2px;
}

.atb-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #909399;
}

.atb-label {
  font-size: 13px;
  color: #606266;
}

.atb-command {
  position: relative;
  background: #0f172a;
  border-radius: 8px;
  padding: 12px 14px;
  cursor: pointer;
  transition: background 0.2s;
}

.atb-command:hover {
  background: #1e293b;
}

.atb-command code {
  display: block;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 12.5px;
  line-height: 1.7;
  color: #e2e8f0;
  word-break: break-all;
  white-space: pre-wrap;
  user-select: all;
  padding-right: 64px;
}

.atb-copy-hint {
  position: absolute;
  top: 10px;
  right: 12px;
  font-size: 11px;
  color: #64748b;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 4px;
  padding: 2px 6px;
}

.atb-command.copied .atb-copy-hint {
  color: #34d399;
}

.atb-tip {
  font-size: 12px;
  color: #b88230;
  background: #fdf6ec;
  border-radius: 6px;
  padding: 8px 10px;
  line-height: 1.6;
}
</style>
