<template>
  <section class="class-analysis">
    <header class="analysis-header">
      <div>
        <h2>类别级检测能力分析</h2>
        <p>比较每个类别的 AP、Precision、Recall 和 F1，并根据样本数量及基准差异自动诊断。</p>
      </div>
    </header>

    <div v-if="!analysisModels.length" class="empty-state">
      <strong>暂无类别级指标数据</strong>
      <p>编辑任一模型，在“指标 JSON”中加入以下结构后即可生成分析：</p>
      <pre>{
  "class_metrics": [
    {"class":"HM","instances":7,"ap50":0.92,"ap5095":0.70,
     "precision":0.81,"recall":0.85,"f1":0.83}
  ]
}</pre>
    </div>

    <template v-else>
      <div class="analysis-controls">
        <label><span>分析模型</span><el-select v-model="focusModelId" @change="syncSelections">
          <el-option v-for="model in analysisModels" :key="model.id" :label="model.name" :value="model.id" />
        </el-select></label>
        <label><span>对比基准</span><el-select v-model="baselineModelId" clearable placeholder="不使用基准">
          <el-option v-for="model in baselineOptions" :key="model.id" :label="model.name" :value="model.id" />
        </el-select></label>
        <label><span>排序依据</span><el-select v-model="sortKey">
          <el-option v-for="option in sortOptions" :key="option.key" :label="option.label" :value="option.key" />
        </el-select></label>
        <button class="direction-button" @click="sortDirection=sortDirection==='desc'?'asc':'desc'">
          {{ sortDirection === 'desc' ? '↓ 从高到低' : '↑ 从低到高' }}
        </button>
      </div>

      <div class="summary-grid">
        <article><span>已分析类别</span><strong>{{ tableRows.length }}</strong><small>{{ focusModel ? focusModel.name : '—' }}</small></article>
        <article class="warning"><span>少样本且指标低</span><strong>{{ diagnosisCounts.smallLow }}</strong><small>实例 &lt; 100，AP@50-95 &lt; 0.50</small></article>
        <article class="warning"><span>多样本但指标低</span><strong>{{ diagnosisCounts.manyLow }}</strong><small>实例 ≥ 100，AP@50-95 &lt; 0.50</small></article>
        <article class="danger"><span>明显退化</span><strong>{{ diagnosisCounts.degraded }}</strong><small>较基准下降至少 0.03</small></article>
        <article class="success"><span>提升最大类别</span><strong>{{ bestImprovement ? bestImprovement.class : '—' }}</strong><small>{{ bestImprovement ? formatDelta(bestImprovement.improvement) : '暂无可比数据' }}</small></article>
      </div>

      <div class="content-grid">
        <section class="compare-card">
          <div class="card-title">
            <div><h3>同类别多模型对比</h3><p>柱形长度对应当前指标数值，悬停可查看精确数据。</p></div>
            <div class="chart-selectors">
              <el-select v-model="selectedClass" filterable placeholder="选择类别">
                <el-option v-for="name in allClasses" :key="name" :label="name" :value="name" />
              </el-select>
              <el-select v-model="compareMetric">
                <el-option v-for="metric in metricDefinitions" :key="metric.key" :label="metric.label" :value="metric.key" />
              </el-select>
            </div>
          </div>
          <div v-if="comparisonRows.length" class="bar-chart">
            <div class="scale"><span>0</span><span>0.25</span><span>0.50</span><span>0.75</span><span>1.00</span></div>
            <div v-for="row in comparisonRows" :key="row.model.id" class="bar-row">
              <div class="bar-label" :title="row.model.name"><i :style="{background:row.color}" />{{ row.model.name }}</div>
              <div class="bar-track">
                <div v-if="isMetric(row.value)" class="bar-fill" :style="{width:barWidth(row.value),background:row.color}" :title="`${row.model.name} · ${selectedClass} · ${metricLabel(compareMetric)}：${formatMetric(row.value)}`" />
                <span v-else class="missing">无数据</span>
              </div>
              <strong>{{ formatMetric(row.value) }}</strong>
            </div>
          </div>
          <div v-else class="chart-empty">当前类别暂无可比较的模型数据</div>
        </section>

        <section class="table-card">
          <div class="card-title table-title">
            <div><h3>{{ focusModel ? focusModel.name : '' }} · 类别明细</h3><p>提升幅度按 AP@50-95 相对所选基准计算。</p></div>
            <span class="rule-note">诊断阈值：少样本 &lt;100 · 低指标 &lt;0.50 · 明显退化 ≤-0.03</span>
          </div>
          <div class="class-table-wrap">
            <table class="class-table">
              <thead><tr>
                <th @click="setSort('class')">类别 {{ sortMark('class') }}</th>
                <th @click="setSort('images')">影像数 {{ sortMark('images') }}</th>
                <th @click="setSort('instances')">实例数 {{ sortMark('instances') }}</th>
                <th @click="setSort('ap50')">AP@50 {{ sortMark('ap50') }}</th>
                <th @click="setSort('ap5095')">AP@50-95 {{ sortMark('ap5095') }}</th>
                <th @click="setSort('precision')">Precision {{ sortMark('precision') }}</th>
                <th @click="setSort('recall')">Recall {{ sortMark('recall') }}</th>
                <th @click="setSort('f1')">F1 {{ sortMark('f1') }}</th>
                <th @click="setSort('improvement')">提升幅度 {{ sortMark('improvement') }}</th>
                <th>自动诊断</th>
              </tr></thead>
              <tbody>
                <tr v-for="row in sortedRows" :key="row.class">
                  <td class="class-name">{{ row.class }}</td>
                  <td>{{ row.images === null ? '—' : row.images }}</td>
                  <td>{{ row.instances }}</td>
                  <td>{{ formatMetric(row.ap50) }}</td>
                  <td class="primary-value">{{ formatMetric(row.ap5095) }}</td>
                  <td>{{ formatMetric(row.precision) }}</td>
                  <td>{{ formatMetric(row.recall) }}</td>
                  <td>{{ formatMetric(row.f1) }}</td>
                  <td :class="deltaClass(row.improvement)">{{ formatDelta(row.improvement) }}</td>
                  <td class="diagnosis-cell"><span v-for="tag in row.tags" :key="tag.text" class="diagnosis-tag" :class="tag.type">{{ tag.text }}</span><span v-if="!row.tags.length" class="normal-tag">表现正常</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </template>
  </section>
</template>

<script>
export default {
  name: 'ClassMetricAnalysis',
  props: { models: { type: Array, default: () => [] }, colors: { type: Array, default: () => [] } },
  data: () => ({
    focusModelId: '', baselineModelId: '', selectedClass: '', compareMetric: 'ap5095',
    sortKey: 'ap5095', sortDirection: 'desc',
    metricDefinitions: [
      { key: 'ap50', label: 'AP@50' }, { key: 'ap5095', label: 'AP@50-95' },
      { key: 'precision', label: 'Precision' }, { key: 'recall', label: 'Recall' }, { key: 'f1', label: 'F1' }
    ],
    sortOptions: [
      { key: 'ap50', label: 'AP@50' }, { key: 'ap5095', label: 'AP@50-95' },
      { key: 'instances', label: '实例数量' }, { key: 'improvement', label: '提升幅度' }
    ]
  }),
  computed: {
    analysisModels () { return this.models.filter(model => model.metrics && Array.isArray(model.metrics.class_metrics) && model.metrics.class_metrics.some(row => !this.isAggregateClass(row.class))) },
    focusModel () { return this.analysisModels.find(model => model.id === this.focusModelId) || null },
    baselineModel () { return this.analysisModels.find(model => model.id === this.baselineModelId) || null },
    baselineOptions () { return this.analysisModels.filter(model => model.id !== this.focusModelId) },
    allClasses () {
      const names = new Set()
      this.analysisModels.forEach(model => model.metrics.class_metrics.forEach(row => { if (row.class && !this.isAggregateClass(row.class)) names.add(row.class) }))
      return [...names].sort((left, right) => left.localeCompare(right, 'zh-CN', { numeric: true }))
    },
    baselineLookup () {
      const lookup = new Map()
      if (this.baselineModel) this.baselineModel.metrics.class_metrics.filter(row => !this.isAggregateClass(row.class)).forEach(row => lookup.set(row.class, row))
      return lookup
    },
    tableRows () {
      if (!this.focusModel) return []
      const rows = this.focusModel.metrics.class_metrics.filter(item => !this.isAggregateClass(item.class)).map(item => {
        const baseline = this.baselineLookup.get(item.class)
        const ap5095 = this.toMetric(item.ap5095)
        const baselineValue = baseline ? this.toMetric(baseline.ap5095) : null
        const improvement = this.isMetric(ap5095) && this.isMetric(baselineValue) ? ap5095 - baselineValue : null
        return {
          class: item.class, images: Number.isFinite(Number(item.images)) ? Math.max(0, Number(item.images)) : null,
          instances: Math.max(0, Number(item.instances) || 0),
          ap50: this.toMetric(item.ap50), ap5095, precision: this.toMetric(item.precision),
          recall: this.toMetric(item.recall), f1: this.toMetric(item.f1), improvement, tags: []
        }
      })
      const comparable = rows.filter(row => this.isMetric(row.improvement) && row.improvement > 0)
      const best = comparable.length ? Math.max(...comparable.map(row => row.improvement)) : null
      return rows.map(row => {
        const tags = []
        if (row.instances < 100 && this.isMetric(row.ap5095) && row.ap5095 < 0.5) tags.push({ text: '少样本且指标低', type: 'warning' })
        if (row.instances >= 100 && this.isMetric(row.ap5095) && row.ap5095 < 0.5) tags.push({ text: '多样本但指标低', type: 'warning' })
        if (this.isMetric(row.improvement) && row.improvement <= -0.03) tags.push({ text: '较基准明显退化', type: 'danger' })
        if (best !== null && Math.abs(row.improvement - best) < 1e-10) tags.push({ text: '提升最大类别', type: 'success' })
        return { ...row, tags }
      })
    },
    sortedRows () {
      return [...this.tableRows].sort((left, right) => {
        const a = left[this.sortKey]; const b = right[this.sortKey]
        const aEmpty = a === null || a === undefined || a === ''; const bEmpty = b === null || b === undefined || b === ''
        if (aEmpty || bEmpty) return aEmpty === bEmpty ? 0 : (aEmpty ? 1 : -1)
        const result = typeof a === 'number' && typeof b === 'number' ? a - b : String(a).localeCompare(String(b), 'zh-CN', { numeric: true })
        return this.sortDirection === 'asc' ? result : -result
      })
    },
    diagnosisCounts () {
      return {
        smallLow: this.tableRows.filter(row => row.tags.some(tag => tag.text === '少样本且指标低')).length,
        manyLow: this.tableRows.filter(row => row.tags.some(tag => tag.text === '多样本但指标低')).length,
        degraded: this.tableRows.filter(row => row.tags.some(tag => tag.type === 'danger')).length
      }
    },
    bestImprovement () { return this.tableRows.find(row => row.tags.some(tag => tag.text === '提升最大类别')) || null },
    comparisonRows () {
      return this.analysisModels.map((model, index) => {
        const row = model.metrics.class_metrics.find(item => item.class === this.selectedClass)
        return { model, value: row ? this.toMetric(row[this.compareMetric]) : null, color: this.colors[index % this.colors.length] || '#3388ee' }
      })
    }
  },
  watch: {
    models: { immediate: true, deep: true, handler () { this.$nextTick(this.syncSelections) } },
    focusModelId () { this.$nextTick(this.syncSelections) }
  },
  methods: {
    syncSelections () {
      if (!this.analysisModels.length) return
      if (!this.analysisModels.some(model => model.id === this.focusModelId)) {
        this.focusModelId = [...this.analysisModels].sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')))[0].id
      }
      if (!this.baselineOptions.some(model => model.id === this.baselineModelId)) {
        const candidates = [...this.baselineOptions].sort((a, b) => String(a.created_at || '').localeCompare(String(b.created_at || '')))
        this.baselineModelId = candidates.length ? candidates[0].id : ''
      }
      if (!this.allClasses.includes(this.selectedClass)) this.selectedClass = this.allClasses[0] || ''
    },
    toMetric (value) { const number = Number(value); return Number.isFinite(number) ? number : null },
    isAggregateClass (value) { return ['all', 'overall', 'total', '全部', '总体', '汇总'].includes(String(value || '').trim().toLowerCase()) },
    isMetric (value) { return typeof value === 'number' && Number.isFinite(value) },
    formatMetric (value) { return this.isMetric(value) ? value.toFixed(4) : '—' },
    formatDelta (value) { return this.isMetric(value) ? `${value >= 0 ? '+' : ''}${value.toFixed(4)}` : '—' },
    deltaClass (value) { return !this.isMetric(value) ? '' : (value > 0 ? 'delta-up' : (value < 0 ? 'delta-down' : '')) },
    barWidth (value) { return `${Math.max(0, Math.min(100, value * 100))}%` },
    metricLabel (key) { const metric = this.metricDefinitions.find(item => item.key === key); return metric ? metric.label : key },
    setSort (key) { if (this.sortKey === key) this.sortDirection = this.sortDirection === 'desc' ? 'asc' : 'desc'; else { this.sortKey = key; this.sortDirection = 'desc' } },
    sortMark (key) { return this.sortKey === key ? (this.sortDirection === 'desc' ? '↓' : '↑') : '↕' }
  }
}
</script>

<style scoped>
.class-analysis{color:#182132}.analysis-header{display:flex;align-items:flex-end;justify-content:space-between;margin-bottom:18px}.analysis-header h2{margin:0 0 7px;font-size:22px}.analysis-header p,.card-title p{margin:0;color:#7f8998;font-size:13px}.empty-state{padding:45px;border:1px solid #e2e6ec;border-radius:13px;background:#fff;text-align:center}.empty-state strong{font-size:18px}.empty-state p{color:#7f8998}.empty-state pre{max-width:650px;margin:18px auto 0;padding:16px;border-radius:8px;background:#f6f8fb;color:#526176;text-align:left;white-space:pre-wrap}.analysis-controls{display:grid;grid-template-columns:1.3fr 1.3fr 1fr auto;align-items:end;gap:14px;padding:18px;border:1px solid #e2e6ec;border-radius:13px;background:#fff}.analysis-controls label>span{display:block;margin-bottom:7px;color:#687589;font-size:12px;font-weight:700}.analysis-controls .el-select{width:100%}.direction-button{height:40px;padding:0 16px;border:1px solid #dce3eb;border-radius:7px;background:#fff;color:#40516a;cursor:pointer}.direction-button:hover{border-color:#3388ee;color:#3388ee}.summary-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin:14px 0}.summary-grid article{padding:16px 17px;border:1px solid #e2e6ec;border-top:3px solid #74a8e8;border-radius:11px;background:#fff}.summary-grid article.warning{border-top-color:#e9a23b}.summary-grid article.danger{border-top-color:#e65b65}.summary-grid article.success{border-top-color:#31aa70}.summary-grid span,.summary-grid small{display:block;color:#7f8998;font-size:11px}.summary-grid strong{display:block;overflow:hidden;margin:9px 0 6px;color:#26354b;font-size:21px;text-overflow:ellipsis;white-space:nowrap}.content-grid{display:grid;gap:14px}.compare-card,.table-card{overflow:hidden;border:1px solid #e2e6ec;border-radius:13px;background:#fff;box-shadow:0 3px 12px rgba(30,45,70,.04)}.card-title{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;padding:20px 22px;border-bottom:1px solid #e9edf2}.card-title h3{margin:0 0 6px;font-size:17px}.chart-selectors{display:flex;gap:9px}.chart-selectors .el-select:first-child{width:170px}.chart-selectors .el-select:last-child{width:140px}.bar-chart{padding:22px}.scale{display:grid;grid-template-columns:repeat(5,1fr);margin:0 55px 8px 190px;color:#98a2b1;font-size:10px}.scale span:last-child{text-align:right}.bar-row{display:grid;grid-template-columns:170px minmax(200px,1fr) 58px;align-items:center;gap:14px;margin:13px 0}.bar-label{overflow:hidden;color:#526176;font-size:12px;font-weight:700;text-overflow:ellipsis;white-space:nowrap}.bar-label i{display:inline-block;width:9px;height:9px;margin-right:7px;border-radius:50%}.bar-track{position:relative;height:19px;border-radius:5px;background:repeating-linear-gradient(90deg,#f2f5f9 0,#f2f5f9 calc(25% - 1px),#dfe6ef 25%)}.bar-fill{height:100%;min-width:2px;border-radius:5px;box-shadow:0 2px 5px rgba(36,73,120,.18);transition:width .25s}.bar-row>strong{font-size:12px;font-variant-numeric:tabular-nums}.missing{position:absolute;left:8px;top:2px;color:#a1a9b5;font-size:10px}.chart-empty{padding:50px;text-align:center;color:#98a2b1}.table-title{align-items:center}.rule-note{padding:6px 9px;border-radius:6px;background:#f5f7fa;color:#7b8798;font-size:10px}.class-table-wrap{overflow-x:auto}.class-table{width:100%;min-width:1100px;border-collapse:collapse}.class-table th,.class-table td{padding:13px 12px;border-bottom:1px solid #e9edf2;text-align:left;white-space:nowrap;font-size:12px}.class-table th{background:#f8fafc;color:#637084;cursor:pointer;user-select:none}.class-table th:last-child{cursor:default}.class-table tbody tr:hover{background:#f8fbff}.class-name{color:#277fd9;font-weight:800}.primary-value{color:#172f50;font-weight:800}.delta-up{color:#159d65;font-weight:800}.delta-down{color:#dd4d58;font-weight:800}.diagnosis-cell{display:flex;flex-wrap:wrap;gap:5px}.diagnosis-tag,.normal-tag{padding:4px 7px;border-radius:10px;font-size:10px}.diagnosis-tag.warning{background:#fff4df;color:#a96b0c}.diagnosis-tag.danger{background:#ffebed;color:#c93f4b}.diagnosis-tag.success{background:#e5f7ee;color:#158657}.normal-tag{background:#eef3f8;color:#718095}@media(max-width:1050px){.analysis-controls{grid-template-columns:1fr 1fr}.summary-grid{grid-template-columns:repeat(3,1fr)}}@media(max-width:700px){.analysis-controls{grid-template-columns:1fr}.summary-grid{grid-template-columns:1fr 1fr}.card-title{align-items:flex-start;flex-direction:column}.chart-selectors{width:100%;flex-direction:column}.chart-selectors .el-select:first-child,.chart-selectors .el-select:last-child{width:100%}.bar-row{grid-template-columns:110px minmax(120px,1fr) 48px}.scale{margin-left:130px}}
</style>
