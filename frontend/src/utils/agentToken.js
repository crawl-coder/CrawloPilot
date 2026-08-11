import { h } from 'vue'
import { ElMessageBox } from 'element-plus'
import AgentTokenBox from '@/components/AgentTokenBox.vue'

/**
 * 展示 Agent 注册令牌弹窗（带样式 + 一键复制）
 */
export function showAgentTokenDialog({ token, serverUrl, nodeName = '', nodeId = null }) {
  const title = nodeName ? `Agent 注册令牌 - ${nodeName}` : 'Agent 注册令牌'
  return ElMessageBox({
    title,
    message: h(AgentTokenBox, { token, serverUrl, nodeName, nodeId }),
    confirmButtonText: '关闭',
    showCancelButton: false,
    closeOnClickModal: true,
    customClass: 'agent-token-dialog',
    width: 520
  })
}
