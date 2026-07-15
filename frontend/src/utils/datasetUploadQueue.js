/**
 * 首页拖拽上传的文件暂存队列
 * 跳转到数据集管理页后自动消费并上传
 */
let pendingFiles = []

export function queueFiles(files) {
  pendingFiles = Array.from(files)
}

export function consumeQueuedFiles() {
  const files = pendingFiles
  pendingFiles = []
  return files
}

export function hasQueuedFiles() {
  return pendingFiles.length > 0
}
