import request from './request'

// 部署相关 API
export function createDeploy(data) {
  return request.post('/deploys', data)
}

export function getDeploys(params) {
  return request.get('/deploys', { params })
}

export function getDeploy(id) {
  return request.get(`/deploys/${id}`)
}

export function rollbackDeploy(id) {
  return request.post(`/deploys/${id}/rollback`)
}

export function retryDeploy(id) {
  return request.post(`/deploys/${id}/retry`)
}

// 节点相关 API
export function createNode(data) {
  return request.post('/nodes', data)
}

export function getNodes(params) {
  return request.get('/nodes', { params })
}

export function getNode(id) {
  return request.get(`/nodes/${id}`)
}

export function testNodeConnection(id) {
  return request.post(`/nodes/${id}/test`)
}

export function checkNodesHealth() {
  return request.post('/nodes/health-check')
}

export function drainNode(id) {
  return request.post(`/nodes/${id}/drain`)
}

export function activateNode(id) {
  return request.post(`/nodes/${id}/activate`)
}

export function deleteNode(id) {
  return request.delete(`/nodes/${id}`)
}

export function getNodeContainers(id) {
  return request.get(`/nodes/${id}/containers`)
}

export function updateNode(id, data) {
  return request.put(`/nodes/${id}`, data)
}
