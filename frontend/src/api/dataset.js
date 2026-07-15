/**
 * 数据集管理 API — 与模型排行模块完全独立
 */
import { request } from './request'
import { requestfile } from './requestfile'
import global from '@/global'

export const getDatasetStats = () =>
  request({ url: '/api/dataset/stats', method: 'get' })

export const getDatasetSamples = () =>
  request({ url: '/api/dataset/samples', method: 'get' })

export const getDatasets = () =>
  request({ url: '/api/dataset/list', method: 'get' })

export const getDataset = id =>
  request({ url: `/api/dataset/${id}`, method: 'get' })

export const createDataset = data =>
  request({ url: '/api/dataset/create', method: 'post', data })

export const renameDataset = (id, name) =>
  request({ url: `/api/dataset/${id}/rename`, method: 'put', data: { name } })

export const deleteDataset = id =>
  request({ url: `/api/dataset/${id}`, method: 'delete' })

export const uploadToDataset = (id, formData, onUploadProgress) =>
  requestfile({
    url: `/api/dataset/${id}/upload`,
    method: 'post',
    data: formData,
    onUploadProgress
  })

export const splitDataset = (id, trainRatio = 0.8) =>
  request({
    url: `/api/dataset/${id}/split`,
    method: 'post',
    data: { train_ratio: trainRatio }
  })

export const preprocessDataset = (id, data) =>
  request({
    url: `/api/dataset/${id}/preprocess`,
    method: 'post',
    data
  })

/** 导出 YOLO 格式 ZIP（浏览器直接下载） */
export const exportDatasetUrl = id =>
  `${global.BASEURL}api/dataset/${id}/export`
