<template>
  <main class="dataset-page">
    <!-- 页头 -->
    <header>
      <div>
        <span class="eyebrow">数据集管理</span>
        <h1>遥感影像与 YOLO 标注</h1>
        <p>上传、校验和管理 25 类遥感时敏目标数据集，支持舰船、飞机、发射车三大类标注。</p>
      </div>
      <button class="dark-button" @click="openCreateDialog">＋ 新建数据集</button>
    </header>

    <!-- 统计栏 -->
    <section class="stats-bar">
      <div v-for="item in statItems" :key="item.key" class="stat-block">
        <span class="stat-value">{{ stats[item.key] ?? 0 }}</span>
        <span class="stat-label">{{ item.label }}</span>
      </div>
    </section>

    <!-- 上传区 + 预处理 -->
    <section class="upload-panel">
      <div
        class="drop-zone"
        :class="{ dragging: isDragging }"
        @dragover.prevent="isDragging = true"
        @dragleave.prevent="isDragging = false"
        @drop.prevent="onDrop"
        @click="triggerFileInput"
      >
        <input
          ref="fileInput"
          type="file"
          multiple
          accept=".tif,.tiff,.png,.jpg,.jpeg,.zip,.txt"
          hidden
          @change="onFileSelect"
        >
        <span class="cloud-icon">☁</span>
        <strong>拖拽或点击上传遥感影像、YOLO 标注数据集</strong>
        <small>投放遥感影像、YOLO 标注数据集压缩包</small>
        <p class="format-hint">{{ uploadHint }}</p>
      </div>

      <!-- 图像预处理控件（复用平台现有工具） -->
      <div class="preprocess-row">
        <span class="pre-label">图像增强</span>
        <label class="pre-check">
          <input ref="clahe" type="checkbox" @change="togglePrehandle(2, 'clahe')"> CLAHE 增强
        </label>
        <label class="pre-check">
          <input ref="sharpen" type="checkbox" @change="togglePrehandle(4, 'sharpen')"> 锐化
        </label>
        <span class="pre-label">降噪处理</span>
        <label class="pre-check">
          <input ref="smooth" type="checkbox" @change="toggleDenoise(3, 'smooth')"> 平滑
        </label>
        <label class="pre-check">
          <input ref="filter" type="checkbox" @change="toggleDenoise(5, 'filter')"> 滤波
        </label>
        <button
          class="pre-apply-btn"
          :disabled="!activeDatasetId || preprocessing"
          @click="applyPreprocess"
        >
          {{ preprocessing ? '处理中…' : '应用预处理到选中数据集' }}
        </button>
      </div>

      <!-- 目标类别图例 -->
      <div class="legend">
        <span v-for="(g, key) in categoryGroups" :key="key" class="legend-item">
          <i :style="{ background: g.color }" />{{ g.label }} (ID {{ g.ids[0] }}–{{ g.ids[g.ids.length - 1] }})
        </span>
      </div>
    </section>

    <!-- 数据集列表 -->
    <section class="list-panel">
      <div class="list-header">
        <h2>我的数据集</h2>
        <span>{{ datasets.length }} 个数据集</span>
      </div>

      <div v-if="datasets.length" class="dataset-grid">
        <article v-for="ds in datasets" :key="ds.id" class="dataset-card">
          <!-- 悬浮标注预览；点击缩略图进入详情 -->
          <div
            class="thumb-wrap clickable"
            @mouseenter="showPreview(ds)"
            @mouseleave="hidePreview"
            @click="openDataset(ds.id)"
          >
            <img
              v-if="ds.preview_url"
              :src="fullUrl(ds.preview_url)"
              :alt="ds.name"
              class="thumb"
            >
            <div v-else class="thumb empty-thumb">暂无影像</div>
            <!-- 悬浮时渲染检测框 -->
            <canvas
              v-show="previewDatasetId === ds.id && previewReady"
              ref="previewCanvas"
              class="preview-canvas"
            />
          </div>

          <div class="card-body">
            <h3 class="clickable" @click="openDataset(ds.id)">{{ ds.name }}</h3>
            <p>
              {{ ds.image_count }} 张影像 · {{ ds.box_count }} 个标注框 ·
              {{ ds.class_count }} 类
            </p>
            <small>上传于 {{ formatTime(ds.updated_at) }}</small>
          </div>

          <div class="card-actions">
            <button title="查看影像与标注" @click="openDataset(ds.id)">查看</button>
            <button title="上传到此数据集" @click.stop="setActiveAndUpload(ds.id)">上传</button>
            <button title="重命名" @click="openRename(ds)">重命名</button>
            <button title="划分训练/验证集" @click="doSplit(ds.id)">划分</button>
            <button title="导出 YOLO 格式" @click="doExport(ds.id)">导出</button>
            <button class="danger" title="删除" @click="doDelete(ds)">删除</button>
          </div>
        </article>
      </div>
      <div v-else class="empty-state">
        还没有数据集，点击右上角「新建数据集」或拖拽上传开始。
      </div>
    </section>

    <!-- 新建数据集弹窗 -->
    <el-dialog v-model="createVisible" title="新建数据集" width="460px">
      <el-form label-position="top">
        <el-form-item label="数据集名称">
          <el-input v-model="createForm.name" maxlength="60" placeholder="例如：舰船检测训练集" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="confirmCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 重命名弹窗 -->
    <el-dialog v-model="renameVisible" title="重命名数据集" width="460px">
      <el-input v-model="renameForm.name" maxlength="60" />
      <template #footer>
        <el-button @click="renameVisible = false">取消</el-button>
        <el-button type="primary" :loading="renaming" @click="confirmRename">保存</el-button>
      </template>
    </el-dialog>
  </main>
</template>

<script>
import {
  getDatasetStats,
  getDatasets,
  createDataset,
  renameDataset,
  deleteDataset,
  uploadToDataset,
  splitDataset,
  preprocessDataset,
  exportDatasetUrl
} from '@/api/dataset'
import { CATEGORY_GROUPS, UPLOAD_HINT } from '@/utils/datasetConstants'
import { drawAnnotations } from '@/utils/annotationDrawer'
import { consumeQueuedFiles } from '@/utils/datasetUploadQueue'
import global from '@/global'
import { ElMessageBox } from 'element-plus'

export default {
  name: 'DatasetManagement',
  data() {
    return {
      stats: { dataset_count: 0, image_count: 0, box_count: 0, class_count: 0 },
      statItems: [
        { key: 'dataset_count', label: '数据集总数' },
        { key: 'image_count', label: '影像总数量' },
        { key: 'box_count', label: '标注框总数量' },
        { key: 'class_count', label: '标注类别总数' }
      ],
      datasets: [],
      categoryGroups: CATEGORY_GROUPS,
      uploadHint: UPLOAD_HINT,
      isDragging: false,
      uploading: false,
      preprocessing: false,
      activeDatasetId: null,
      prehandle: 0,
      denoise: 0,
      createVisible: false,
      creating: false,
      createForm: { name: '' },
      renameVisible: false,
      renaming: false,
      renameForm: { id: '', name: '' },
      previewDatasetId: null,
      previewReady: false
    }
  },
  mounted() {
    this.loadAll()
    if (this.$route.query.action === 'create') {
      this.openCreateDialog()
    }
    // 消费首页拖拽暂存的文件
    const queued = consumeQueuedFiles()
    if (queued.length) this.handleUpload(queued)
  },
  methods: {
    fullUrl(path) {
      if (!path) return ''
      if (path.startsWith('http')) return path
      return global.BASEURL.replace(/\/$/, '') + path
    },
    formatTime(iso) {
      if (!iso) return '—'
      return iso.replace('T', ' ').slice(0, 16)
    },
    async loadAll() {
      try {
        const [statsRes, listRes] = await Promise.all([
          getDatasetStats(),
          getDatasets()
        ])
        this.stats = statsRes.data.data
        this.datasets = listRes.data.data
        if (this.datasets.length && !this.activeDatasetId) {
          this.activeDatasetId = this.datasets[0].id
        }
      } catch { /* 拦截器已提示 */ }
    },
    openCreateDialog() {
      this.createForm.name = ''
      this.createVisible = true
    },
    async confirmCreate() {
      this.creating = true
      try {
        const res = await createDataset({ name: this.createForm.name })
        this.createVisible = false
        this.activeDatasetId = res.data.data.id
        await this.loadAll()
        this.$message.success('数据集创建成功')
      } finally {
        this.creating = false
      }
    },
    triggerFileInput() {
      this.$refs.fileInput.click()
    },
    onFileSelect(e) {
      const files = Array.from(e.target.files || [])
      if (files.length) this.handleUpload(files)
      e.target.value = ''
    },
    onDrop(e) {
      this.isDragging = false
      const files = Array.from(e.dataTransfer.files || [])
      if (files.length) this.handleUpload(files)
    },
    async ensureDataset() {
      if (this.activeDatasetId) return this.activeDatasetId
      const res = await createDataset({ name: '' })
      this.activeDatasetId = res.data.data.id
      return this.activeDatasetId
    },
    async handleUpload(files) {
      const id = await this.ensureDataset()
      const formData = new FormData()
      files.forEach(f => formData.append('files', f))
      this.uploading = true
      try {
        const res = await uploadToDataset(id, formData)
        const { warnings, has_errors, imported_count } = res.data.data
        await this.loadAll()
        if (warnings?.length) {
          const msg = warnings.slice(0, 8).join('\n') +
            (warnings.length > 8 ? `\n…共 ${warnings.length} 条提示` : '')
          if (has_errors) {
            ElMessageBox.alert(msg, '标注校验告警', { type: 'warning' })
          } else {
            this.$message.warning(`上传完成（${imported_count} 项），部分提示：${warnings[0]}`)
          }
        } else {
          this.$message.success(`成功导入 ${imported_count} 项`)
        }
      } finally {
        this.uploading = false
      }
    },
    openDataset(id) {
      this.$router.push(`/dataset-management/${id}`)
    },
    setActiveAndUpload(id) {
      this.activeDatasetId = id
      this.triggerFileInput()
    },
    openRename(ds) {
      this.renameForm = { id: ds.id, name: ds.name }
      this.renameVisible = true
    },
    async confirmRename() {
      if (!this.renameForm.name.trim()) return this.$message.warning('名称不能为空')
      this.renaming = true
      try {
        await renameDataset(this.renameForm.id, this.renameForm.name)
        this.renameVisible = false
        await this.loadAll()
        this.$message.success('重命名成功')
      } finally {
        this.renaming = false
      }
    },
    async doSplit(id) {
      try {
        await ElMessageBox.confirm(
          '将按 80% / 20% 随机划分训练集与验证集，是否继续？',
          '划分数据集',
          { type: 'info' }
        )
        const res = await splitDataset(id, 0.8)
        this.$message.success(res.data.msg)
        await this.loadAll()
      } catch { /* 取消 */ }
    },
    doExport(id) {
      window.open(exportDatasetUrl(id), '_blank')
    },
    async doDelete(ds) {
      try {
        await ElMessageBox.confirm(
          `确定删除数据集「${ds.name}」？此操作不可恢复。`,
          '删除确认',
          { type: 'warning' }
        )
        await deleteDataset(ds.id)
        if (this.activeDatasetId === ds.id) this.activeDatasetId = null
        await this.loadAll()
        this.$message.success('已删除')
      } catch { /* 取消 */ }
    },
    togglePrehandle(code, refName) {
      const checked = this.$refs[refName].checked
      if (code === 2 && checked) {
        if (this.$refs.sharpen) this.$refs.sharpen.checked = false
      }
      if (code === 4 && checked) {
        if (this.$refs.clahe) this.$refs.clahe.checked = false
      }
      this.prehandle = checked ? code : 0
    },
    toggleDenoise(code, refName) {
      const checked = this.$refs[refName].checked
      if (code === 3 && checked && this.$refs.filter) {
        this.$refs.filter.checked = false
      }
      if (code === 5 && checked && this.$refs.smooth) {
        this.$refs.smooth.checked = false
      }
      this.denoise = checked ? code : 0
    },
    async applyPreprocess() {
      if (!this.activeDatasetId) return this.$message.warning('请先选择或创建数据集')
      if (!this.prehandle && !this.denoise) {
        return this.$message.warning('请至少选择一种预处理方式')
      }
      const ds = this.datasets.find(d => d.id === this.activeDatasetId)
      if (!ds?.images?.length) return this.$message.warning('数据集中暂无影像')
      this.preprocessing = true
      try {
        await preprocessDataset(this.activeDatasetId, {
          filenames: ds.images.map(i => i.filename),
          prehandle: this.prehandle,
          denoise: this.denoise
        })
        this.$message.success('预处理完成')
        await this.loadAll()
      } finally {
        this.preprocessing = false
      }
    },
    showPreview(ds) {
      if (!ds.images?.length) return
      this.previewDatasetId = ds.id
      const imgData = ds.images[0]
      const img = new Image()
      img.crossOrigin = 'anonymous'
      img.onload = () => {
        this.previewReady = true
        this.$nextTick(() => {
          const canvas = this.$refs.previewCanvas
          const el = Array.isArray(canvas) ? canvas[0] : canvas
          if (el) drawAnnotations(el, img, imgData.annotations || [])
        })
      }
      img.src = this.fullUrl(imgData.url)
    },
    hidePreview() {
      this.previewDatasetId = null
      this.previewReady = false
    }
  }
}
</script>

<style scoped>
.dataset-page {
  min-height: calc(100vh - 60px);
  padding: 38px;
  background: #f7f9fc;
  color: #192234;
  font-family: "Microsoft YaHei", sans-serif;
  box-sizing: border-box;
}
.dataset-page header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  max-width: 1180px;
  margin: 0 auto 22px;
}
.eyebrow { color: #3388ee; font-size: 12px; font-weight: 800; letter-spacing: 1.5px; }
header h1 { margin: 7px 0; font-size: 30px; }
header p { margin: 0; color: #7f899b; font-size: 14px; }
.dark-button {
  padding: 13px 20px; border: 0; border-radius: 10px;
  background: #151515; color: #fff; font-weight: 700; cursor: pointer;
}
.dark-button:hover { background: #2a2a2a; }

/* 统计栏 */
.stats-bar {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  max-width: 1180px;
  margin: 0 auto 22px;
}
.stat-block {
  padding: 20px 22px;
  border: 1px solid #e3e8ef;
  border-radius: 14px;
  background: #fff;
  text-align: center;
  box-shadow: 0 4px 16px rgba(31, 45, 70, .04);
}
.stat-value { display: block; font-size: 28px; font-weight: 800; color: #2684ff; }
.stat-label { display: block; margin-top: 6px; font-size: 13px; color: #7f899b; }

/* 上传区 */
.upload-panel {
  max-width: 1180px;
  margin: 0 auto 28px;
  padding: 24px;
  border: 1px solid #e3e8ef;
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 6px 24px rgba(31, 45, 70, .05);
}
.drop-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 42px 20px;
  border: 2px dashed #b3d4fc;
  border-radius: 14px;
  background: #f0f7ff;
  cursor: pointer;
  transition: .2s;
}
.drop-zone.dragging, .drop-zone:hover {
  border-color: #409eff;
  background: #e8f3ff;
}
.cloud-icon { font-size: 36px; color: #409eff; font-style: normal; }
.drop-zone strong { font-size: 15px; color: #333; }
.drop-zone small { color: #6b7a8d; }
.format-hint { margin: 4px 0 0; font-size: 12px; color: #9aa5b3; }

.preprocess-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 18px;
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid #edf0f5;
}
.pre-label { font-size: 13px; font-weight: 700; color: #5a6478; }
.pre-check { font-size: 13px; color: #444; cursor: pointer; display: flex; align-items: center; gap: 5px; }
.pre-apply-btn {
  margin-left: auto;
  padding: 8px 16px;
  border: 1px solid #409eff;
  border-radius: 8px;
  background: #fff;
  color: #409eff;
  font-size: 13px;
  cursor: pointer;
}
.pre-apply-btn:disabled { opacity: .5; cursor: not-allowed; }

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-top: 14px;
}
.legend-item { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #6b7a8d; }
.legend-item i { display: inline-block; width: 14px; height: 14px; border-radius: 3px; }

/* 列表 */
.list-panel {
  max-width: 1180px;
  margin: 0 auto;
  padding: 24px;
  border: 1px solid #e3e8ef;
  border-radius: 18px;
  background: #fff;
}
.list-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; }
.list-header h2 { margin: 0; font-size: 20px; }
.list-header span { font-size: 13px; color: #8c96a7; }

.dataset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
.dataset-card {
  border: 1px solid #e5e9ef;
  border-radius: 14px;
  overflow: hidden;
  transition: .2s;
}
.dataset-card:hover {
  border-color: #bcd8fb;
  box-shadow: 0 6px 18px rgba(45, 100, 165, .08);
}
.thumb-wrap { position: relative; height: 160px; background: #f2f6fb; overflow: hidden; }
.thumb { width: 100%; height: 100%; object-fit: cover; }
.empty-thumb { display: grid; place-items: center; color: #aab4c3; font-size: 13px; }
.preview-canvas {
  position: absolute; inset: 0;
  width: 100%; height: 100%;
  object-fit: cover;
}
.card-body { padding: 14px 16px 8px; }
.clickable { cursor: pointer; }
.thumb-wrap.clickable:hover .thumb,
.thumb-wrap.clickable:hover .empty-thumb { opacity: .92; }
.card-body h3 { margin: 0 0 6px; font-size: 16px; }
.card-body h3.clickable:hover { color: #409eff; }
.card-body p { margin: 0; font-size: 12px; color: #7f8998; }
.card-body small { font-size: 11px; color: #aab4c3; }
.card-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px 12px 12px;
}
.card-actions button {
  padding: 5px 10px;
  border: 1px solid #dde3ec;
  border-radius: 6px;
  background: #fff;
  font-size: 12px;
  cursor: pointer;
  color: #4a5568;
}
.card-actions button:hover { border-color: #409eff; color: #409eff; }
.card-actions button.danger:hover { border-color: #f56c6c; color: #f56c6c; }

.empty-state { text-align: center; padding: 40px; color: #9aa3b1; font-size: 14px; }

@media (max-width: 800px) {
  .dataset-page { padding: 24px 16px; }
  .dataset-page header { flex-direction: column; align-items: flex-start; gap: 16px; }
  .stats-bar { grid-template-columns: 1fr 1fr; }
}
</style>
