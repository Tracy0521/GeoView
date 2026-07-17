<template>
  <div class="metric-chart">
    <h4>{{ title }}</h4>
    <div class="chart-stage">
      <svg ref="svg" viewBox="0 0 440 240" preserveAspectRatio="none" @mousemove="handleMove" @mouseleave="hoverIndex=null">
        <g class="grid">
          <line v-for="tick in yTicks" :key="'yh'+tick.y" x1="55" x2="425" :y1="tick.y" :y2="tick.y" />
          <line v-for="tick in xTicks" :key="'xv'+tick.value" :x1="tick.x" :x2="tick.x" y1="18" y2="193" />
        </g>
        <line class="axis" x1="55" x2="425" y1="193" y2="193" />
        <line class="axis" x1="55" x2="55" y1="18" y2="193" />
        <g class="labels">
          <text v-for="tick in yTicks" :key="'yl'+tick.y" x="47" :y="tick.y+4" class="y-label">{{ formatTick(tick.value) }}</text>
          <text v-for="tick in xTicks" :key="'xl'+tick.value" :x="tick.x" y="211">{{ formatEpoch(tick.value) }}</text>
          <text x="240" y="232" class="axis-title">轮次（Epoch）</text>
        </g>
        <polyline v-for="line in drawableLines" :key="line.id" :points="line.points" :stroke="line.color" />
        <g v-if="hoverIndex!==null && hoverValues.length" class="hover-layer">
          <line :x1="hoverX" :x2="hoverX" y1="18" y2="193" />
          <circle v-for="item in hoverValues" :key="item.id" :cx="hoverX" :cy="valueY(item.value)" r="4" :fill="item.color" />
        </g>
        <text v-if="!lines.length" x="240" y="108" class="empty">请选择包含指标数据的模型</text>
      </svg>
      <div v-if="hoverIndex!==null && hoverValues.length" class="tooltip" :class="{ right: tooltipRight }" :style="tooltipStyle">
          <strong>轮次：{{ formatEpoch(hoverIndex) }}</strong>
        <div v-for="item in hoverValues" :key="item.id"><i :style="{background:item.color}" /><span>{{ item.name }}</span><b>{{ formatValue(item.value) }}</b></div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'MetricChart',
  props: { title: { type: String, required: true }, lines: { type: Array, default: () => [] } },
  data: () => ({ hoverIndex: null, pointerPercent: 0 }),
  computed: {
    allValues() { return this.lines.flatMap(item => item.values || []).filter(Number.isFinite) },
    epochValues() { return this.lines.flatMap(line => this.lineEpochs(line)) },
    minEpoch() { return this.epochValues.length ? Math.min(...this.epochValues) : 0 },
    maxEpoch() { return this.epochValues.length ? Math.max(...this.epochValues) : 1 },
    bounds() {
      if (!this.allValues.length) return { min: 0, max: 1 }
      let min = Math.min(...this.allValues), max = Math.max(...this.allValues)
      const padding = (max - min || Math.max(Math.abs(max) * 0.1, 0.1)) * 0.12
      min -= padding; max += padding
      if (min >= 0 && min < padding * 1.5) min = 0
      return { min, max }
    },
    yTicks() { return Array.from({length:6}, (_,i) => ({value:this.bounds.max-(this.bounds.max-this.bounds.min)*i/5,y:18+i*35})) },
    xTicks() { return Array.from({length:6},(_,i)=>({value:this.minEpoch+(this.maxEpoch-this.minEpoch)*i/5,x:55+i*74})) },
    drawableLines() { return this.lines.filter(line=>line.values&&line.values.length).map(line=>({...line,points:line.values.map((value,index)=>`${this.epochX(this.lineEpochs(line)[index]).toFixed(1)},${this.valueY(value).toFixed(1)}`).join(' ')})) },
    hoverX() { return this.epochX(this.hoverIndex===null?this.minEpoch:this.hoverIndex) },
    hoverValues() { if(this.hoverIndex===null)return[]; return this.lines.flatMap(line=>{const epochs=this.lineEpochs(line);const index=epochs.findIndex(epoch=>Math.abs(epoch-this.hoverIndex)<1e-6);return index>=0&&Number.isFinite(line.values[index])?[{id:line.id,name:line.name,color:line.color,value:line.values[index]}]:[]}).sort((left,right)=>right.value-left.value) },
    tooltipRight() { return this.pointerPercent>62 },
    tooltipStyle() { return this.tooltipRight?{right:`${Math.max(3,100-this.pointerPercent+2)}%`}:{left:`${Math.min(78,this.pointerPercent+2)}%`} }
  },
  methods: {
    lineEpochs(line) { return Array.isArray(line.epochs)&&line.epochs.length===line.values.length?line.epochs:line.values.map((_,index)=>index) },
    epochX(epoch) { return 55+((epoch-this.minEpoch)/Math.max(this.maxEpoch-this.minEpoch,1))*370 },
    valueY(value) { return 193-((value-this.bounds.min)/(this.bounds.max-this.bounds.min||1))*175 },
    handleMove(event) { if(!this.allValues.length)return; const rect=this.$refs.svg.getBoundingClientRect(); const viewX=(event.clientX-rect.left)/rect.width*440; const clamped=Math.max(55,Math.min(425,viewX)); const target=this.minEpoch+(clamped-55)/370*(this.maxEpoch-this.minEpoch); this.hoverIndex=this.epochValues.reduce((nearest,epoch)=>Math.abs(epoch-target)<Math.abs(nearest-target)?epoch:nearest,this.epochValues[0]); this.pointerPercent=(event.clientX-rect.left)/rect.width*100 },
    formatTick(value) { const abs=Math.abs(value); return abs>=100?value.toFixed(0):abs>=1?value.toFixed(2):value.toFixed(3) },
    formatValue(value) { return Number(value).toFixed(Math.abs(value)<0.1?5:4) },
    formatEpoch(value) { return Number.isInteger(value)?value:Number(value).toFixed(1) }
  }
}
</script>

<style scoped>
.metric-chart{border:1px solid #e1e5eb;border-radius:14px;background:#fff;padding:12px 12px 8px}.metric-chart h4{text-align:center;margin:0 0 3px;color:#283448;font-size:14px}.chart-stage{position:relative}.metric-chart svg{display:block;width:100%;height:235px;cursor:crosshair;overflow:visible}.grid line{stroke:#e9edf2;stroke-width:1}.axis{stroke:#bdc6d2;stroke-width:1}.labels text{fill:#667286;font-size:11px;text-anchor:middle}.labels .y-label{text-anchor:end}.labels .axis-title{font-size:12px}polyline{fill:none;stroke-width:2.2;vector-effect:non-scaling-stroke;stroke-linejoin:round;stroke-linecap:round}.empty{fill:#a2abb9;font-size:13px;text-anchor:middle}.hover-layer line{stroke:#8792a3;stroke-width:1}.hover-layer circle{stroke:#fff;stroke-width:2}.tooltip{position:absolute;top:48%;z-index:3;min-width:145px;max-width:220px;padding:10px 12px;border:1px solid #e3e6eb;border-radius:10px;background:rgba(255,255,255,.96);box-shadow:0 6px 18px rgba(24,34,50,.16);pointer-events:none;transform:translateY(-50%)}.tooltip strong{display:block;margin-bottom:7px;color:#273143;font-size:12px}.tooltip div{display:grid;grid-template-columns:9px minmax(45px,1fr) auto;align-items:center;gap:7px;margin-top:5px;font-size:11px}.tooltip i{width:9px;height:9px;border-radius:50%}.tooltip span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#4e5a6c}.tooltip b{color:#172033;font-size:12px}.tooltip.right{left:auto}
</style>
