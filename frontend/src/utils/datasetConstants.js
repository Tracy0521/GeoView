/**
 * 赛题 25 类 YOLO 遥感数据集常量
 * 0-3 舰船 | 4-23 飞机 | 24 发射车
 */

export const NUM_CLASSES = 25

export const CATEGORY_GROUPS = {
  ship: { label: '舰船', ids: [0, 1, 2, 3], color: '#2d86ff' },
  airplane: { label: '飞机', ids: Array.from({ length: 20 }, (_, i) => i + 4), color: '#31be84' },
  launcher: { label: '发射车', ids: [24], color: '#f4494f' }
}

/** 根据类别 ID 返回分组 key */
export function getCategoryGroup(classId) {
  if (classId >= 0 && classId <= 3) return 'ship'
  if (classId >= 4 && classId <= 23) return 'airplane'
  if (classId === 24) return 'launcher'
  return 'unknown'
}

/** 获取标注框边框颜色 */
export function getBoxColor(classId) {
  const group = getCategoryGroup(classId)
  return CATEGORY_GROUPS[group]?.color || '#999'
}

/** 支持的影像格式说明 */
export const UPLOAD_HINT = 'tif/png/jpg 单图、ZIP 数据集压缩包，单图 < 100MB、压缩包 < 10GB'

/** 支持的文件扩展名（前端校验用） */
export const IMAGE_EXTENSIONS = ['.tif', '.tiff', '.png', '.jpg', '.jpeg']
export const ZIP_EXTENSION = '.zip'
