import { request } from './request'

export const getProjects = () => request({ url: '/api/model-rank/projects', method: 'get' })
export const createProject = data => request({ url: '/api/model-rank/projects', method: 'post', data })
export const getProject = id => request({ url: `/api/model-rank/projects/${id}`, method: 'get' })
export const removeProject = id => request({ url: `/api/model-rank/projects/${id}`, method: 'delete' })
export const addModel = (id, data, onUploadProgress) => request({
  url: `/api/model-rank/projects/${id}/models`, method: 'post', data, onUploadProgress
})
export const updateModel = (projectId, modelId, data) => request({
  url: `/api/model-rank/projects/${projectId}/models/${modelId}`, method: 'patch', data
})
export const removeModel = (projectId, modelId) => request({
  url: `/api/model-rank/projects/${projectId}/models/${modelId}`, method: 'delete'
})
