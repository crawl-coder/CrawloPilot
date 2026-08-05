import request from './request'

/**
 * 节点管理 API
 */

// 获取节点列表
export function getNodes(params) {
  return request.get('/nodes', { params })
}

// 获取节点详情
export function getNode(nodeId) {
  return request.get(`/nodes/${nodeId}`)
}

// 创建节点
export function createNode(data) {
  return request.post('/nodes', data)
}

// 更新节点
export function updateNode(nodeId, data) {
  return request.put(`/nodes/${nodeId}`, data)
}

// 测试节点连接
export function testNodeConnection(nodeId) {
  return request.post(`/nodes/${nodeId}/test`)
}

// 删除节点
export function deleteNode(nodeId) {
  return request.delete(`/nodes/${nodeId}`)
}
