<template>
  <main v-if="dataset" class="detail-page">
    <header class="page-header">
      <div>
        <div class="back" @click="$router.push('/dataset-management')">← 返回数据集列表</div>
        <h1>{{ dataset.name }}</h1>
        <p class="meta">
          {{ dataset.image_count }} 张影像 · {{ dataset.box_count }} 个标注框 ·
          {{ dataset.class_count }} 类 · 更新于 {{ formatTime(dataset.updated_at) }}
        </p>
      </div>
      <button class="dark-button" @click="doExport">导出 YOLO</button>
    </header>

    <div class="workspace">
      <aside class="image-panel">
        <el-input v-model="keyword" clearable placeholder="搜索文件名…" />
        <!-- 绑定滚动监听，触底加载下一页 -->
        <div class="image-list" @scroll="onImageScroll">
          <button
              v-for="img in filteredImages"
              :key="img.id"
              type="button"
              class="image-item"
              :class="{ active: selectedImage?.id === img.id }"
              @click="selectImage(img)"
          >
            <img :src="fullUrl(img.url)" :alt="img.filename" loading="lazy">
            <span class="item-info">
              <strong>{{ img.filename }}</strong>
              <small>
                {{ img.box_count }} 框
                <template v-if="img.split && img.split !== 'unset'"> · {{ img.split === 'train' ? '训练' : '验证' }}</template>
              </small>
            </span>
          </button>
          <div v-if="loading" class="load-tip">加载中……</div>
          <div v-if="!hasMore && imageList.length > 0" class="load-tip">已加载全部影像</div>
        </div>
      </aside>

      <section v-if="selectedImage" class="viewer-panel">
        <div class="viewer-toolbar">
          <strong>{{ selectedImage.filename }}</strong>
          <span>{{ selectedImage.box_count }} 个标注框</span>
          <span v-if="selectedImage.split && selectedImage.split !== 'unset'" class="split-tag">
            {{ selectedImage.split === 'train' ? '训练集' : '验证集' }}
          </span>
        </div>
        <div class="canvas-wrap">
          <canvas ref="viewerCanvas" class="viewer-canvas" />
        </div>
        <div v-if="selectedImage.annotations?.length" class="annotation-table">
          <div class="table-head">标注明细</div>
          <div
              v-for="(ann, idx) in selectedImage.annotations"
              :key="idx"
              class="ann-row"
          >
            <i :style="{ background: getBoxColor(ann.class_id) }" />
            <span>类别 #{{ ann.class_id }}</span>
            <span>{{ categoryLabel(ann.class_id) }}</span>
            <span>x={{ ann.x.toFixed(4) }} y={{ ann.y.toFixed(4) }}</span>
            <span>w={{ ann.w.toFixed(4) }} h={{ ann.h.toFixed(4) }}</span>
          </div>
        </div>
        <div v-if="selectedImage.warnings?.length" class="warnings">
          <div v-for="(w, i) in selectedImage.warnings" :key="i">{{ w }}</div>
        </div>
      </section>
    </div>

    <div v-if="imageList.length === 0 && !loading" class="empty-state">该数据集暂无影像，请返回列表上传文件。</div>
  </main>
</template>

<script>
import { getDataset, exportDatasetUrl } from '@/api/dataset'
import { drawAnnotations } from '@/utils/annotationDrawer'
import { CATEGORY_GROUPS, getBoxColor, getCategoryGroup } from '@/utils/datasetConstants'
import global from '@/global'

export default {
  name: 'DatasetDetail',
  data() {
    return {
      dataset: null,
      keyword: '',
      selectedImage: null,

      // 分页控制
      imageList: [],
      page: 1,
      pageSize: 16,
      hasMore: true,
      loading: false
    }
  },
  computed: {
    filteredImages() {
      const images = this.imageList
      const key = this.keyword.trim().toLowerCase()
      if (!key) return images
      return images.filter(img => img.filename.toLowerCase().includes(key))
    }
  },
  watch: {
    '$route.params.id': {
      immediate: true,
      handler() {
        this.resetPagination()
        this.loadDatasetBase()
      }
    }
  },
  methods: {
    getBoxColor,
    fullUrl(path) {
      if (!path) return ''
      if (path.startsWith('http')) return path
      return global.BASEURL.replace(/\/$/, '') + path
    },
    formatTime(iso) {
      if (!iso) return '—'
      return iso.replace('T', ' ').slice(0, 16)
    },
    categoryLabel(classId) {
      const group = getCategoryGroup(classId)
      return CATEGORY_GROUPS[group]?.label || '未知'
    },

    // 重置分页状态（切换数据集时调用）
    resetPagination() {
      this.imageList = []
      this.page = 1
      this.hasMore = true
      this.loading = false
      this.selectedImage = null
    },

    // 只加载数据集基础信息，不带图片
    async loadDatasetBase() {
      try {
        const res = await getDataset(this.$route.params.id, { page: 0, limit: 0 })
        const { images, ...baseInfo } = res.data.data
        this.dataset = baseInfo
        await this.loadImagePage()
      } catch {
        this.$router.replace('/dataset-management')
      }
    },

    // 加载图片分页
    async loadImagePage() {
      if (this.loading || !this.hasMore) return
      this.loading = true
      try {
        const res = await getDataset(this.$route.params.id, {
          page: this.page,
          limit: this.pageSize
        })
        const data = res.data.data
        const newImgs = data.images || []

        if (this.page === 1) {
          this.imageList = newImgs
          if (newImgs.length > 0) {
            this.selectedImage = newImgs[0]
            this.$nextTick(() => this.renderSelected())
          }
        } else {
          this.imageList.push(...newImgs)
        }

        const total = data.pagination?.total || 0
        this.hasMore = this.imageList.length < total
        this.page += 1
      } catch (err) {
        console.error('分页加载图片失败：', err)
      } finally {
        this.loading = false
      }
    },

    // 左侧滚动到底部触发加载
    onImageScroll(e) {
      const dom = e.target
      const reachBottom = dom.scrollTop + dom.clientHeight >= dom.scrollHeight - 80
      if (reachBottom) {
        this.loadImagePage()
      }
    },

    selectImage(img) {
      this.selectedImage = img
      this.$nextTick(() => this.renderSelected())
    },
    renderSelected() {
      if (!this.selectedImage) return
      const canvas = this.$refs.viewerCanvas
      if (!canvas) return
      const img = new Image()
      img.crossOrigin = 'anonymous'
      img.onload = () => {
        drawAnnotations(canvas, img, this.selectedImage.annotations || [])
      }
      img.src = this.fullUrl(this.selectedImage.url)
    },
    doExport() {
      window.open(exportDatasetUrl(this.dataset.id), '_blank')
    }
  }
}
</script>

<style scoped>
.detail-page {
  min-height: calc(100vh - 60px);
  padding: 30px 38px;
  background: #f7f9fc;
  color: #192234;
  font-family: "Microsoft YaHei", sans-serif;
  box-sizing: border-box;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  max-width: 1180px;
  margin: 0 auto 22px;
}
.back {
  color: #498ee6;
  font-size: 12px;
  cursor: pointer;
  margin-bottom: 6px;
}
.page-header h1 { margin: 0 0 8px; font-size: 28px; }
.meta { margin: 0; color: #7f899b; font-size: 13px; }
.dark-button {
  padding: 12px 18px;
  border: 0;
  border-radius: 10px;
  background: #151515;
  color: #fff;
  font-weight: 700;
  cursor: pointer;
}

.workspace {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 18px;
  max-width: 1180px;
  margin: 0 auto;
}
.image-panel,
.viewer-panel {
  border: 1px solid #e3e8ef;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 4px 16px rgba(31, 45, 70, .04);
}
.image-panel {
  padding: 14px;
  align-self: start;
  max-height: calc(100vh - 180px);
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.image-list {
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}
.image-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  border: 1px solid #e8edf3;
  border-radius: 10px;
  background: #fafbfd;
  cursor: pointer;
  text-align: left;
}
.image-item:hover,
.image-item.active {
  border-color: #409eff;
  background: #f0f7ff;
}
.image-item img {
  width: 56px;
  height: 56px;
  object-fit: cover;
  border-radius: 6px;
  flex-shrink: 0;
}
.item-info { min-width: 0; }
.item-info strong {
  display: block;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.item-info small { color: #8c96a7; font-size: 11px; }

.viewer-panel { padding: 18px; }
.viewer-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
  font-size: 13px;
  color: #6b7a8d;
}
.viewer-toolbar strong { color: #192234; font-size: 15px; }
.split-tag {
  padding: 2px 8px;
  border-radius: 999px;
  background: #eef5ff;
  color: #409eff;
  font-size: 12px;
}
.canvas-wrap {
  border: 1px solid #edf0f5;
  border-radius: 10px;
  background: #f2f6fb;
  overflow: auto;
  max-height: 62vh;
}
.viewer-canvas {
  display: block;
  max-width: 100%;
  height: auto;
}

.annotation-table {
  margin-top: 16px;
  border: 1px solid #edf0f5;
  border-radius: 10px;
  overflow: hidden;
}
.table-head {
  padding: 10px 14px;
  background: #f8fafc;
  font-size: 13px;
  font-weight: 700;
}
.ann-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 16px;
  padding: 8px 14px;
  border-top: 1px solid #edf0f5;
  font-size: 12px;
  color: #5a6478;
}
.ann-row i {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.warnings {
  margin-top: 12px;
  padding: 10px 14px;
  border-radius: 8px;
  background: #fff7e6;
  color: #b88230;
  font-size: 12px;
}

.empty-state {
  max-width: 1180px;
  margin: 0 auto;
  padding: 48px;
  text-align: center;
  color: #9aa3b1;
  background: #fff;
  border-radius: 14px;
  border: 1px solid #e3e8ef;
}

.load-tip {
  padding: 12px 0;
  text-align: center;
  font-size: 12px;
  color: #888;
}

@media (max-width: 900px) {
  .detail-page { padding: 20px 16px; }
  .page-header { flex-direction: column; align-items: flex-start; gap: 14px; }
  .workspace { grid-template-columns: 1fr; }
  .image-panel { max-height: 280px; }
}
</style>