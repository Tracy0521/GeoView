<template>
  <section class="diagnosis">
    <aside>
      <div class="side-title"><strong>诊断范围</strong><small>选择模型与类别</small></div>
      <label>模型</label>
      <el-select v-model="modelId" placeholder="选择模型"><el-option v-for="model in models" :key="model.id" :label="model.name" :value="model.id" /></el-select>
      <label>类别</label>
      <el-select v-model="className"><el-option label="全部类别" value=""/><el-option v-for="name in classes" :key="name" :label="name" :value="name"/></el-select>
      <label>错误类型</label>
      <div class="type-list"><button v-for="item in types" :key="item.key" :class="{active:type===item.key}" @click="type=item.key"><span>{{ item.label }}</span><b>{{ count(item.key) }}</b></button></div>
      <small class="count-hint">“全部影像”按图片去重；其余类型按目标框统计，同一图片可能包含多个问题。</small>
      <el-button type="primary" plain @click="openGenerate">生成诊断数据</el-button>
    </aside>
    <main>
      <header><div><h2>错误样本诊断中心</h2><p>从真实框与预测框中定位模型失效原因</p></div><span>{{ remoteTotal }} 个样本</span></header>
      <div v-if="samples.length" class="reason-card">
        <div v-for="reason in reasons" :key="reason.key"><span>{{ reason.label }}</span><i><em :style="{width:reason.percent+'%'}" /></i><b>{{ reason.percent }}%</b></div>
      </div>
      <div v-if="filtered.length" class="sample-grid">
        <button v-for="sample in filtered" :key="sample.id" @click="selected=sample">
          <div class="thumb"><img v-if="sample.image" :src="absoluteUrl(sample.image)"><span v-else>暂无原图</span><em :class="sample.type">{{ sample.error_types&&sample.error_types.length>1 ? `${sample.error_types.length} 类问题` : typeLabel(sample.type) }}</em><b v-if="sample.error_count>1">{{ sample.error_count }} 处</b></div>
          <strong>{{ sample.image_name || '未命名影像' }}</strong><small>{{ errorSummary(sample) }}</small>
        </button>
      </div>
      <el-empty v-else description="暂无符合条件的诊断样本，请先选择验证集生成诊断数据" />
    </main>

    <el-dialog v-model="uploadVisible" title="生成错误样本诊断数据" width="620px" :close-on-click-modal="false">
      <p class="help">系统将使用模型权重对验证集逐张推理，读取数据集中的 YOLO 标注，并自动计算 TP、FN、FP、类别错误、定位偏差和小目标漏检。</p>
      <el-form label-position="top"><el-form-item label="检测模型"><el-select v-model="uploadModelId"><el-option v-for="model in supportedModels" :key="model.id" :label="model.name" :value="model.id" /></el-select></el-form-item>
      <el-form-item label="验证数据集"><el-select v-model="datasetId" filterable placeholder="选择数据集"><el-option v-for="dataset in datasets" :key="dataset.id" :label="`${dataset.name}（${dataset.image_count} 张）`" :value="dataset.id" /></el-select><small class="field-help">优先使用 val 划分；没有验证划分时使用全部影像。</small></el-form-item>
      <el-form-item label="验证图片数量"><el-select v-model="sampleLimit"><el-option label="20 张（快速检查）" :value="20"/><el-option label="50 张（推荐）" :value="50"/><el-option label="100 张" :value="100"/><el-option label="200 张" :value="200"/><el-option label="全部图片" :value="0"/></el-select><small class="field-help">系统会从验证集中均匀抽样，避免只选择排序靠前的图片。</small></el-form-item></el-form>
      <div v-if="job.running||job.finished||job.error" class="job-progress"><div><span>{{ job.message }}</span><strong>{{ job.completed||0 }}/{{ job.total||'—' }}</strong></div><el-progress :percentage="jobPercentage" :status="job.error?'exception':(job.finished?'success':undefined)"/><pre v-if="job.error">{{ job.error }}</pre></div>
      <template #footer><el-button :disabled="job.running" @click="uploadVisible=false">关闭</el-button><el-button type="primary" :loading="job.running||uploading" :disabled="!uploadModelId||!datasetId" @click="submit">{{ job.running?'生成中':'生成诊断数据' }}</el-button></template>
    </el-dialog>

    <el-dialog v-model="detailVisible" title="样本诊断详情" width="900px">
      <div v-if="selected" class="sample-detail">
        <div class="canvas"><div v-if="selected.image" class="canvas-stage" :style="stageStyle(selected)"><img :src="absoluteUrl(selected.image)"><svg :viewBox="`0 0 ${selected.width||imageWidth} ${selected.height||imageHeight}`" preserveAspectRatio="none"><rect v-for="(box,index) in truthBoxes(selected)" :key="`g${index}`" v-bind="rect(box.bbox,selected)" class="truth"/><rect v-for="(box,index) in predictionBoxes(selected)" :key="`p${index}`" v-bind="rect(box.bbox,selected)" class="prediction"/></svg></div></div>
        <div class="legend"><span><i class="green"/>真实框</span><span><i class="red"/>预测框</span><b>{{ errorSummary(selected) }}</b></div>
        <div class="facts"><div><small>类别</small><strong>{{ selected.class_name || '—' }}</strong></div><div><small>置信度</small><strong>{{ number(selected.confidence) }}</strong></div><div><small>IoU</small><strong>{{ number(selected.iou) }}</strong></div><div><small>模型</small><strong>{{ modelName(selected.model_id) }}</strong></div></div>
        <p>同图完整检测结果已叠加显示；绿色为真实标注，红色为当前模型预测。可切换左侧模型查看同一数据集的其他模型结果。</p>
      </div>
    </el-dialog>
  </section>
</template>

<script>
import global from '@/global'
import { generateModelDiagnostics, getModelDiagnostics, getModelDiagnosticsStatus } from '@/api/modelRank'
import { getDatasets } from '@/api/dataset'
export default {
  name:'ErrorDiagnosisCenter', props:{models:{type:Array,default:()=>[]}}, emits:['refresh'],
  data(){return{modelId:'',className:'',type:'all',selected:null,remoteSamples:[],remoteTotal:0,diagnosisImageCount:0,diagnosisCounts:{},diagnosisClasses:[],uploadVisible:false,uploadModelId:'',datasetId:'',sampleLimit:50,datasets:[],uploading:false,job:{running:false,finished:false,total:0,completed:0,message:'',error:''},pollTimer:null,imageWidth:1000,imageHeight:1000,types:[{key:'all',label:'全部影像'},{key:'tp',label:'正确检测 TP'},{key:'fn',label:'漏检 FN'},{key:'fp',label:'误检 FP'},{key:'class_error',label:'类别判断错误'},{key:'localization',label:'定位不准确'},{key:'duplicate',label:'重复检测'},{key:'low_confidence',label:'置信度过低'},{key:'dense_miss',label:'密集目标漏检'},{key:'small_miss',label:'小目标漏检'}]}},
  computed:{
    samples(){return this.remoteSamples},
    classes(){return this.diagnosisClasses},
    filtered(){return this.remoteSamples},
    supportedModels(){return this.models.filter(model=>/\.pt$/i.test(model.filename||model.stored_filename||''))},
    jobPercentage(){return this.job.total?Math.min(100,Math.round((this.job.completed||0)/this.job.total*100)):0},
    reasons(){const groups=[{key:'fn',label:'漏检',k:['fn','dense_miss','small_miss']},{key:'localization',label:'定位偏差',k:['localization']},{key:'class_error',label:'类别混淆',k:['class_error']},{key:'duplicate',label:'重复框',k:['duplicate']},{key:'fp',label:'背景误检',k:['fp']}];const total=groups.reduce((sum,g)=>sum+g.k.reduce((n,k)=>n+(this.diagnosisCounts[k]||0),0),0)||1;return groups.map(g=>({...g,percent:Math.round(g.k.reduce((n,k)=>n+(this.diagnosisCounts[k]||0),0)/total*100)}))},
    detailVisible:{get(){return Boolean(this.selected)},set(value){if(!value)this.selected=null}}
  },
  watch:{models:{immediate:true,handler(value){if(!this.modelId&&value.length)this.modelId=value[0].id;if(!this.uploadModelId&&this.supportedModels.length)this.uploadModelId=this.supportedModels[0].id}},modelId(){this.loadSamples()},type(){this.loadSamples()},className(){this.loadSamples()}},
  beforeUnmount(){if(this.pollTimer)clearTimeout(this.pollTimer)},
  methods:{
    count(key){return key==='all'?this.diagnosisImageCount:(this.diagnosisCounts[key]||0)},typeLabel(key){return(this.types.find(item=>item.key===key)||{}).label||key},number(value){return value===null||value===undefined||value===''?'—':Number(value).toFixed(2)},modelName(id){return(this.models.find(item=>item.id===id)||{}).name||'—'},
    absoluteUrl(url){if(!url)return'';if(/^https?:/.test(url))return url;return `${(global.BASEURL||'').replace(/\/$/,'')}/${String(url).replace(/^\//,'')}`},stageStyle(sample){const width=Number(sample.width)||this.imageWidth,height=Number(sample.height)||this.imageHeight,ratio=width/height;return{aspectRatio:`${width} / ${height}`,width:`min(100%, ${Math.max(1,ratio*70)}vh)`}},rect(box,sample){const maxWidth=Number(sample&&sample.width)||this.imageWidth,maxHeight=Number(sample&&sample.height)||this.imageHeight,x1=Math.max(0,Math.min(maxWidth,Number(box&&box[0])||0)),y1=Math.max(0,Math.min(maxHeight,Number(box&&box[1])||0)),x2=Math.max(0,Math.min(maxWidth,Number(box&&box[2])||0)),y2=Math.max(0,Math.min(maxHeight,Number(box&&box[3])||0));return{x:Math.min(x1,x2),y:Math.min(y1,y2),width:Math.abs(x2-x1),height:Math.abs(y2-y1)}},uniqueBoxes(boxes){const seen=new Set();return boxes.filter(box=>{if(!box||!box.bbox)return false;const key=`${box.class_id??box.class??''}:${box.bbox.map(value=>Number(value).toFixed(2)).join(',')}`;if(seen.has(key))return false;seen.add(key);return true})},truthBoxes(sample){return this.uniqueBoxes(sample.errors?sample.errors.map(error=>error.ground_truth):sample.ground_truth?[sample.ground_truth]:[])},predictionBoxes(sample){return this.uniqueBoxes(sample.errors?sample.errors.map(error=>error.prediction):sample.prediction?[sample.prediction]:[])},errorSummary(sample){const errors=sample.errors||[sample];const labels=[...new Set(errors.map(error=>this.typeLabel(error.type)))];return `${errors.length} 处问题 · ${labels.join('、')}`},
    async openGenerate(){this.uploadVisible=true;if(!this.datasets.length){try{const res=await getDatasets();this.datasets=res.data.data||[];if(!this.datasetId&&this.datasets.length)this.datasetId=this.datasets[0].id}catch(error){this.$message.error('数据集列表加载失败')}}},
    async loadSamples(){if(!this.modelId)return;try{const res=await getModelDiagnostics(this.$route.params.id,this.modelId,{type:this.type,class_name:this.className,page:1,limit:120});const data=res.data.data||{};this.remoteSamples=data.samples||[];this.remoteTotal=data.total||0;this.diagnosisImageCount=data.image_count||0;this.diagnosisCounts=data.counts||{};this.diagnosisClasses=data.classes||[]}catch(error){this.remoteSamples=[];this.remoteTotal=0;this.diagnosisImageCount=0}},
    async submit(){if(!this.uploadModelId||!this.datasetId)return this.$message.warning('请选择模型和验证数据集');this.uploading=true;try{const res=await generateModelDiagnostics(this.$route.params.id,this.uploadModelId,this.datasetId,this.sampleLimit);this.job=res.data.data||{};this.pollStatus()}finally{this.uploading=false}},
    async pollStatus(){if(this.pollTimer)clearTimeout(this.pollTimer);try{const res=await getModelDiagnosticsStatus(this.$route.params.id,this.uploadModelId,this.datasetId);this.job=res.data.data||{};if(this.job.finished){this.$message.success('诊断数据生成完成');this.modelId=this.uploadModelId;await this.loadSamples();this.$emit('refresh');return}}catch(error){return}if(this.job.running)this.pollTimer=setTimeout(()=>this.pollStatus(),2000)}
  }
}
</script>

<style scoped>
.thumb>b{position:absolute;right:8px;bottom:8px;padding:4px 7px;border-radius:10px;color:#fff;background:rgba(20,31,48,.78);font-size:9px}
.job-progress{margin-top:14px;padding:13px;border:1px solid #dbe9f7;border-radius:9px;background:#f5faff}.job-progress>div{display:flex;justify-content:space-between;margin-bottom:8px;color:#52708f;font-size:11px}.job-progress pre{max-height:100px;overflow:auto;margin:8px 0 0;color:#bd4650;font-size:10px;white-space:pre-wrap}.field-help{display:block;margin-top:6px;color:#8995a5;font-size:10px}
.diagnosis{display:grid;grid-template-columns:230px minmax(0,1fr);gap:18px}.diagnosis>aside,.diagnosis>main{border:1px solid #e2e7ee;border-radius:14px;background:#fff}.diagnosis>aside{align-self:start;padding:20px}.side-title strong,.side-title small{display:block}.side-title small{margin:4px 0 18px;color:#8c97a6;font-size:11px}.diagnosis aside>label{display:block;margin:14px 0 7px;color:#5e6a7d;font-size:12px;font-weight:700}.diagnosis aside .el-select{width:100%}.type-list{display:flex;flex-direction:column;gap:3px;margin-bottom:8px}.type-list button{display:flex;justify-content:space-between;padding:8px 9px;border:0;border-radius:7px;background:transparent;color:#697589;font-size:11px;cursor:pointer}.type-list button.active{color:#267fdc;background:#edf6ff}.type-list b{font-size:10px}.count-hint{display:block;margin:0 2px 16px;color:#98a2b1;font-size:9px;line-height:1.5}.diagnosis>main{padding:23px}.diagnosis main>header{display:flex;justify-content:space-between;align-items:center}.diagnosis h2{margin:0;font-size:21px}.diagnosis header p{margin:5px 0;color:#8792a2;font-size:12px}.diagnosis header>span{padding:7px 11px;border-radius:16px;color:#347fce;background:#eef6ff;font-size:11px}.reason-card{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:20px 0;padding:16px;border-radius:11px;background:#f7f9fc}.reason-card div{display:grid;grid-template-columns:1fr auto;gap:6px}.reason-card span,.reason-card b{font-size:10px}.reason-card i{grid-column:1/-1;height:5px;border-radius:4px;background:#e2e8f0}.reason-card em{display:block;height:100%;border-radius:4px;background:#4a91e6}.sample-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:13px}.sample-grid>button{overflow:hidden;padding:0;border:1px solid #e5e9ef;border-radius:10px;background:#fff;text-align:left;cursor:pointer}.thumb{position:relative;display:grid;place-items:center;height:145px;overflow:hidden;color:#9ba5b2;background:#edf1f5}.thumb img{width:100%;height:100%;object-fit:cover}.thumb em{position:absolute;top:8px;left:8px;padding:4px 7px;border-radius:5px;color:#fff;background:#e45757;font-size:9px;font-style:normal}.thumb em.tp{background:#32a776}.sample-grid strong,.sample-grid small{display:block;margin:10px 11px 0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.sample-grid small{margin:4px 11px 11px;color:#8994a4;font-size:9px}.help{padding:10px;border-radius:8px;color:#64748b;background:#f3f7fb;font-size:12px;line-height:1.7}.canvas{position:relative;min-height:420px;overflow:hidden;border-radius:10px;background:#111}.canvas img{display:block;width:100%;max-height:600px;object-fit:contain}.canvas svg{position:absolute;inset:0;width:100%;height:100%}.canvas rect{fill:transparent;stroke-width:4;vector-effect:non-scaling-stroke}.canvas .truth{stroke:#24d17e}.canvas .prediction{stroke:#ff4d5e}.legend{display:flex;align-items:center;gap:17px;margin:13px 0}.legend span{display:flex;align-items:center;gap:6px;font-size:12px}.legend i{width:12px;height:3px}.legend .green{background:#24d17e}.legend .red{background:#ff4d5e}.legend b{margin-left:auto;color:#d54c56}.facts{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.facts div{padding:12px;border-radius:8px;background:#f5f7fa}.facts small,.facts strong{display:block}.facts small{color:#8a95a5;font-size:10px}.facts strong{margin-top:5px}.sample-detail>p{color:#778397;font-size:12px}@media(max-width:900px){.diagnosis{grid-template-columns:1fr}.sample-grid{grid-template-columns:repeat(2,1fr)}.reason-card{grid-template-columns:1fr 1fr}}
.canvas{display:flex;align-items:center;justify-content:center;max-height:70vh}.canvas-stage{position:relative;max-width:100%;max-height:70vh;line-height:0}.canvas-stage img{display:block;width:100%!important;height:100%;max-height:none!important;object-fit:fill!important}.canvas-stage svg{position:absolute;inset:0;width:100%;height:100%}
</style>
