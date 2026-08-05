import request from './request'

// 团队 API
export function getTeams() {
  return request.get('/teams')
}
