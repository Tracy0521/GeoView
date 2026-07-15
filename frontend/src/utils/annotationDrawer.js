/**
 * 在 Canvas 上绘制 YOLO 归一化水平检测框
 * 舰船蓝 / 飞机绿 / 发射车红
 */
import { getBoxColor } from './datasetConstants'

/**
 * @param {HTMLCanvasElement} canvas
 * @param {HTMLImageElement} image
 * @param {Array} annotations - [{ class_id, x, y, w, h }]
 */
export function drawAnnotations(canvas, image, annotations = []) {
  const ctx = canvas.getContext('2d')
  const w = image.naturalWidth || image.width
  const h = image.naturalHeight || image.height
  canvas.width = w
  canvas.height = h
  ctx.clearRect(0, 0, w, h)
  ctx.drawImage(image, 0, 0, w, h)

  annotations.forEach(ann => {
    const bw = ann.w * w
    const bh = ann.h * h
    const bx = ann.x * w - bw / 2
    const by = ann.y * h - bh / 2
    const color = getBoxColor(ann.class_id)

    ctx.strokeStyle = color
    ctx.lineWidth = Math.max(2, w / 400)
    ctx.strokeRect(bx, by, bw, bh)

    const label = `#${ann.class_id}`
    ctx.font = `bold ${Math.max(11, w / 50)}px Microsoft YaHei, sans-serif`
    const tw = ctx.measureText(label).width + 8
    const th = Math.max(16, w / 45)
    ctx.fillStyle = color
    ctx.fillRect(bx, Math.max(0, by - th), tw, th)
    ctx.fillStyle = '#fff'
    ctx.fillText(label, bx + 4, Math.max(12, by - 4))
  })
}
