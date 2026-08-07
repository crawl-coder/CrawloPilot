/**
 * WebSocket 客户端
 * 
 * 提供任务实时数据推送:
 * - 日志实时推送
 * - 状态实时更新
 * - 控制命令发送
 */

class TaskWebSocket {
  constructor(taskId, options = {}) {
    this.taskId = taskId
    this.ws = null
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
    this.reconnectDelay = 1000 // 1秒
    this.callbacks = {
      onLog: options.onLog || (() => {}),
      onStatus: options.onStatus || (() => {}),
      onMetrics: options.onMetrics || (() => {}),
      onError: options.onError || (() => {}),
      onMessage: options.onMessage || (() => {})
    }
  }
  
  connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const token = localStorage.getItem('token') || ''
    const wsUrl = `${protocol}//${window.location.host}/ws/tasks/${this.taskId}?token=${encodeURIComponent(token)}`
    
    console.log(`🔌 连接 WebSocket: ${wsUrl}`)
    
    this.ws = new WebSocket(wsUrl)
    
    this.ws.onopen = () => {
      console.log(`✅ WebSocket 连接成功: ${this.taskId}`)
      this.reconnectAttempts = 0
    }
    
    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        this.handleMessage(message)
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error)
      }
    }
    
    this.ws.onerror = (error) => {
      console.error(`❌ WebSocket 错误: ${this.taskId}`, error)
      this.callbacks.onError(error)
    }
    
    this.ws.onclose = () => {
      console.warn(`⚠️  WebSocket 断开: ${this.taskId}`)
      this.reconnect()
    }
  }
  
  handleMessage(message) {
    // 通用消息回调
    this.callbacks.onMessage(message)
    
    // 根据消息类型分发
    switch (message.type) {
      case 'log':
        this.callbacks.onLog(message.data)
        break
      case 'status':
        this.callbacks.onStatus(message.data)
        break
      case 'metrics':
        this.callbacks.onMetrics(message.data)
        break
      case 'success':
        console.log('✅ WebSocket 操作成功:', message.message)
        break
      case 'error':
        console.error('❌ WebSocket 操作失败:', message.message)
        break
    }
  }
  
  reconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      console.log(`🔄 重连尝试 ${this.reconnectAttempts}/${this.maxReconnectAttempts}`)
      
      setTimeout(() => {
        this.connect()
      }, this.reconnectDelay * this.reconnectAttempts)
    } else {
      console.error('❌ 达到最大重连次数,停止重连')
    }
  }
  
  // 发送命令
  sendCommand(command) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: command
      }))
      console.log(`📤 发送命令: ${command}`)
    } else {
      console.warn('⚠️  WebSocket 未连接,无法发送命令')
    }
  }
  
  pause() {
    this.sendCommand('pause')
  }
  
  resume() {
    this.sendCommand('resume')
  }
  
  stop() {
    this.sendCommand('stop')
  }
  
  disconnect() {
    if (this.ws) {
      this.ws.close()
      this.ws = null
      console.log(`🔌 WebSocket 已断开: ${this.taskId}`)
    }
  }
}

export default TaskWebSocket
