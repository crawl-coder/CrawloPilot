import request from './request'

// 服务器（真实主机）API

export function getServers(params) {
  return request.get('/servers', { params })
}

export function getServer(id) {
  return request.get(`/servers/${id}`)
}

export function createServer(data) {
  return request.post('/servers', data)
}

export function updateServer(id, data) {
  return request.put(`/servers/${id}`, data)
}

export function deleteServer(id) {
  return request.delete(`/servers/${id}`)
}

export function probeServer(id) {
  return request.post(`/servers/${id}/probe`)
}

export function enterMaintenance(id) {
  return request.post(`/servers/${id}/maintenance`)
}

export function getServerNodes(id) {
  return request.get(`/servers/${id}/nodes`)
}

export function createServerNode(id, data) {
  return request.post(`/servers/${id}/nodes`, data)
}
