<template>
  <div class="small-sample-chart">
    <div class="chart-head">
      <h4>小样本类别变化 <small>（实例数 &lt; 100）</small></h4>
      <div v-if="datasets.length" class="line-legend">
        <span><i class="dash" />基线</span><span><i />模型结果</span>
      </div>
    </div>
    <div v-if="datasets.length" class="model-legend">
      <span v-for="item in datasets" :key="item.id"><i :style="{background:item.color}" />{{ item.name }}</span>
    </div>
    <div v-if="categories.length" ref="stage" class="chart-stage">
      <svg ref="svg" viewBox="0 0 720 310" preserveAspectRatio="none" @mousemove="handleMove" @mouseleave="hoverIndex=null">
        <g class="grid"><line v-for="tick in yTicks" :key="tick.y" x1="58" x2="704" :y1="tick.y" :y2="tick.y" /></g>
        <line class="axis" x1="58" x2="704" y1="244" y2="244" /><line class="axis" x1="58" x2="58" y1="18" y2="244" />
        <g class="labels">
          <text v-for="tick in yTicks" :key="'y'+tick.y" x="49" :y="tick.y+4" class="y-label">{{ tick.value.toFixed(2) }}</text>
          <g v-for="(item,index) in categories" :key="item.class" :transform="`translate(${pointX(index)},0)`">
            <text y="265">{{ item.class }}</text><text y="284" class="instances">{{ item.instances }} instances</text>
          </g>
        </g>
        <g v-for="model in chartModels" :key="model.id">
          <polyline :points="model.baselinePoints" :stroke="model.color" class="data-line baseline-line" />
          <polyline :points="model.strpnPoints" :stroke="model.color" class="data-line" />
          <g v-for="point in model.points" :key="model.id+point.class">
            <circle :cx="point.x" :cy="point.baselineY" r="3.8" :fill="model.color" class="data-point baseline-point" />
            <circle :cx="point.x" :cy="point.strpnY" r="4.2" :fill="model.color" class="data-point" />
          </g>
        </g>
        <g v-if="hoverIndex!==null" class="hover-layer">
          <line :x1="pointX(hoverIndex)" :x2="pointX(hoverIndex)" y1="18" y2="244" />
          <circle v-for="item in hoverValues" :key="item.id+'b'" :cx="pointX(hoverIndex)" :cy="pointY(item.baseline)" r="5" :fill="item.color" class="hover-baseline" />
          <circle v-for="item in hoverValues" :key="item.id+'s'" :cx="pointX(hoverIndex)" :cy="pointY(item.strpn)" r="5" :fill="item.color" />
        </g>
      </svg>
      <div v-if="hoverIndex!==null && hoverValues.length" class="tooltip" :class="{right:tooltipRight}" :style="tooltipStyle">
        <strong>{{ categories[hoverIndex].class }} <small>{{ categories[hoverIndex].instances }} instances</small></strong>
        <div v-for="item in hoverValues" :key="item.id" class="tooltip-model">
          <div class="model-name"><i :style="{background:item.color}" />{{ item.name }}</div>
          <div class="metric"><span>{{ item.baselineLabel }}</span><b>{{ format(item.baseline) }}</b></div>
          <div class="metric"><span>{{ item.resultLabel }}</span><b>{{ format(item.strpn) }}</b></div>
          <div class="metric change"><span>变化</span><b :class="item.change>=0?'up':'down'">{{ formatChange(item.change) }} {{ item.change>=0?'↑':'↓' }}</b></div>
        </div>
      </div>
    </div>
    <div v-else class="empty">请选择包含小样本类别指标数据的模型</div>
  </div>
</template>

<script>
export default {
  name:'SmallSampleChart', props:{datasets:{type:Array,default:()=>[]}}, data:()=>({hoverIndex:null,pointerPercent:0}),
  computed:{
    categories(){const result=[];this.datasets.forEach(model=>model.values.forEach(item=>{if(!result.some(existing=>existing.class===item.class))result.push({class:item.class,instances:Number(item.instances)})}));return result.sort((left,right)=>left.instances-right.instances||left.class.localeCompare(right.class))},
    allValues(){return this.datasets.flatMap(model=>model.values.flatMap(item=>[item.baseline,item.strpn])).filter(Number.isFinite)},
    bounds(){if(!this.allValues.length)return{min:0,max:1};let min=Math.min(...this.allValues),max=Math.max(...this.allValues);const pad=(max-min||.1)*.12;return{min:Math.max(0,min-pad),max:max+pad}},
    yTicks(){return Array.from({length:6},(_,i)=>({value:this.bounds.max-(this.bounds.max-this.bounds.min)*i/5,y:18+i*45.2}))},
    chartModels(){return this.datasets.map(model=>{const points=this.categories.flatMap((category,index)=>{const item=model.values.find(value=>value.class===category.class);return item?[{...item,x:this.pointX(index),baselineY:this.pointY(item.baseline),strpnY:this.pointY(item.strpn)}]:[]});return{...model,points,baselinePoints:points.map(point=>`${point.x},${point.baselineY}`).join(' '),strpnPoints:points.map(point=>`${point.x},${point.strpnY}`).join(' ')}})},
    hoverValues(){if(this.hoverIndex===null)return[];const category=this.categories[this.hoverIndex];return this.datasets.flatMap(model=>{const item=model.values.find(value=>value.class===category.class);return item?[{id:model.id,name:model.name,color:model.color,baseline:item.baseline,baselineLabel:item.baseline_label||'基线',strpn:item.strpn,resultLabel:item.result_label||'ST-RPN',change:item.strpn-item.baseline}]:[]})},
    tooltipRight(){return this.pointerPercent>65},
    tooltipStyle(){return this.tooltipRight?{right:`${Math.max(2,100-this.pointerPercent+2)}%`}:{left:`${Math.min(78,this.pointerPercent+2)}%`}}
  },
  methods:{
    pointX(index){return 58+(index/Math.max(this.categories.length-1,1))*646},
    pointY(value){return 244-(value-this.bounds.min)/(this.bounds.max-this.bounds.min||1)*226},
    handleMove(event){const rect=this.$refs.svg.getBoundingClientRect();const viewX=(event.clientX-rect.left)/rect.width*720;const clamped=Math.max(58,Math.min(704,viewX));this.hoverIndex=Math.round((clamped-58)/646*Math.max(this.categories.length-1,0));this.pointerPercent=(event.clientX-rect.left)/rect.width*100},
    format(value){return Number(value).toFixed(3)},
    formatChange(value){return `${value>=0?'+':''}${Number(value).toFixed(3)}`}
  }
}
</script>

<style scoped>
.small-sample-chart{grid-column:1/-1;border:1px solid #e1e5eb;border-radius:14px;background:#fff;padding:14px}.chart-head{display:flex;align-items:center;justify-content:space-between}.chart-head h4{margin:0;color:#283448;font-size:14px}.chart-head h4 small{color:#7f8998;font-weight:400}.line-legend,.model-legend{display:flex;align-items:center;flex-wrap:wrap;gap:14px;color:#657184;font-size:12px}.line-legend span,.model-legend span{display:flex;align-items:center;gap:6px}.line-legend i{width:22px;border-top:3px solid #667286}.line-legend i.dash{border-top-style:dashed}.model-legend{margin-top:12px;padding:9px 12px;border-radius:8px;background:#f8fafc}.model-legend i{width:9px;height:9px;border-radius:50%}.chart-stage{position:relative}.chart-stage svg{display:block;width:100%;height:310px;overflow:visible;cursor:crosshair}.grid line{stroke:#e9edf2;stroke-width:1}.axis{stroke:#bdc6d2;stroke-width:1}.labels text{fill:#536074;font-size:11px;text-anchor:middle}.labels .y-label{text-anchor:end}.labels .instances{fill:#8b95a4;font-size:9px}.data-line{fill:none;stroke-width:2.4;vector-effect:non-scaling-stroke;stroke-linecap:round;stroke-linejoin:round}.baseline-line{stroke-dasharray:7 5;opacity:.82}.data-point{stroke:#fff;stroke-width:2}.baseline-point{opacity:.82}.hover-layer line{stroke:#8792a3;stroke-width:1;stroke-dasharray:3 3}.hover-layer circle{stroke:#fff;stroke-width:2}.hover-layer .hover-baseline{opacity:.72}.tooltip{position:absolute;top:47%;z-index:3;min-width:210px;max-width:270px;padding:11px 13px;border:1px solid #dfe4eb;border-radius:10px;background:rgba(255,255,255,.97);box-shadow:0 7px 20px rgba(24,34,50,.16);pointer-events:none;transform:translateY(-50%)}.tooltip>strong{display:block;padding-bottom:8px;border-bottom:1px solid #edf0f4;color:#273143;font-size:13px}.tooltip>strong small{margin-left:5px;color:#8a94a3;font-weight:400}.tooltip-model{padding-top:8px}.tooltip-model+.tooltip-model{margin-top:7px;border-top:1px solid #edf0f4}.model-name{display:flex;align-items:center;gap:6px;margin-bottom:5px;color:#3d4859;font-size:12px;font-weight:700}.model-name i{width:9px;height:9px;border-radius:50%}.metric{display:grid;grid-template-columns:1fr auto;gap:14px;margin-top:3px;color:#6f7a8a;font-size:11px}.metric b{color:#263143;font-size:11px}.metric .up{color:#159867}.metric .down{color:#d94d55}.tooltip.right{left:auto}.empty{padding:80px 20px;text-align:center;color:#a2abb9;font-size:13px}@media(max-width:780px){.chart-head{align-items:flex-start;flex-direction:column;gap:10px}.chart-stage{overflow-x:auto}.chart-stage svg{min-width:680px}.tooltip{position:fixed;top:auto;right:16px!important;bottom:16px;left:16px!important;max-width:none;transform:none}}
</style>
