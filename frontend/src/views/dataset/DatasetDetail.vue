<template>
  <main v-if="dataset" class="detail-page">
    <header class="page-header">
      <div>
        <div class="title-row">
          <h1 v-if="!editName">{{ dataset.name }}</h1>
          <el-input
              v-else
              v-model="dataset.name"
              size="large"
              @blur="saveDatasetInfo"
              @keyup.enter="saveDatasetInfo"
          />
          <button class="edit-btn" @click="editName = !editName">
            {{ editName ? '保存' : '编辑' }}
          </button>
        </div>
        <p class="meta">
          {{ dataset.image_count }} 张影像 · {{ dataset.box_count }} 个标注框 ·
          {{ dataset.class_count }} 类 · 更新于 {{ formatTime(dataset.updated_at) }}
        </p>
        <!-- 数据集简介【重构区域】 -->
        <div class="desc-row">
          <!-- 常态展示区域 -->
          <div
              v-if="!editDesc"
              class="desc-view"
              @click="editDesc = true"
          >
            <span v-if="dataset.description" class="desc-text">{{ dataset.description }}</span>
            <span v-else class="desc-placeholder">添加数据集简介</span>
            <!--            <span class="edit-pencil">✏</span>-->
          </div>
          <!-- 编辑输入框 -->
          <el-input
              v-else
              v-model="dataset.description"
              type="textarea"
              :rows="2"
              placeholder="添加数据集简介"
              clearable
              @blur="saveDesc"
              @keyup.enter="saveDesc"
              ref="descInputRef"
          />
        </div>
      </div>
      <button class="dark-button" @click="doExport">导出 YOLO</button>
    </header>

    <!-- Tab 标签导航 -->
    <div class="tab-nav">
      <button
          v-for="tab in tabList"
          :key="tab.value"
          class="tab-item"
          :class="{ active: activeTab === tab.value }"
          @click="activeTab = tab.value"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- ========== Images 标签页（原有图片分页模块） ========== -->
    <div v-if="activeTab === 'images'" class="tab-content">
      <!-- 顶部工具栏（参考Ultralytics） -->
      <div class="toolbar">
        <el-input v-model="keyword" clearable placeholder="搜索文件名…" class="search-input" @input="onSearchChange"/>

        <div class="toolbar-right">
          <!-- 显隐控制按钮 -->
          <div class="dropdown-wrap">
            <button class="tool-btn" @click="visiblePopover = !visiblePopover">
              <span>👁</span>
            </button>
            <div v-if="visiblePopover" class="dropdown-menu visible-menu">
              <div class="menu-title">Visibility</div>
              <label class="menu-item">
                <input type="checkbox" v-model="showAnnotations"> Annotations
              </label>
              <label class="menu-item">
                <input type="checkbox" v-model="showClassLabel"> Class labels
              </label>
            </div>
          </div>

          <!-- 视图模式切换 -->
          <div class="view-switch">
            <button
                v-for="mode in viewModeList"
                :key="mode.value"
                class="tool-btn"
                :class="{ active: viewMode === mode.value }"
                @click="viewMode = mode.value"
                :title="mode.label"
            >
              {{ mode.icon }}
            </button>
          </div>
        </div>
      </div>

      <!-- 图片主区域 -->
      <div class="image-container">
        <!-- Grid 网格视图 -->
        <div v-if="viewMode === 'grid'" class="grid-view">
          <div
              v-for="img in pageImages"
              :key="img.id"
              class="grid-card"
              :class="{ active: selectedImage?.id === img.id }"
              @click="openImageViewer(img)"
              @mouseenter="hoverGridImgId = img.id"
              @mouseleave="hoverGridImgId = null"
          >
            <div class="preview-box">
              <canvas
                  ref="gridCanvas"
                  class="grid-canvas"
                  :data-img-id="img.id"
              ></canvas>
              <!-- hover浮现操作按钮 -->
              <div v-if="hoverGridImgId === img.id" class="grid-card-actions" @click.stop>
                <!-- 下载按钮，width和height从20改成18，缩小尺寸 -->
                <button class="action-btn" @click="downloadSingleImage(img)" title="下载图片">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                       stroke-linecap="round" stroke-linejoin="round">
                    <path d="M12 5v9"></path>
                    <path d="M9 11l3 3 3-3"></path>
                    <path d="M3 15v4a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-4"></path>
                  </svg>
                </button>
                <!-- 删除按钮同步修改 -->
                <button class="action-btn danger" @click="deleteSingleImage(img)" title="删除图片">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                       stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2"></path>
                    <line x1="10" y1="11" x2="10" y2="17"></line>
                    <line x1="14" y1="11" x2="14" y2="17"></line>
                  </svg>
                </button>
              </div>
            </div>
            <div class="card-footer">
              <div class="filename">{{ img.filename }}</div>
              <div class="info-text">
                {{ img.width }}×{{ img.height }}
                <template v-if="img.split && img.split !== 'unset'">
                  · {{ getSplitName(img.split) }}
                </template>
                · {{ img.box_count }} annotations
              </div>
            </div>
          </div>
        </div>

        <!-- Compact 紧凑列表 -->
        <div v-if="viewMode === 'compact'" class="compact-view">
          <div
              v-for="img in pageImages"
              :key="img.id"
              class="compact-item"
              :class="{ active: selectedImage?.id === img.id }"
              @click="openImageViewer(img)"
          >
            <div class="thumb-wrap">
              <canvas class="compact-canvas" :data-img-id="img.id"></canvas>
            </div>
            <div class="compact-text">
              <div class="filename">{{ img.filename }}</div>
              <div class="info-text">
                {{ img.box_count }} 标注框
                <template v-if="img.split && img.split !== 'unset'">
                  · {{ img.split === 'train' ? '训练集' : '验证集' }}
                </template>
              </div>
            </div>
          </div>
        </div>

        <!-- Table 表格视图 -->
        <div v-if="viewMode === 'table'" class="table-view">
          <!-- 新增横向滚动容器 -->
          <div class="table-scroll-wrap">
            <table>
              <thead>
              <tr>
                <!--              <th style="width:80px">Preview</th>-->
                <th style="width:80px">预览</th>
                <th>
                  <button class="table-sort-btn" @click="sortTable('filename')">
                    名称
                    <span>{{ getSortArrow('filename') }}</span>
                  </button>
                </th>
                <th>
                  <button class="table-sort-btn" @click="sortTable('height')">
                    高
                    <span>{{ getSortArrow('height') }}</span>
                  </button>
                </th>
                <th>
                  <button class="table-sort-btn" @click="sortTable('width')">
                    宽
                    <span>{{ getSortArrow('width') }}</span>
                  </button>
                </th>
                <th>
                  <button class="table-sort-btn" @click="sortTable('size')">
                    大小
                    <span>{{ getSortArrow('size') }}</span>
                  </button>
                </th>
                <th>划分</th>
                <th>
                  <button class="table-sort-btn" @click="sortTable('box_count')">
                    标注数
                    <span>{{ getSortArrow('box_count') }}</span>
                  </button>
                </th>
                <th style="min-width: 240px;">类别</th>
              </tr>
              </thead>
              <tbody>
              <tr
                  v-for="img in sortedTableImages"
                  :key="img.id"
                  :class="{ active: selectedImage?.id === img.id }"
                  @click="openImageViewer(img)"
              >
                <td>
                  <div class="table-thumb">
                    <canvas class="table-canvas" :data-img-id="img.id"></canvas>
                  </div>
                </td>
                <td>{{ img.filename }}</td>
                <td>{{ img.height != null ? img.height : '-' }}</td>
                <td>{{ img.width != null ? img.width : '-' }}</td>
                <td>{{ img.size != null ? formatFileSize(img.size) : '-' }}</td>
                <td>
                  <!-- 【修复】class绑定在外层split-row -->
                  <span class="split-row" :class="splitClass(img.split)">
        <span class="split-dot"></span>
        <span class="split-text">{{ getSplitName(img.split) }}</span>
      </span>
                </td>
                <td>{{ img.box_count }}</td>
                <td>
      <span class="classes-cell">
        <span
            v-for="cls in img.class_list"
            :key="cls.class_id"
            class="class-tag"
        >
        <span class="color-dot-small" :style="{background:getClassColor(cls.class_id)}"></span>
        {{ classNameCnMap[cls.class_id] || cls.name }}<sup>{{ cls.count }}</sup>
        </span>
      </span>
                  <span v-if="!img.class_list || img.class_list.length === 0">-</span>
                </td>
              </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div v-if="loading" class="load-tip">加载中……</div>
        <div v-if="pageImages.length === 0 && !loading" class="empty-tip">暂无影像数据</div>
      </div>

      <!-- ========== 新增底部分页控件 ========== -->
      <div class="pagination-bar" v-if="total > 0">
        <span class="page-info">共 {{ total }} 条</span>
        <button class="page-btn" :disabled="currentPage <=1" @click="changePage(currentPage -1)">上一页</button>

        <span class="page-jump-wrap">
    第
    <input
        class="page-input"
        v-model.number="jumpPageNum"
        @keyup.enter="handleJumpPage"
    />
    / {{ maxPage }} 页
  </span>

        <button class="page-btn" :disabled="currentPage >= maxPage" @click="changePage(currentPage +1)">下一页</button>
      </div>

      <!-- ✅【新增拖拽上传区域】放在分页下面 -->
      <div
          class="drop-upload-area"
          @click="triggerFileSelect"
          @dragover.prevent="onDragOver"
          @dragleave="onDragLeave"
          @drop.prevent="onFileDrop"
          :class="{drag_active: dragHover}"
      >
        <div class="upload-icon">
          <!-- 上下箭头上传图标，可以替换为svg -->
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#999" stroke-width="1.5">
            <path d="M12 16V8"></path>
            <path d="M9 11l3-3 3 3"></path>
            <path d="M3 15v4a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-4"></path>
          </svg>
        </div>
        <h3 class="upload-title">All {{ dataset.image_count }} images loaded</h3>
        <p class="upload-desc">Drag and drop more images here to expand your dataset.</p>
        <input
            ref="fileInputRef"
            type="file"
            multiple
            accept=".jpg,.jpeg,.png,.tif,.tiff,.zip,.txt"
            style="display:none"
            @change="onFileSelect"
        />
      </div>
    </div>


    <!-- ========== Classes 标签页【改造完成】 ========== -->
    <div v-if="activeTab === 'classes'" class="tab-content">
      <div class="chart-card">
        <div class="chart-header-row">
          <!--          <h3>Class Distribution</h3>-->
          <h3>类别分布</h3>
          <span class="chart-subtitle">{{ classList.length }} classes · {{
              totalAnnotationCount
            }} total annotations</span>
        </div>
        <div class="chart-box" ref="classChartWrap"></div>
      </div>

      <div class="class-table-wrap">
        <div class="table-head-row">
          <!--          <h3>Classes</h3>-->
          <h3>类别</h3>
        </div>
        <table class="class-table">
          <thead>
          <tr>
            <th style="width:110px">
              <!--              <span>Index</span>-->
              <span>索引</span>
              <button class="sort-btn" @click="sortByField('class_id')">
                {{ sortField === 'class_id' ? (sortAsc ? '↑' : '↓') : '⇅' }}
              </button>
            </th>
            <th>
              <!--              <span>Name</span>-->
              <span>名称</span>
              <button class="sort-btn" @click="sortByField('name')">
                {{ sortField === 'name' ? (sortAsc ? '↑' : '↓') : '⇅' }}
              </button>
            </th>
            <th style="width:160px">
              <!--              <span>Annotations</span>-->
              <span>标注数量</span>
              <button class="sort-btn" @click="sortByField('annotation_count')">
                {{ sortField === 'annotation_count' ? (sortAsc ? '↑' : '↓') : '⇅' }}
              </button>
            </th>
            <!--            <th style="width:140px">Images</th>-->
            <th style="width:140px">影像数</th>
          </tr>
          </thead>
          <tbody>
          <tr v-if="classList.length === 0">
            <td colspan="4" class="empty-row">等待后端接口返回类别数据</td>
          </tr>
          <tr v-for="c in sortedClassList" :key="c.class_id">
            <td>
              <span class="color-dot" :style="{background:getClassColor(c.class_id)}"></span>
              {{ c.class_id }}
            </td>
            <td>{{ classNameCnMap[c.class_id] || c.name }}</td>
            <td>{{ c.annotation_count }}</td>
            <td>{{ c.image_count || 0 }}</td>
          </tr>
          </tbody>
          <!-- 新增类别固定放在表格底部 -->
          <tfoot>
          <tr>
            <td colspan="4" style="padding:12px 14px;">
              <div style="display:flex; gap:12px; align-items:center;">
                <el-input
                    v-model="newClassName"
                    placeholder="Add new class..."
                    clearable
                    style="flex:1;"
                    @keyup.enter="addClass"
                ></el-input>
                <el-button type="primary" @click="addClass">+ Add</el-button>
              </div>
            </td>
          </tr>
          </tfoot>
        </table>
      </div>
    </div>

    <!-- ========== Charts 标签页 ========== -->
    <div v-if="activeTab === 'charts'" class="tab-content">
      <div class="chart-grid">
        <div class="chart-card">
          <h3>划分分布 Train / Val</h3>
          <div class="chart-box" ref="splitChartWrap">划分饼图</div>
        </div>
        <div class="chart-card">
          <h3>高频类别</h3>
          <div class="chart-box" ref="topClassChartWrap">Top类别饼图</div>
        </div>
        <div class="chart-card">
          <h3>图片尺寸分布</h3>
          <div class="chart-box" ref="sizeChartWrap">宽高分布图</div>
        </div>
        <div class="chart-card">
          <h3>单图标注数量分布</h3>
          <div class="chart-box" ref="objPerImgChartWrap">单图标注柱状图</div>
        </div>
      </div>
    </div>

    <!-- 大图查看弹窗【标注明细展示真实类别名称】 -->
    <div v-if="selectedImage" class="image-modal" @click.self="closeViewer" @wheel.prevent="onCanvasWheel">
      <div class="modal-inner">
        <div class="modal-header">
          <strong>{{ selectedImage.filename }}</strong>
          <span>{{ selectedImage.box_count }} 个标注框</span>
          <span v-if="selectedImage.split && selectedImage.split !== 'unset'" class="split-tag">
            {{ getSplitName(selectedImage.split) }}
          </span>
          <span style="margin-left:auto;font-size:12px;color:#888;">缩放: {{ canvasScale.toFixed(2) }}x</span>
          <button class="close-btn" @click="closeViewer">✕</button>
        </div>
        <div class="modal-canvas-wrap" ref="canvasWrapRef" @mousedown="onCanvasMouseDown" @mousemove="onCanvasMouseMove"
             @mouseup="onCanvasMouseUp" @mouseleave="onCanvasMouseUp">
          <canvas ref="viewerCanvas" class="viewer-canvas"
                  :style="{transform:`scale(${canvasScale}) translate(${canvasOffset.x}px,${canvasOffset.y}px)`}"/>
        </div>
        <!-- 底部切换栏 -->
        <div class="viewer-bottom-bar">
          <button class="switch-btn" :disabled="!hasPrevImage" @click="switchPrevImage">← 上一张</button>
          <span class="page-indicator">{{ currentImgIndex }} / {{ totalImgCount }}</span>
          <button class="switch-btn" :disabled="!hasNextImage" @click="switchNextImage">下一张 →</button>
        </div>
        <div v-if="selectedImage.annotations?.length" class="annotation-table">
          <div class="table-head">标注明细</div>
          <div
              v-for="(ann, idx) in selectedImage.annotations"
              :key="idx"
              class="ann-row"
              :class="{active: highlightAnnIndex === idx}"
              @click="setHighlightAnn(idx)"
          >
            <i :style="{ background: getBoxColor(ann.class_id) }"/>
            <span>类别 #{{ ann.class_id }}</span>
            <span>{{ classNameCnMap[ann.class_id] || classNameMap[ann.class_id] || '未知类别' }}</span>
            <span>{{ categoryLabel(ann.class_id) }}</span>
            <span>x={{ ann.x.toFixed(4) }} y={{ ann.y.toFixed(4) }}</span>
            <span>w={{ ann.w.toFixed(4) }} h={{ ann.h.toFixed(4) }}</span>
          </div>
        </div>
        <div v-if="selectedImage.warnings?.length" class="warnings">
          <div v-for="(w, i) in selectedImage.warnings" :key="i">{{ w }}</div>
        </div>
      </div>
    </div>
    <!-- ========== 新增页脚 ========== -->
    <footer class="page-footer">
      <div class="back" @click="$router.push('/dataset-management')">← 返回数据集列表</div>
      <span class="footer-tip">GeoView · 遥感数据集管理</span>
    </footer>
  </main>

</template>

<script>
import {
  getClassBarOption,
  getSplitPieOption,
  getTopClassPieOption,
  getObjPerImageBarOption,
  getImageSizeBarOption,
  disposeChart
} from './datasetChartHelper'
import * as echarts from 'echarts'
import {getDataset, exportDatasetUrl} from '@/api/dataset'
import {drawAnnotations} from '@/utils/annotationDrawer'
import {CATEGORY_GROUPS, getBoxColor, getCategoryGroup} from '@/utils/datasetConstants'
import global from '@/global'
import axios from 'axios'

export default {
  name: 'DatasetDetail',
  data() {
    return {
      // ====== 新增中文映射 ======
      classNameCnMap: {
        0: "航母",
        1: "两栖舰",
        2: "驱护舰",
        3: "民船",
        4: "SU-35",
        5: "C-130",
        6: "C-17",
        7: "C-5",
        8: "F-16",
        9: "TU-160",
        10: "E-3",
        11: "B-52",
        12: "P-3C",
        13: "B-1B",
        14: "E-8",
        15: "TU-22",
        16: "F-15",
        17: "KC-135",
        18: "F-22",
        19: "FA-18",
        20: "TU-95",
        21: "KC-10",
        22: "SU-34",
        23: "SU-24",
        24: "发射车"
      },
      // ====== 新增结束 ======
      dataset: null,
      keyword: '',
      selectedImage: null,
      editName: false,
      // 简介编辑开关【新增】
      editDesc: false,

      // Tab 配置
      activeTab: 'images',
      tabList: [
        {label: '影像', value: 'images'},
        {label: '类别', value: 'classes'},
        {label: '图表', value: 'charts'}
      ],

      // 视图控制
      viewMode: 'grid',
      viewModeList: [
        {icon: '▦', value: 'grid', label: '网格视图'},
        {icon: '☰', value: 'compact', label: '紧凑列表'},
        {icon: '▤', value: 'table', label: '表格视图'}
      ],
      visiblePopover: false,
      showAnnotations: true,
      showClassLabel: true,

      // 传统分页配置
      pageSize: 20,
      currentPage: 1,
      total: 0,
      maxPage: 1,
      jumpPageNum: 1,
      loading: false,
      _pageData: [],

      // Classes页面
      newClassName: '',
      classList: [],
      totalAnnotationCount: 0,

      // 类别名称映射（弹窗使用）
      classNameMap: {},
      // 类别颜色缓存
      classColorMap: {},
      // 排序配置
      sortField: 'annotation_count',
      sortAsc: false,

      // 图表相关变量
      datasetStats: {},
      chartLoading: false, // 新增
      charts: {
        classBar: null,
        splitPie: null,
        topClassPie: null,
        imageSizeBar: null,
        objPerImgBar: null
      },

      // table 排序
      tableSortField: 'filename',
      tableSortAsc: true,

      // 拖拽上传区域新增变量
      dragHover: false,
      uploadLoading: false,

      /* 卡片悬浮效果相关（？ */
      hoverGridImgId: null,

      /* 大图缩放、平移 */
      canvasScale: 1,
      canvasOffset: {x: 0, y: 0},
      isDragging: false,
      dragStart: {x: 0, y: 0},
      /* 高亮选中标注下标 */
      highlightAnnIndex: -1,
      /* 弹窗图片分页索引 */
      currentImgIndex: 0,
      totalImgCount: 0,
    }
  },

  computed: {
    // 删除原来的 pageImages(){}
    pageImages() {
      // 直接使用后端返回的全部当前分页数据，不再前端过滤
      return this._pageData
    },
    sortedClassList() {
      const arr = [...this.classList]
      arr.sort((a, b) => {
        let valA = a[this.sortField]
        let valB = b[this.sortField]
        if (typeof valA === 'string') {
          valA = valA.toLowerCase()
          valB = valB.toLowerCase()
          if (valA > valB) return this.sortAsc ? 1 : -1
          if (valA < valB) return this.sortAsc ? -1 : 1
          return 0
        }
        return this.sortAsc ? valA - valB : valB - valA
      })
      return arr
    },

    sortedTableImages() {
      const list = [...this.pageImages]
      list.sort((a, b) => {
        let va = a[this.tableSortField]
        let vb = b[this.tableSortField]

        // 字符串文件名
        if (this.tableSortField === 'filename') {
          va = va?.toLowerCase() || ''
          vb = vb?.toLowerCase() || ''
          if (va > vb) return this.tableSortAsc ? 1 : -1
          if (va < vb) return this.tableSortAsc ? -1 : 1
          return 0
        }
        // 数字高度/宽度/标注数
        if (['height', 'width', 'box_count'].includes(this.tableSortField)) {
          va = Number(va || 0)
          vb = Number(vb || 0)
          return this.tableSortAsc ? va - vb : vb - va
        }
        // 文件大小 bytes
        if (this.tableSortField === 'size') {
          va = Number(va || 0)
          vb = Number(vb || 0)
          return this.tableSortAsc ? va - vb : vb - va
        }
        return 0
      })
      return list
    },

    /* 上下张切换计算属性 */
    hasPrevImage() {
      return this.currentImgIndex > 0
    },
    hasNextImage() {
      return this.currentImgIndex < this.totalImgCount - 1
    },
  },

  watch: {
    '$route.params.id': {
      immediate: true,
      handler() {
        this.resetPage()
        this.loadDatasetBase()
      }
    },
    async activeTab(newTab) {
      this.selectedImage = null
      // 离开charts标签，销毁实例
      if (this.activeTab === 'charts' && newTab !== 'charts') {
        this.destroyAllCharts()
      }

      if (newTab === 'images') {
        this.loadImagePage()
      }
      if (newTab === 'classes') {
        await this.loadClassData()
        this.$nextTick(() => {
          this.renderClassDistributionChart()
        })
      }
      if (newTab === 'charts') {
        await this.$nextTick()
        // 新增：没有类别数据就加载
        if (!this.classList.length) {
          await this.loadClassData()
        }
        await this.loadChartStatistics()
        this.destroyAllCharts()
        this.$nextTick(async () => {
          this.renderAllCharts()
          setTimeout(() => {
            Object.values(this.charts).forEach(ins => {
              if (ins) ins.resize()
            })
          }, 60)
        })
      }
    },
    // 下方所有watch保留不动
    editDesc(newVal) {
      if (newVal) {
        this.$nextTick(() => {
          this.$refs.descInputRef.focus()
        })
      }
    },
    showAnnotations() {
      this.$nextTick(() => this.redrawAllThumb())
    },
    showClassLabel() {
      this.$nextTick(() => this.redrawAllThumb())
    },
    viewMode() {
      this.$nextTick(() => this.redrawAllThumb())
    },
    currentPage(newVal) {
      this.jumpPageNum = newVal
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
    getSplitName(split) {
      if (split === 'train') return 'Train'
      if (split === 'val') return 'Val'
      if (split === 'test') return 'Test'
      return 'Unset'
    },
    handleDocumentClick(e) {
      if (!e.target.closest('.dropdown-wrap')) {
        this.visiblePopover = false
      }
    },
    onSearchChange() {
      this.currentPage = 1
      this.loadImagePage()
    },

    // 获取类别固定颜色
    getClassColor(classId) {
      if (this.classColorMap[classId]) {
        return this.classColorMap[classId]
      }
      const hue = (classId * 47) % 360
      const color = `hsl(${hue}, 70%, 55%)`
      this.classColorMap[classId] = color
      return color
    },

    // 切换排序字段
    sortByField(field) {
      if (this.sortField === field) {
        this.sortAsc = !this.sortAsc
      } else {
        this.sortField = field
        this.sortAsc = true
      }
    },

    // 加载类别名称映射（弹窗使用）
    async loadDatasetClassMap(datasetId) {
      try {
        const url = `${global.BASEURL}/api/dataset/${datasetId}/classes`
        const res = await axios.get(url)
        const map = {}
        res.data.data.forEach(item => {
          map[item.class_id] = item.name
        })
        this.classNameMap = map
      } catch (err) {
        console.warn("加载类别名称映射失败", err)
        this.classNameMap = {}
      }
    },

    // 保存数据集名称、简介
    async saveDatasetInfo() {
      console.log('保存数据集信息', this.dataset.name, this.dataset.description)
      this.editName = false
    },
    // 保存简介专用方法【新增】
    saveDesc() {
      this.editDesc = false
      this.saveDatasetInfo()
    },

    resetPage() {
      this.currentPage = 1
      this.total = 0
      this.maxPage = 1
      this.jumpPageNum = 1
      this.selectedImage = null
      this._pageData = []
      this.classNameMap = {}
      this.classColorMap = {}
      this.classList = []
      this.totalAnnotationCount = 0
      this.editDesc = false
    },

    // 只加载数据集基础信息
    async loadDatasetBase() {
      try {
        const res = await getDataset(this.$route.params.id, {page: 0, limit: 0})
        const {images, ...baseInfo} = res.data.data
        this.dataset = baseInfo
        if (!this.dataset.description) this.dataset.description = ''
        await this.loadDatasetClassMap(this.dataset.id)
        await this.loadImagePage()
      } catch {
        this.$router.replace('/dataset-management')
      }
    },

    async loadImagePage() {
      if (this.loading) return
      this.loading = true
      this._pageData = []
      try {
        const res = await getDataset(this.$route.params.id, {
          page: this.currentPage,
          limit: this.pageSize,
          keyword: this.keyword.trim()
        })
        const data = res.data.data
        this._pageData = data.images || []
        this.total = data.pagination?.total || 0
        this.maxPage = Math.ceil(this.total / this.pageSize) || 1
      } catch (err) {
        console.error('分页加载图片失败：', err)
      } finally {
        this.loading = false
        this.$nextTick(() => this.redrawAllThumb())
      }
    },

    changePage(page) {
      if (page < 1 || page > this.maxPage || page === this.currentPage) return
      this.selectedImage = null
      this.currentPage = page
      this.loadImagePage()
    },

    handleJumpPage() {
      let num = Number(this.jumpPageNum)
      if (isNaN(num)) num = this.currentPage
      num = Math.max(1, Math.min(num, this.maxPage))
      this.jumpPageNum = num
      this.changePage(num)
    },

    openImageViewer(img) {
      // 重置缩放、高亮状态
      this.canvasScale = 1
      this.canvasOffset = {x: 0, y: 0}
      this.highlightAnnIndex = -1

      this.selectedImage = img
      // 计算当前图片在列表中的序号
      this.currentImgIndex = this.pageImages.findIndex(p => p.id === img.id)
      this.totalImgCount = this.pageImages.length

      this.$nextTick(() => this.renderSelectedBig())
    },
    closeViewer() {
      this.selectedImage = null
      this.canvasScale = 1
      this.canvasOffset = {x: 0, y: 0}
      this.highlightAnnIndex = -1
    },
    /* 滚轮缩放 */
    onCanvasWheel(e) {
      const scaleStep = 0.12
      const minScale = 0.4
      const maxScale = 3.5
      if (e.deltaY < 0) {
        this.canvasScale = Math.min(this.canvasScale + scaleStep, maxScale)
      } else {
        this.canvasScale = Math.max(this.canvasScale - scaleStep, minScale)
      }
    },
    /* 画布拖拽平移（配套缩放体验） */
    onCanvasMouseDown(e) {
      this.isDragging = true
      this.dragStart.x = e.clientX - this.canvasOffset.x
      this.dragStart.y = e.clientY - this.canvasOffset.y
    },
    onCanvasMouseMove(e) {
      if (!this.isDragging) return
      this.canvasOffset.x = e.clientX - this.dragStart.x
      this.canvasOffset.y = e.clientY - this.dragStart.y
    },
    onCanvasMouseUp() {
      this.isDragging = false
    },
    /* 标注明细点击高亮 */
    setHighlightAnn(idx) {
      if (this.highlightAnnIndex === idx) {
        this.highlightAnnIndex = -1
      } else {
        this.highlightAnnIndex = idx
      }
      this.$nextTick(() => this.renderSelectedBig())
    },

    /* 切换图片方法 */
    switchPrevImage() {
      if (!this.hasPrevImage) return
      const nextImg = this.pageImages[this.currentImgIndex - 1]
      this.openImageViewer(nextImg)
    },
    switchNextImage() {
      if (!this.hasNextImage) return
      const nextImg = this.pageImages[this.currentImgIndex + 1]
      this.openImageViewer(nextImg)
    },

    /* 改动：绘制时区分普通标注、高亮标注（高亮改为「边框加粗 + 框内半透明填充」） */
    renderSelectedBig() {
      if (!this.selectedImage) return
      const canvas = this.$refs.viewerCanvas
      if (!canvas) return
      const img = new Image()
      img.crossOrigin = 'anonymous'
      img.onload = () => {
        const ctx = canvas.getContext('2d')
        canvas.width = img.width
        canvas.height = img.height
        ctx.clearRect(0, 0, canvas.width, canvas.height)
        ctx.drawImage(img, 0, 0)

        const annos = this.selectedImage.annotations || []
        annos.forEach((ann, idx) => {
          const cx = ann.x * img.width
          const cy = ann.y * img.height
          const bw = ann.w * img.width
          const bh = ann.h * img.height
          const x = cx - bw / 2
          const y = cy - bh / 2

          // 判断是否为高亮条目
          const isHighlight = this.highlightAnnIndex === idx
          const baseColor = this.getBoxColor(ann.class_id)
          const className = this.classNameCnMap[ann.class_id] || this.classNameMap[ann.class_id] || 'unknown'

          // ========= 第一步：先绘制标签（置顶，防止被遮挡） =========
          const textH = 18
          ctx.fillStyle = baseColor
          ctx.fillRect(x, y - textH, ctx.measureText(className).width + 6, textH)
          ctx.fillStyle = '#ffffff'
          ctx.font = '13px sans-serif'
          ctx.fillText(className, x + 3, y - 4)

          // ========= 第二步：绘制标注框 + 高亮填充 =========
          ctx.strokeStyle = baseColor
          ctx.lineWidth = isHighlight ? 3 : 2
          ctx.strokeRect(x, y, bw, bh)

          // 高亮：增加半透明填充（33代表20%透明度）
          if (isHighlight) {
            ctx.fillStyle = baseColor + '33'
            ctx.fillRect(x, y, bw, bh)
          }
        })
      }
      img.src = this.fullUrl(this.selectedImage.url)
    },

    redrawAllThumb() {
      const canvasList = document.querySelectorAll('[data-img-id]')
      canvasList.forEach(canvas => {
        const imgId = canvas.getAttribute('data-img-id')
        const imgInfo = this._pageData.find(i => i.id === imgId)
        if (!imgInfo) return
        const image = new Image()
        image.crossOrigin = 'anonymous'
        image.onload = () => {
          const ctx = canvas.getContext('2d')
          canvas.width = canvas.offsetWidth
          canvas.height = canvas.offsetHeight
          ctx.clearRect(0, 0, canvas.width, canvas.height)
          const scale = Math.min(canvas.width / image.width, canvas.height / image.height)
          const w = image.width * scale
          const h = image.height * scale
          const x = (canvas.width - w) / 2
          const y = (canvas.height - h) / 2
          ctx.drawImage(image, x, y, w, h)
          drawAnnotations(canvas, image, imgInfo.annotations || [], {
            showBox: this.showAnnotations,
            showLabel: this.showClassLabel
          })
        }
        image.src = this.fullUrl(imgInfo.url)
      })
    },

    // 新增类别
    async addClass() {
      const name = this.newClassName.trim()
      if (!name) {
        this.$message.warning("类别名称不能为空")
        return
      }
      // 简单方案：取现有最大class_id +1
      const maxId = this.classList.reduce((max, item) => Math.max(max, item.class_id), -1)
      const newClassId = maxId + 1
      try {
        await axios.post(`/api/dataset/${this.dataset.id}/classes`, {
          class_id: newClassId,
          name: name
        })
        this.newClassName = ""
        // 重新刷新类别列表
        await this.loadClassData()
        // 如果当前在classes标签页，重新渲染图表
        if (this.activeTab === 'classes') {
          setTimeout(() => this.renderClassDistributionChart(), 100)
        }
      } catch (err) {
        console.error(err)
        this.$message.error("新增类别失败")
      }
    },

    doExport() {
      window.open(exportDatasetUrl(this.dataset.id), '_blank')
    },

    async loadClassData() {
      try {
        const url = `${global.BASEURL}/api/dataset/${this.dataset.id}/classes`
        const res = await axios.get(url)
        this.classList = res.data.data || []
        this.totalAnnotationCount = this.classList.reduce((sum, item) => sum + item.annotation_count, 0)
      } catch (e) {
        console.error('加载类别列表失败', e)
        this.classList = []
        this.totalAnnotationCount = 0
      }
    },

    renderClassDistributionChart() {
      const dom = this.$refs.classChartWrap
      if (!dom || !this.classList.length) {
        return
      }
      disposeChart(this.charts.classBar)
      const chartIns = echarts.init(dom)
      const option = getClassBarOption(this.classList)
      chartIns.setOption(option)
      this.charts.classBar = chartIns
      chartIns.resize()
    },

    renderAllCharts() {
      const taskList = [
        this.renderSplitPieChart.bind(this),
        this.renderTopClassPieChart.bind(this),
        this.renderImageSizeChart.bind(this),
        this.renderObjPerImageChart.bind(this)
      ]
      taskList.forEach(fn => {
        try {
          fn()
        } catch (e) {
          console.error('图表渲染异常', fn.name, e)
        }
      })
    },

    renderSplitPieChart() {
      const dom = this.$refs.splitChartWrap
      if (!dom) return
      disposeChart(this.charts.splitPie)
      const chartIns = echarts.init(dom)
      const {train = 0, val = 0} = this.datasetStats
      const option = getSplitPieOption(train, val)
      chartIns.setOption(option)
      this.charts.splitPie = chartIns
    },

    // 新增
    processTopClassData(classList, topN = 10) {
      // 按标注数量降序
      const sorted = [...classList].sort((a, b) => b.annotation_count - a.annotation_count)
      const topList = sorted.slice(0, topN)
      const restList = sorted.slice(topN)
      const otherCount = restList.reduce((sum, item) => sum + item.annotation_count, 0)

      const chartData = [...topList]
      if (otherCount > 0) {
        chartData.push({
          name: "Other",
          annotation_count: otherCount,
          class_id: -1 // 标记Other
        })
      }
      return chartData
    },

    // 替换后
    renderTopClassPieChart() {
      const dom = this.$refs.topClassChartWrap
      if (!dom) return
      disposeChart(this.charts.topClassPie)
      const chartIns = echarts.init(dom)

      // 使用预处理函数，取Top10，自动合并剩余为Other
      const pieData = this.processTopClassData(this.classList, 10)

      const option = getTopClassPieOption(pieData, this.classNameCnMap)
      chartIns.setOption(option)
      this.charts.topClassPie = chartIns
    },

    renderObjPerImageChart() {
      const dom = this.$refs.objPerImgChartWrap
      if (!dom) return
      disposeChart(this.charts.objPerImgBar)
      const chartIns = echarts.init(dom)
      const {object_count_list = []} = this.datasetStats
      const option = getObjPerImageBarOption(object_count_list)
      chartIns.setOption(option)
      this.charts.objPerImgBar = chartIns
    },

    renderImageSizeChart() {
      const dom = this.$refs.sizeChartWrap
      if (!dom) return
      disposeChart(this.charts.imageSizeBar)
      const chartIns = echarts.init(dom)
      const {width_list = [], height_list = []} = this.datasetStats
      const option = getImageSizeBarOption(width_list, height_list)
      chartIns.setOption(option)
      this.charts.imageSizeBar = chartIns
    },

    destroyAllCharts() {
      Object.values(this.charts).forEach(ins => {
        disposeChart(ins)
      })
    },

    // ========== 表格排序相关 ==========
    sortTable(field) {
      if (this.tableSortField === field) {
        this.tableSortAsc = !this.tableSortAsc
      } else {
        this.tableSortField = field
        this.tableSortAsc = true
      }
    },
    getSortArrow(field) {
      if (this.tableSortField !== field) return '⇅'
      return this.tableSortAsc ? '↑' : '↓'
    },
    // 文件大小格式化 bytes → KB
    formatFileSize(bytes) {
      if (!bytes) return '-'
      const kb = (bytes / 1024).toFixed(1)
      return `${kb} KB`
    },
    splitClass(split) {
      if (split === 'train') return 'split-train'
      if (split === 'val') return 'split-val'
      if (split === 'test') return 'split-test'
      return ''
    },

    // 拖拽悬浮
    onDragOver() {
      this.dragHover = true
    },
    onDragLeave() {
      this.dragHover = false
    },

    // 拖拽放下文件
    async onFileDrop(e) {
      this.dragHover = false
      const files = Array.from(e.dataTransfer.files)
      if (!files.length) return
      await this.uploadFiles(files)
    },

    // 点击区域触发隐藏input
    triggerFileSelect() {
      this.$refs.fileInputRef.click()
    },

    // 文件选择器选中
    async onFileSelect(e) {
      const files = Array.from(e.target.files)
      if (!files.length) return
      await this.uploadFiles(files)
      // 清空，防止重复选择同一个文件不触发change
      e.target.value = ""
    },

    // 核心：调用已有上传接口
    async uploadFiles(fileList) {
      if (this.uploadLoading) return
      this.uploadLoading = true
      try {
        const formData = new FormData()
        fileList.forEach(f => {
          formData.append("files", f)
        })
        const res = await this.$axios.post(`/api/dataset/${this.dataset.id}/upload`, formData, {
          headers: {
            "Content-Type": "multipart/form-data"
          }
        })
        this.$message.success("上传完成")
        // ✅上传完成刷新图片列表
        this.currentPage = 1
        this.loadImagePage()
      } catch (err) {
        console.error(err)
        this.$message.error("上传失败")
      } finally {
        this.uploadLoading = false
      }
    },

    // 单张图片下载
    async downloadSingleImage(img) {
      try {
        const url = this.fullUrl(img.url)
        // 请求图片转为blob
        const res = await fetch(url, {
          mode: 'cors',
          credentials: 'include'
        })
        const blob = await res.blob()
        const blobUrl = URL.createObjectURL(blob)

        const a = document.createElement('a')
        a.href = blobUrl
        a.download = img.filename
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)

        // 释放内存
        URL.revokeObjectURL(blobUrl)
        this.$message.success('开始下载')
      } catch (err) {
        console.error('下载失败', err)
        // 降级方案：打开图片页面，用户手动保存
        window.open(this.fullUrl(img.url), '_blank')
        this.$message.warning('自动下载失败，请在新页面右键图片另存')
      }
    },

    // 删除单张图片
    async deleteSingleImage(img) {
      try {
        await this.$confirm(`确认删除【${img.filename}】，图片及所有标注将会被清除！`, '警告', {type: 'warning'})
        // 用户点击确认，执行删除请求
        await this.$axios.delete(`/api/dataset/${this.dataset.id}/image/${img.filename}`)
        this.$message.success('删除成功')
        this.loadImagePage()
      } catch (e) {
        // ElementUI 的 confirm 取消会 reject，判断是否是用户取消
        if (e !== 'cancel') {
          this.$message.error('删除失败，请检查接口或权限')
          console.error('删除图片报错：', e)
        }
      }
    },

    // 加载图表统计数据（Train/Val、类别分布、尺寸分布）
    async loadChartStatistics() {
      if (this.chartLoading) return
      this.chartLoading = true
      try {
        const url = `${global.BASEURL}/api/dataset/${this.dataset.id}/chart-stat`
        const res = await axios.get(url)
        console.log("【图表原始数据】", res.data.data)
        const raw = res.data.data || {}

        // ✅ 字段映射：统一后端返回字段名为前端使用的字段名
        this.datasetStats = {
          ...raw,
          // 单图标注数量分布：box_distribution → object_count_list
          object_count_list: raw.box_distribution || [],
          // 图片尺寸分布：width_data/height_data → width_list/height_list
          width_list: raw.width_data || [],
          height_list: raw.height_data || [],
          // Top Classes 数据备份
          top_classes: raw.top_classes || []
        }

        console.log("【映射后数据】", this.datasetStats)
      } catch (err) {
        console.error("加载图表统计失败", err)
        this.datasetStats = {}
      } finally {
        this.chartLoading = false
      }
    },

    // methods底部
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
  align-items: flex-start;
  max-width: 1240px;
  margin: 0 auto 22px;
}

/*
.back {
  color: #498ee6;
  font-size: 12px;
  cursor: pointer;
}
*/

.title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-header h1 {
  margin: 0 0 8px;
  font-size: 28px;
}

.edit-btn {
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid #ddd;
  background: #fff;
  cursor: pointer;
}

.meta {
  margin: 0;
  color: #7f899b;
  font-size: 13px;
}

.desc-row {
  margin-top: 10px;
  max-width: 700px;
}

/* ========== 简介视图样式【新增】 ========== */
.desc-view {
  position: relative;
  padding: 0px;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.desc-view:hover {
  background-color: #efefef;
}

/* 正文简介文字样式 */
.desc-text {
  color: rgb(127, 137, 155);
  font-size: 16px;
  line-height: 1.6;
}

/* 空白占位文字 */
.desc-placeholder {
  color: #a1a8b3;
  font-size: 16px;
}

.edit-pencil {
  position: absolute;
  right: 12px;
  top: 6px;
  opacity: 0;
  transition: opacity 0.2s ease;
  font-size: 18px;
  color: #666;
}

.desc-view:hover .edit-pencil {
  opacity: 0.8;
}

/* ======================================= */
.dark-button {
  padding: 12px 18px;
  border: 0;
  border-radius: 10px;
  background: #151515;
  color: #fff;
  font-weight: 700;
  cursor: pointer;
}

/* Tab导航 */
.tab-nav {
  max-width: 1240px;
  margin: 0 auto 20px;
  display: flex;
  gap: 4px;
  border-bottom: 1px solid #e3e8ef;
}

.tab-item {
  padding: 10px 16px;
  border: none;
  background: transparent;
  font-size: 15px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
}

.tab-item.active {
  border-bottom-color: #409eff;
  color: #409eff;
  font-weight: bold;
}

.tab-content {
  max-width: 1240px;
  margin: 0 auto;
}

/* 顶部工具栏 */
.toolbar {
  max-width: 1240px;
  margin: 0 auto 16px;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.search-input {
  width: 320px;
}

.toolbar-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
}

.tool-btn {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  border: 1px solid #e3e8ef;
  background: #fff;
  cursor: pointer;
  font-size: 16px;
}

.tool-btn.active {
  background: #edf4ff;
  border-color: #409eff;
  color: #409eff;
}

/* 下拉菜单 */
.dropdown-wrap {
  position: relative;
}

.dropdown-menu {
  position: absolute;
  top: 42px;
  right: 0;
  width: 180px;
  padding: 10px;
  background: #fff;
  border: 1px solid #e3e8ef;
  border-radius: 10px;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);
  z-index: 100;
}

.menu-title {
  font-size: 13px;
  color: #888;
  padding-bottom: 6px;
  margin-bottom: 6px;
  border-bottom: 1px solid #f0f2f5;
}

.menu-item {
  display: block;
  padding: 6px 4px;
  font-size: 14px;
  cursor: pointer;
}

/* 图片区域 */
.image-container {
  max-width: 1240px;
  margin: 0 auto;
  min-height: 400px;
  padding-bottom: 20px;
}

/* Grid网格视图 */
.grid-view {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
}

.grid-card {
  position: relative;
  border: 1px solid #e3e8ef;
  border-radius: 12px;
  overflow: hidden;
  background: #fff;
  cursor: pointer;
  transition: 0.2s ease all;
}

.grid-card:hover {
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.12);
  border-color: #c0d8f5;
}

.grid-card.active {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
}

.preview-box {
  width: 100%;
  height: 160px;
  background: #f2f6fb;
  position: relative;
}

.grid-canvas {
  width: 100%;
  height: 100%;
  display: block;
}

/* hover浮现操作按钮 */
.grid-card-actions {
  position: absolute;
  top: 8px;
  right: 8px;
  display: flex;
  gap: 6px;
}

.action-btn {
  width: 30px;
  height: 30px;
  border-radius: 6px;
  background: #ffffffdd;
  border: none;
  cursor: pointer;
  font-size: 14px;
}

.action-btn:hover {
  background: #ffffff;
}

.action-btn.danger {
  color: #f56c6c;
}

.card-footer {
  padding: 10px;
}

.filename {
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.info-text {
  font-size: 12px;
  color: #888;
  margin-top: 4px;
}

/* Compact紧凑视图 */
.compact-view {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.compact-item {
  display: flex;
  gap: 12px;
  padding: 8px;
  border: 1px solid #e3e8ef;
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  align-items: center;
}

.compact-item.active {
  border-color: #409eff;
}

.thumb-wrap {
  width: 80px;
  height: 60px;
  flex-shrink: 0;
  background: #f2f6fb;
}

.compact-canvas {
  width: 100%;
  height: 100%;
  display: block;
}

.compact-text {
  min-width: 0;
}

/* Table表格视图 */
.table-view {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e3e8ef;
  //overflow: hidden;
}

/* 新增：横向滚动容器 */
.table-scroll-wrap {
  overflow-x: auto;
}

.table-scroll-wrap table {
  /* 关键：设置表格最小总宽度，小于这个宽度就出现滚动条 */
  min-width: 920px;
  width: 100%;
  border-collapse: collapse;
}

.table-view table {
  width: 100%;
  border-collapse: collapse;
}

.table-view th,
.table-view td {
  padding: 12px 14px;
  text-align: left;
  border-bottom: 1px solid #f0f2f5;
  font-size: 14px;
  vertical-align: middle; /* 新增：垂直居中，解决上下错位 */
  font-weight: normal; /* 新增：表头取消默认加粗 */
}

.table-view th {
  background: #f8fafc;
}

.table-view tbody tr {
  cursor: pointer;
}

.table-view tbody tr.active {
  background: #f0f7ff;
}

.table-thumb {
  width: 80px;
  height: 50px;
  background: #f2f6fb;
}

.table-canvas {
  width: 100%;
  height: 100%;
  display: block;
}

.load-tip, .empty-tip {
  padding: 40px 0;
  text-align: center;
  color: #999;
}

.table-sort-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 14px;
  color: inherit;
  padding: 0; /* 新增：清除按钮默认内边距，防止水平偏移 */
  margin: 0;
}

.table-sort-btn:hover {
  color: #409eff;
}

.classes-cell {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 6px 8px;
  align-items: center;
  vertical-align: middle;
}

.class-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
}

.color-dot-small {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.split-row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  vertical-align: middle;
}

.split-dot {
  width: 12px;
  height: 12px;
  border-radius: 9999px;
  flex-shrink: 0;
}

.split-text {
  font-size: 14px;
}

.split-train .split-dot {
  background-color: #22c55e;
}

.split-val .split-dot {
  background-color: #3b82f6;
}

.split-test .split-dot {
  background-color: #a855f7;
}

/* 分页栏 */
.pagination-bar {
  max-width: 1240px;
  margin: 0 auto;
  padding: 16px 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
}

.page-info {
  color: #666;
  font-size: 14px;
}

.page-btn {
  padding: 6px 14px;
  border: 1px solid #e3e8ef;
  background: #fff;
  border-radius: 6px;
  cursor: pointer;
}

.page-btn:disabled {
  color: #ccc;
  cursor: not-allowed;
}

.page-jump-wrap {
  font-size: 14px;
  color: #333;
  display: flex;
  align-items: center;
  gap: 6px;
}

.page-input {
  width: 56px;
  padding: 4px;
  border: 1px solid #ddd;
  border-radius: 4px;
  text-align: center;
}

/* Classes / Charts 页面样式 */
.chart-header-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
}

.chart-subtitle {
  color: #777;
  font-size: 13px;
}

.chart-card {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e3e8ef;
  padding: 16px;
  margin-bottom: 20px;
}

.chart-box {
  width: 100%;
  height: 320px;
  //display: flex;
  //align-items: center;
  //justify-content: center;
  color: #999;
}

.class-table-wrap {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e3e8ef;
  padding: 16px;
}

.table-head-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.class-table {
  width: 100%;
  border-collapse: collapse;
}

.class-table th, .class-table td {
  padding: 10px;
  text-align: left;
  border-bottom: 1px solid #eee;
}

.sort-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 14px;
  color: #666;
  padding: 0 4px;
}

.color-dot {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  margin-right: 8px;
  vertical-align: middle;
}

.class-table tfoot tr {
  border-top: 1px solid #eee;
}

.add-class-footer-row {
  padding: 12px 10px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.add-class-input {
  flex: 1;
  max-width: 420px;
}

.empty-row {
  text-align: center;
  color: #999;
  padding: 30px 0;
}

.chart-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

/* 大图弹窗 */
.image-modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
  padding: 24px;
  backdrop-filter: blur(2px);
}

.modal-inner {
  width: min(1160px, 100%);
  max-height: 92vh;
  background: #fff;
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.25);
}

.modal-header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 24px;
  border-bottom: 1px solid #f0f2f6;
  background-color: #fcfcfd;
}

.modal-header strong {
  font-size: 15px;
  color: #1d2129;
}

.modal-header > span {
  font-size: 13px;
  color: #6e7681;
}

.close-btn {
  margin-left: auto;
  border: none;
  background: #f2f3f5;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  font-size: 18px;
  cursor: pointer;
  color: #4e5969;
  transition: background 0.2s;
}

.close-btn:hover {
  background: #e5e6eb;
}

.modal-canvas-wrap {
  flex: 1;
  overflow: auto;
  background: #f7f8fa;
  padding: 20px;
  text-align: center;
}

.modal-canvas-wrap::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.modal-canvas-wrap::-webkit-scrollbar-thumb {
  background: #d0d3d9;
  border-radius: 3px;
}

.viewer-canvas {
  max-width: 100%;
  height: auto;
  display: inline-block;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.split-tag {
  padding: 3px 10px;
  border-radius: 999px;
  background: #e8f3ff;
  color: #2979e2;
  font-size: 12px;
  font-weight: 500;
}

.annotation-table {
  padding: 16px 24px;
  border-top: 1px solid #f0f2f6;
  max-height: 260px;
  overflow-y: auto;
  background: #fcfcfd;
}

.annotation-table::-webkit-scrollbar {
  width: 6px;
}

.annotation-table::-webkit-scrollbar-thumb {
  background: #d0d3d9;
  border-radius: 3px;
}

.table-head {
  padding-bottom: 12px;
  font-weight: 600;
  font-size: 14px;
  color: #1d2129;
}

.ann-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 18px;
  padding: 9px 10px;
  font-size: 13px;
  border-radius: 8px;
  transition: background 0.2s;
}

.ann-row:hover {
  background-color: #f2f3f5;
}

.ann-row i {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  flex-shrink: 0;
}

.warnings {
  margin: 0 24px 16px;
  padding: 12px 16px;
  border-radius: 10px;
  background: #fff7e6;
  color: #b88230;
  font-size: 13px;
}

@media (max-width: 900px) {
  .detail-page {
    padding: 20px 16px;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 14px;
  }

  .toolbar {
    flex-direction: column;
    align-items: flex-start;
  }

  .search-input {
    width: 100%;
  }

  .toolbar-right {
    margin-left: unset;
  }

  .grid-view {
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  }

  .pagination-bar {
    flex-wrap: wrap;
  }

  .chart-grid {
    grid-template-columns: 1fr;
  }
}

/* 底部切换栏 */
.viewer-bottom-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 20px;
  padding: 12px 24px;
  border-top: 1px solid #f0f2f6;
  background: #fcfcfd;
}

.switch-btn {
  padding: 6px 16px;
  border-radius: 8px;
  border: 1px solid #dcdfe6;
  background: #fff;
  cursor: pointer;
  transition: 0.2s;
}

.switch-btn:disabled {
  color: #c0c4cc;
  background: #f5f7fa;
  cursor: not-allowed;
}

.page-indicator {
  font-size: 13px;
  color: #666;
}

/* 标注明细激活高亮行 */
.ann-row.active {
  background-color: #e8f3ff;
}

/* Images页面新增上传区域 */
.drop-upload-area {
  margin-top: 24px;
  border: 2px dashed #d0d0d0;
  border-radius: 8px;
  padding: 40px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  border-radius: 30px;
}

.drop-upload-area.drag_active {
  border-color: #409eff;
  background-color: rgba(64, 158, 255, 0.05);
}

.upload-icon {
  margin-bottom: 16px;
}

.upload-title {
  font-size: 22px;
  font-weight: 500;
  color: #222;
  margin: 0 0 8px;
}

.upload-desc {
  font-size: 16px;
  color: #777;
  margin: 0;
}

/* 页脚 */
.page-footer {
  margin-top: 48px;
  padding: 24px 8px;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.back {
  color: #2b77e5;
  cursor: pointer;
  font-size: 14px;
  transition: 0.2s;
}

.back:hover {
  color: #1d5bbd;
  text-decoration: underline;
}

.footer-tip {
  font-size: 14px;
  color: #64748b;
}
</style>