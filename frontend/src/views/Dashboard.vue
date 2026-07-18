<template>
  <main class="dashboard">
    <section class="hero">
      <div>
        <span class="eyebrow">GEOVIEW PLATFORM</span>
        <h1>欢迎使用 GeoView</h1>
        <p>面向遥感影像的智能解译平台，让目标检测、结果管理和数据分析更加简单高效。</p>
      </div>
      <button class="primary-action" @click="$router.push('/detectobjects')">
        开始检测 <span>→</span>
      </button>
    </section>

    <section class="overview-card">
      <div class="profile">
        <div class="profile-mark">G</div>
        <div>
          <h2>工作台概览</h2>
          <p>今日状态良好，开始一项新的遥感影像分析任务吧。</p>
        </div>
        <span class="status"><i /> 系统在线</span>
      </div>
      <div class="stats">
        <div v-for="item in stats" :key="item.label" class="stat-item">
          <span class="stat-icon" :class="item.tone">{{ item.icon }}</span>
          <div><strong>{{ item.value }}</strong><small>{{ item.label }}</small></div>
        </div>
      </div>
    </section>

    <div class="section-heading">
      <div><span>快捷入口</span><h2>数据集与模型</h2></div>
      <p>参考 Ultralytics 双分区布局，管理数据与模型资源</p>
    </div>

    <!-- Ultralytics 风格双卡片：数据集（左）+ 模型排行（右） -->
    <section class="dual-grid">
      <!-- 数据集卡片 -->
      <article class="dual-card dataset-card">
        <div class="card-head">
          <div class="card-title">
            <span class="card-icon green">▤</span>
            <h3>数据集</h3>
          </div>
          <button class="dark-button" @click="goDatasetManage">＋ 新数据集</button>
        </div>

        <div
            class="upload-drop"
            :class="{ dragging: isDragging }"
            @dragover.prevent="isDragging = true"
            @dragleave.prevent="isDragging = false"
            @drop.prevent="onDrop"
            @click="goDatasetManage"
        >
          <span class="cloud">☁</span>
          <p>投放遥感影像、YOLO 标注数据集压缩包</p>
          <small>{{ uploadHint }}</small>
        </div>

        <!-- 横向滚动缩略预览栏：固定纵向高度，不撑开卡片 -->
        <div v-if="previewSamples.length" class="thumb-scroll">
          <div class="thumb-track">
            <div v-for="(s, i) in previewSamples" :key="i" class="thumb-item">
              <img :src="fullUrl(s.url)" :alt="s.filename">
            </div>
          </div>
        </div>
        <div v-else class="thumb-empty">上传数据集后，样本将在此预览</div>

        <button class="view-all" @click="goDatasetManage">查看全部</button>
      </article>

      <!-- 模型排行卡片 -->
      <article class="dual-card model-card" @click="$router.push('/model-ranking')">
        <div class="card-head">
          <div class="card-title">
            <span class="card-icon blue">♜</span>
            <h3>模型排行</h3>
          </div>
          <span class="arrow">↗</span>
        </div>
        <p class="card-desc">创建模型项目，对比不同模型的指标表现，快速发现更适合任务的优秀模型。</p>
        <div class="card-visual ranking-visual">
          <div class="rank rank-two"><b>2</b><i /></div>
          <div class="rank rank-one"><b>1</b><i /></div>
          <div class="rank rank-three"><b>3</b><i /></div>
        </div>
      </article>
    </section>

    <!-- 目标检测快捷入口 -->
    <section class="detect-shortcut" @click="$router.push('/detectobjects')">
      <span class="detect-icon">⌖</span>
      <div>
        <h3>目标检测</h3>
        <p>选择已上传数据集与模型，执行遥感影像推理</p>
      </div>
      <span class="arrow">→</span>
    </section>

    <section class="recent">
      <div><span class="recent-icon">◷</span><div><h3>最近活动</h3><p>你的任务动态将在这里展示</p></div></div>
      <button @click="$router.push('/history')">查看全部记录 →</button>
    </section>
  </main>
</template>

<script>
import { getDatasetStats, getDatasetSamples } from '@/api/dataset'
import { UPLOAD_HINT } from '@/utils/datasetConstants'
import { queueFiles } from '@/utils/datasetUploadQueue'
import global from '@/global'

export default {
  name: 'DashboardView',
  data() {
    return {
      stats: [
        { icon: '▤', value: '0', label: '数据集', tone: 'green' },
        { icon: '▧', value: '0', label: '处理影像', tone: 'cyan' },
        { icon: '✓', value: '0', label: '标注框', tone: 'blue' },
        { icon: '◷', value: '—', label: '最近运行', tone: 'purple' }
      ],
      samples: [],
      uploadHint: UPLOAD_HINT,
      isDragging: false
    }
  },
  computed: {
    // 计算属性：只截取前8张图片用于预览，限制渲染数量
    previewSamples() {
      return this.samples.slice(0, 8)
    }
  },
  mounted() {
    this.loadDatasetInfo()
  },
  methods: {
    fullUrl(path) {
      if (!path) return ''
      return global.BASEURL.replace(/\/$/, '') + path
    },
    goDatasetManage() {
      this.$router.push('/dataset-management')
    },
    onDrop(e) {
      this.isDragging = false
      const files = Array.from(e.dataTransfer.files || [])
      if (files.length) {
        queueFiles(files)
        this.goDatasetManage()
      }
    },
    async loadDatasetInfo() {
      try {
        const [statsRes, samplesRes] = await Promise.all([
          getDatasetStats(),
          getDatasetSamples()
        ])
        const d = statsRes.data.data
        this.stats[0].value = String(d.dataset_count)
        this.stats[1].value = String(d.image_count)
        this.stats[2].value = String(d.box_count)
        this.samples = samplesRes.data.data || []
      } catch { /* 后端未启动时保持默认 */ }
    }
  }
}
</script>

<style scoped>
.dashboard { min-height: calc(100vh - 60px); padding: 38px 34px 46px; box-sizing: border-box; color: #172033; background: #f7f9fc; font-family: "Microsoft YaHei", Arial, sans-serif; }
.hero { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin-bottom: 28px; }
.eyebrow { color: #409eff; font-size: 12px; font-weight: 800; letter-spacing: 2px; }
h1 { margin: 8px 0 10px; font-size: 34px; letter-spacing: -1px; }
.hero p { margin: 0; color: #748095; font-size: 15px; }
.primary-action { border: 0; border-radius: 12px; padding: 13px 22px; background: #2684ff; color: #fff; font-size: 15px; font-weight: 700; cursor: pointer; box-shadow: 0 8px 20px rgba(38,132,255,.24); transition: .2s; }
.primary-action:hover { transform: translateY(-2px); box-shadow: 0 11px 25px rgba(38,132,255,.3); }
.primary-action span { margin-left: 12px; }
.overview-card, .dual-card, .recent, .detect-shortcut { border: 1px solid #e8edf4; background: #fff; box-shadow: 0 6px 24px rgba(31,45,70,.055); }
.overview-card { border-radius: 18px; padding: 26px 28px 22px; }
.profile { display: flex; align-items: center; gap: 15px; padding-bottom: 22px; border-bottom: 1px solid #edf0f5; }
.profile-mark { display: grid; place-items: center; width: 50px; height: 50px; border-radius: 14px; color: white; font-size: 23px; font-weight: 800; background: linear-gradient(145deg,#1f8cff,#5bc5e7); }
.profile h2, .profile p { margin: 0; }.profile h2 { font-size: 19px; margin-bottom: 5px; }.profile p { color: #8490a3; font-size: 13px; }
.status { margin-left: auto; padding: 7px 11px; border-radius: 20px; background: #effaf4; color: #349768; font-size: 12px; font-weight: 700; }.status i { display: inline-block; width: 7px; height: 7px; margin-right: 5px; border-radius: 50%; background: #37bf7b; }
.stats { display: grid; grid-template-columns: repeat(4,1fr); gap: 10px; padding-top: 20px; }
.stat-item { display: flex; align-items: center; gap: 12px; padding: 8px 12px; border-right: 1px solid #edf0f5; }.stat-item:last-child { border: 0; }
.stat-icon { display: grid; place-items: center; border-radius: 10px; font-style: normal; font-weight: 800; width: 38px; height: 38px; }
.stat-item strong, .stat-item small { display:block; }.stat-item strong { font-size: 20px; }.stat-item small { margin-top: 3px; color: #8c96a7; font-size: 12px; }
.blue { color:#2785f6; background:#eaf3ff; }.cyan { color:#14a4b8; background:#e8f9fb; }.green { color:#3da76d; background:#ebf8f0; }.purple { color:#8758df; background:#f2edff; }
.section-heading { display:flex; justify-content:space-between; align-items:flex-end; margin: 34px 2px 17px; }.section-heading span { color:#2684ff; font-size:12px; font-weight:700; }.section-heading h2 { margin:5px 0 0; font-size:22px; }.section-heading p { margin:0; color:#929bad; font-size:13px; }

/* 双卡片布局 */
.dual-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
/* 核心修改：固定卡片高度，不再自适应撑开 */
.dual-card {
  border-radius: 16px;
  padding: 22px 24px 18px;
  height: 320px; /* 固定高度，两张卡片完全等高 */
  display: flex;
  flex-direction: column;
}
.card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.card-title { display: flex; align-items: center; gap: 10px; }
.card-title h3 { margin: 0; font-size: 19px; }
.card-icon { display: grid; place-items: center; width: 40px; height: 40px; border-radius: 10px; font-size: 20px; font-style: normal; font-weight: 800; }
.card-icon.green { color: #3da76d; background: #ebf8f0; }
.card-icon.blue { color: #2785f6; background: #eaf3ff; }
.dark-button { padding: 9px 16px; border: 0; border-radius: 10px; background: #151515; color: #fff; font-size: 13px; font-weight: 700; cursor: pointer; }
.dark-button:hover { background: #2a2a2a; }

.upload-drop {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 28px 16px; border: 2px dashed #b3d4fc; border-radius: 12px;
  background: #f0f7ff; cursor: pointer; transition: .2s;
  flex: 1; /* 自动填充剩余空间 */
}
.upload-drop.dragging, .upload-drop:hover { border-color: #409eff; background: #e8f3ff; }
.upload-drop .cloud { font-size: 30px; color: #409eff; font-style: normal; }
.upload-drop p { margin: 0; font-size: 14px; color: #444; text-align: center; }
.upload-drop small { font-size: 11px; color: #9aa5b3; text-align: center; }

/* 核心修改：锁定预览区域纵向高度，仅横向滚动，不会拉高卡片 */
.thumb-scroll {
  margin-top: 14px;
  overflow: hidden;
  max-height: 70px; /* 固定纵向高度，超出隐藏 */
}
.thumb-track { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 4px; scrollbar-width: thin; }
.thumb-item { flex-shrink: 0; width: 72px; height: 54px; border-radius: 6px; overflow: hidden; border: 1px solid #e0e6ed; }
.thumb-item img { width: 100%; height: 100%; object-fit: cover; }
.thumb-empty { margin-top: 14px; padding: 12px; text-align: center; font-size: 12px; color: #aab4c3; background: #f5f7fa; border-radius: 8px; }
.view-all { margin-top: 12px; border: 0; background: transparent; color: #3788ee; font-weight: 700; font-size: 13px; cursor: pointer; text-align: left; padding: 0; }
.view-all:hover { text-decoration: underline; }

.model-card { cursor: pointer; transition: .25s; }
.model-card:hover { transform: translateY(-4px); border-color: #cfe2fa; box-shadow: 0 12px 30px rgba(31,76,130,.11); }
.card-desc { margin: 0 0 12px; color: #7f8a9c; font-size: 13px; line-height: 1.7; }
.arrow { color: #9aa4b3; font-size: 20px; }
.card-visual { position: relative; height: 72px; border-radius: 10px; overflow: hidden; background: #f2f6fb; margin-top: auto; }
.ranking-visual { display:flex; align-items:flex-end; justify-content:center; gap:7px; padding:9px 24% 0; box-sizing:border-box; }
.rank { position:relative; display:flex; justify-content:center; width:31%; border-radius:5px 5px 0 0; background:#9bddb8; }
.rank-one { height:100%; background:#55c587; }.rank-two { height:72%; }.rank-three { height:55%; }
.rank b { position:absolute; top:8px; color:#fff; font-size:12px; }
.rank i { position:absolute; top:-7px; width:13px; height:13px; border:3px solid #fff; border-radius:50%; background:#62cd92; }

.detect-shortcut {
  display: flex; align-items: center; gap: 14px;
  margin-top: 20px; padding: 16px 22px; border-radius: 14px; cursor: pointer; transition: .2s;
}
.detect-shortcut:hover { border-color: #bcd8fb; transform: translateY(-2px); }
.detect-icon { display: grid; place-items: center; width: 42px; height: 42px; border-radius: 10px; background: #eaf3ff; color: #2785f6; font-size: 22px; font-style: normal; }
.detect-shortcut h3 { margin: 0 0 3px; font-size: 15px; }
.detect-shortcut p { margin: 0; font-size: 12px; color: #8c96a7; }
.detect-shortcut .arrow { margin-left: auto; color: #3788ee; font-weight: 700; }

.recent { display:flex; align-items:center; justify-content:space-between; margin-top:20px; padding:17px 22px; border-radius:14px; }
.recent>div { display:flex;align-items:center;gap:12px; }
.recent-icon { display:grid;place-items:center;width:38px;height:38px;border-radius:10px;background:#f1f5fa;color:#637086;font-size:20px; }
.recent h3,.recent p { margin:0; }.recent h3 { font-size:15px;margin-bottom:3px; }.recent p { color:#949dae;font-size:12px; }
.recent button { border:0;background:transparent;color:#3788ee;font-weight:700;cursor:pointer; }

@media (max-width: 900px) { .dual-grid { grid-template-columns: 1fr; } }
@media (max-width: 720px) {
  .dashboard { padding:24px 16px 34px; }
  .hero { align-items:flex-start; flex-direction:column; }
  .hero h1 { font-size:27px; }
  .stats { grid-template-columns:1fr 1fr; }
  .stat-item { border-right:0; }
  .section-heading p { display:none; }
  .profile { align-items:flex-start; }
  .status { display:none; }
}
</style>