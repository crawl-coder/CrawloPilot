import request from './request'

export function getProjects(params) {
  return request.get('/projects', { params })
}

export function createProject(data) {
  return request.post('/projects', data)
}

export function getProject(id) {
  return request.get(`/projects/${id}`)
}

export function updateProject(id, data) {
  return request.put(`/projects/${id}`, data)
}

export function deleteProject(id) {
  return request.delete(`/projects/${id}`)
}

export function getProjectVersions(id) {
  return request.get(`/projects/${id}/versions`)
}

export function createProjectVersion(id, data) {
  return request.post(`/projects/${id}/versions`, data)
}
