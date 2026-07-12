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
      <div><span>快捷入口</span><h2>开始你的工作</h2></div>
      <p>选择下方功能，快速进入任务流程</p>
    </div>

    <section class="feature-grid">
      <article class="feature-card featured" @click="$router.push('/detectobjects')">
        <div class="feature-top">
          <span class="feature-icon blue">⌖</span>
          <span class="arrow">↗</span>
        </div>
        <h3>目标检测</h3>
        <p>上传遥感影像，使用智能模型快速识别并定位图像中的目标对象。</p>
        <div class="card-visual detection-visual">
          <span class="scan-line" />
          <i class="target one" /><i class="target two" /><i class="target three" />
        </div>
      </article>

      <article class="feature-card muted-card">
        <div class="feature-top">
          <span class="feature-icon purple">▤</span>
          <span class="coming">即将上线</span>
        </div>
        <h3>数据集</h3>
        <p>集中管理遥感影像与标注数据，为模型训练、评估和应用提供可靠的数据基础。</p>
        <div class="card-visual dataset-visual">
          <div v-for="n in 3" :key="n" class="dataset-row"><i /><span /><b /></div>
        </div>
      </article>

      <article class="feature-card" @click="$router.push('/model-ranking')">
        <div class="feature-top">
          <span class="feature-icon green">♜</span>
          <span class="arrow">↗</span>
        </div>
        <h3>模型排行</h3>
        <p>创建模型项目，对比不同模型的指标表现，快速发现更适合任务的优秀模型。</p>
        <div class="card-visual ranking-visual">
          <div class="rank rank-two"><b>2</b><i /></div>
          <div class="rank rank-one"><b>1</b><i /></div>
          <div class="rank rank-three"><b>3</b><i /></div>
        </div>
      </article>
    </section>

    <section class="recent">
      <div><span class="recent-icon">◷</span><div><h3>最近活动</h3><p>你的任务动态将在这里展示</p></div></div>
      <button @click="$router.push('/history')">查看全部记录 →</button>
    </section>
  </main>
</template>

<script>
export default {
  name: 'DashboardView',
  data() {
    return {
      stats: [
        { icon: '⌖', value: '0', label: '检测任务', tone: 'blue' },
        { icon: '▧', value: '0', label: '处理影像', tone: 'cyan' },
        { icon: '✓', value: '0', label: '已完成', tone: 'green' },
        { icon: '◷', value: '—', label: '最近运行', tone: 'purple' }
      ]
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
.overview-card, .feature-card, .recent { border: 1px solid #e8edf4; background: #fff; box-shadow: 0 6px 24px rgba(31,45,70,.055); }
.overview-card { border-radius: 18px; padding: 26px 28px 22px; }
.profile { display: flex; align-items: center; gap: 15px; padding-bottom: 22px; border-bottom: 1px solid #edf0f5; }
.profile-mark { display: grid; place-items: center; width: 50px; height: 50px; border-radius: 14px; color: white; font-size: 23px; font-weight: 800; background: linear-gradient(145deg,#1f8cff,#5bc5e7); }
.profile h2, .profile p { margin: 0; }.profile h2 { font-size: 19px; margin-bottom: 5px; }.profile p { color: #8490a3; font-size: 13px; }
.status { margin-left: auto; padding: 7px 11px; border-radius: 20px; background: #effaf4; color: #349768; font-size: 12px; font-weight: 700; }.status i { display: inline-block; width: 7px; height: 7px; margin-right: 5px; border-radius: 50%; background: #37bf7b; }
.stats { display: grid; grid-template-columns: repeat(4,1fr); gap: 10px; padding-top: 20px; }
.stat-item { display: flex; align-items: center; gap: 12px; padding: 8px 12px; border-right: 1px solid #edf0f5; }.stat-item:last-child { border: 0; }
.stat-icon, .feature-icon { display: grid; place-items: center; border-radius: 10px; font-style: normal; font-weight: 800; }.stat-icon { width: 38px; height: 38px; }.stat-item strong, .stat-item small { display:block; }.stat-item strong { font-size: 20px; }.stat-item small { margin-top: 3px; color: #8c96a7; font-size: 12px; }
.blue { color:#2785f6; background:#eaf3ff; }.cyan { color:#14a4b8; background:#e8f9fb; }.green { color:#3da76d; background:#ebf8f0; }.purple { color:#8758df; background:#f2edff; }
.section-heading { display:flex; justify-content:space-between; align-items:flex-end; margin: 34px 2px 17px; }.section-heading span { color:#2684ff; font-size:12px; font-weight:700; }.section-heading h2 { margin:5px 0 0; font-size:22px; }.section-heading p { margin:0; color:#929bad; font-size:13px; }
.feature-grid { display:grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap:20px; }
.feature-card { position:relative; min-height: 275px; padding:24px; overflow:hidden; border-radius:16px; cursor:pointer; transition:.25s; }.feature-card:hover { transform:translateY(-4px); border-color:#cfe2fa; box-shadow:0 12px 30px rgba(31,76,130,.11); }.feature-top { display:flex; justify-content:space-between; align-items:center; }.feature-icon { width:43px; height:43px; font-size:21px; }.arrow { color:#9aa4b3; font-size:20px; }.feature-card h3 { margin:20px 0 9px; font-size:19px; }.feature-card p { max-width:360px; margin:0; color:#7f8a9c; font-size:13px; line-height:1.75; }.coming { padding:5px 9px; color:#7c8799; background:#f0f2f5; border-radius:20px; font-size:11px; }
.card-visual { position:absolute; left:24px; right:24px; bottom:20px; height:72px; border-radius:10px; overflow:hidden; background:#f2f6fb; }.detection-visual { background:linear-gradient(140deg,#dceaf0,#b7d3d0 45%,#d6c69c); }.detection-visual:before { content:""; position:absolute; inset:0; background:linear-gradient(90deg,transparent 48%,rgba(255,255,255,.25) 49%,transparent 50%); }.target { position:absolute; border:2px solid #2d86ff; }.target.one { width:54px;height:33px;left:16%;top:18px; }.target.two { width:42px;height:42px;left:51%;top:12px;border-color:#ffb328; }.target.three { width:34px;height:27px;right:8%;top:25px;border-color:#31be84; }.scan-line { position:absolute; left:0;right:0;top:50%;height:1px;background:rgba(255,255,255,.8); }
.dataset-visual { padding:10px 14px; box-sizing:border-box; }.dataset-row { display:flex; align-items:center; gap:8px; height:18px; }.dataset-row i { width:11px;height:9px;border-radius:2px;background:#9b78e8; }.dataset-row span { width:54%;height:5px;border-radius:4px;background:#d7e0ec; }.dataset-row b { margin-left:auto;width:17%;height:5px;border-radius:4px;background:#e3e8ef; }
.ranking-visual { display:flex; align-items:flex-end; justify-content:center; gap:7px; padding:9px 24% 0; box-sizing:border-box; }.rank { position:relative; display:flex; justify-content:center; width:31%; border-radius:5px 5px 0 0; background:#9bddb8; }.rank-one { height:100%; background:#55c587; }.rank-two { height:72%; }.rank-three { height:55%; }.rank b { position:absolute; top:8px; color:#fff; font-size:12px; }.rank i { position:absolute; top:-7px; width:13px; height:13px; border:3px solid #fff; border-radius:50%; background:#62cd92; }.muted-card { cursor:default; }.muted-card:hover { transform:none; }
.recent { display:flex; align-items:center; justify-content:space-between; margin-top:20px; padding:17px 22px; border-radius:14px; }.recent>div { display:flex;align-items:center;gap:12px; }.recent-icon { display:grid;place-items:center;width:38px;height:38px;border-radius:10px;background:#f1f5fa;color:#637086;font-size:20px; }.recent h3,.recent p { margin:0; }.recent h3 { font-size:15px;margin-bottom:3px; }.recent p { color:#949dae;font-size:12px; }.recent button { border:0;background:transparent;color:#3788ee;font-weight:700;cursor:pointer; }
@media (max-width: 1050px) { .feature-grid { grid-template-columns: 1fr 1fr; }.feature-card:last-child { display:none; } }
@media (max-width: 720px) { .dashboard { padding:24px 16px 34px; }.hero { align-items:flex-start; flex-direction:column; }.hero h1 { font-size:27px; }.stats { grid-template-columns:1fr 1fr; }.stat-item { border-right:0; }.feature-grid { grid-template-columns:1fr; }.feature-card:last-child { display:block; }.section-heading p { display:none; }.profile { align-items:flex-start; }.status { display:none; } }
</style>
