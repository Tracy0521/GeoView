<template>
  <main v-if="project" class="detail-page">
    <header class="project-header">
      <div class="title-block"><span class="project-mark">{{ project.name.slice(0,1).toUpperCase() }}</span><div><div class="back" @click="$router.push('/model-ranking')">← 返回模型项目</div><h1>{{ project.name }}</h1></div></div>
      <button class="dark-button" @click="uploadVisible=true">＋ 增加模型</button>
      <p class="meta">◇ {{ project.models.length }} 个模型 · ✓ {{ project.models.length }} 个已保存 · {{ formatSize(totalSize) }} · 更新于 {{ formatDate(project.updated_at) }}</p>
      <p class="description">{{ project.description || '保存已经训练完成的模型，并在同一图表中比较它们的指标表现。' }}</p>
    </header>

    <div class="toolbar"><el-input v-model="keyword" clearable placeholder="搜索模型…" /><span>{{ selected.length }} 个已选择</span></div>
    <div class="workspace">
      <aside class="model-panel">
        <div class="panel-head"><strong>◇ 模型</strong><small>{{ selected.length }} 个已选</small></div>
        <label class="select-all"><input type="checkbox" :checked="allSelected" @change="toggleAll"> {{ allSelected ? '取消全选' : '选择全部' }}</label>
        <div class="model-group">⌄ 已训练模型 <span>{{ filteredModels.length }}</span></div>
        <label v-for="(model,index) in filteredModels" :key="model.id" class="model-row">
          <input v-model="selected" type="checkbox" :value="model.id">
          <i :style="{background: colors[index % colors.length]}" />
          <span><strong>{{ model.name }}</strong><small>{{ model.score ? model.score + ' 分 · ' : '' }}{{ formatSize(model.size) }}</small></span>
          <button title="删除模型" @click.prevent="remove(model)">×</button>
        </label>
        <div class="upload-box" @click="uploadVisible=true"><b>⇧</b><span>添加已训练模型</span><small>.pt / .pth / .pdparams / .onnx</small></div>
      </aside>

      <section class="charts-panel">
        <div class="compare-tip"><strong>指标对比</strong><span v-for="line in legend" :key="line.id"><i :style="{background:line.color}" />{{ line.name }}</span><small v-if="!legend.length">请在左侧勾选模型</small></div>
        <div class="section-card">
          <button class="section-title" @click="open.metrics=!open.metrics"><span>{{ open.metrics ? '⌄' : '›' }} 指标 <small>(4/4)</small></span><b>•••</b></button>
          <div v-show="open.metrics" class="chart-grid two">
            <MetricChart v-for="metric in metricCharts" :key="metric.key" :title="metric.title" :lines="chartLines(metric.key)" />
          </div>
        </div>
        <div class="section-card">
          <button class="section-title" @click="open.loss=!open.loss"><span>{{ open.loss ? '⌄' : '›' }} 损失 <small>(3/3)</small></span><b>•••</b></button>
          <div v-show="open.loss" class="chart-grid three">
            <MetricChart v-for="metric in lossCharts" :key="metric.key" :title="metric.title" :lines="chartLines(metric.key)" />
          </div>
        </div>
      </section>
    </div>

    <el-dialog v-model="uploadVisible" title="增加已训练模型" width="560px" :close-on-click-modal="false">
      <p class="dialog-note">这里只保存已经完成训练的模型，不提供云训练功能。</p>
      <el-form label-position="top">
        <el-form-item label="模型名称"><el-input v-model="uploadForm.name" placeholder="例如：YOLOv8 建筑物检测" /></el-form-item>
        <div class="form-row"><el-form-item label="框架"><el-select v-model="uploadForm.framework"><el-option label="PyTorch" value="PyTorch"/><el-option label="PaddlePaddle" value="PaddlePaddle"/><el-option label="ONNX" value="ONNX"/></el-select></el-form-item><el-form-item label="综合得分（可选）"><el-input v-model="uploadForm.score" placeholder="例如：91.5" /></el-form-item></div>
        <el-form-item label="模型文件"><input ref="modelFile" type="file" accept=".pt,.pth,.pdparams,.onnx" @change="pickModel"><div v-if="uploadForm.file" class="file-name">{{ uploadForm.file.name }} · {{ formatSize(uploadForm.file.size) }}</div></el-form-item>
        <el-form-item label="训练结果 results.csv（推荐）"><input type="file" accept=".csv,text/csv" @change="pickResultsCsv"><div v-if="uploadForm.metricsFile" class="file-name">{{ uploadForm.metricsFile.name }} · 将自动读取精确率、召回率、mAP 和损失曲线</div><small class="field-help">请选择 Ultralytics 训练输出目录中的 results.csv。</small></el-form-item>
        <el-form-item label="指标 JSON（可选，兼容其他训练框架）"><el-input v-model="uploadForm.metrics" type="textarea" :rows="5" placeholder='{"precision":[0.4,0.6],"recall":[0.3,0.5],"map50":[0.2,0.4],"map5095":[0.1,0.3],"box_loss":[1.2,0.8]}' /><input type="file" accept=".json" @change="loadMetricsFile"></el-form-item>
      </el-form>
      <template #footer><el-button @click="uploadVisible=false">取消</el-button><el-button type="primary" :loading="uploading" @click="upload">保存模型</el-button></template>
    </el-dialog>
  </main>
</template>

<script>
import MetricChart from '@/components/MetricChart.vue'
import { addModel, getProject, removeModel } from '@/api/modelRank'
export default {
  name: 'ModelProjectDetail', components: { MetricChart },
  data: () => ({ project:null, keyword:'', selected:[], uploadVisible:false, uploading:false, colors:['#18a4c4','#8b5bd9','#ed8b2f','#35a86c','#ec5269','#527ce8'], open:{metrics:true,loss:true}, uploadForm:{name:'',framework:'PyTorch',score:'',file:null,metricsFile:null,metrics:''}, metricCharts:[{key:'precision',title:'精确率（Precision）'},{key:'recall',title:'召回率（Recall）'},{key:'map50',title:'mAP@50'},{key:'map5095',title:'mAP@50-95'}], lossCharts:[{key:'box_loss',title:'定位损失（box_loss）'},{key:'cls_loss',title:'分类损失（cls_loss）'},{key:'dfl_loss',title:'分布焦点损失（dfl_loss）'}] }),
  computed: {
    filteredModels(){ return this.project.models.filter(item=>item.name.toLowerCase().includes(this.keyword.toLowerCase())) },
    allSelected(){ return this.filteredModels.length>0 && this.filteredModels.every(item=>this.selected.includes(item.id)) },
    totalSize(){ return this.project.models.reduce((sum,item)=>sum+item.size,0) },
    legend(){ return this.project.models.filter(item=>this.selected.includes(item.id)).map(item=>({id:item.id,name:item.name,color:this.modelColor(item.id)})) }
  },
  mounted(){ this.load() },
  methods: {
    async load(){ const res=await getProject(this.$route.params.id); this.project=res.data.data; this.selected=this.project.models.map(item=>item.id) },
    modelColor(id){ const index=this.project.models.findIndex(item=>item.id===id); return this.colors[index%this.colors.length] },
    chartLines(key){ return this.project.models.filter(item=>this.selected.includes(item.id) && item.metrics && item.metrics[key] && item.metrics[key].length).map(item=>({id:item.id,name:item.name,color:this.modelColor(item.id),values:item.metrics[key]})) },
    toggleAll(){ const ids=this.filteredModels.map(item=>item.id); this.selected=this.allSelected?this.selected.filter(id=>!ids.includes(id)):[...new Set([...this.selected,...ids])] },
    pickModel(event){ this.uploadForm.file=event.target.files[0]; if(this.uploadForm.file && !this.uploadForm.name) this.uploadForm.name=this.uploadForm.file.name.replace(/\.[^.]+$/,'') },
    pickResultsCsv(event){ this.uploadForm.metricsFile=event.target.files[0] || null },
    loadMetricsFile(event){ const file=event.target.files[0]; if(!file)return; const reader=new FileReader(); reader.onload=()=>{this.uploadForm.metrics=reader.result}; reader.readAsText(file) },
    async upload(){
      if(!this.uploadForm.file)return this.$message.warning('请选择已训练好的模型文件')
      let metrics={}; if(this.uploadForm.metrics.trim()){try{metrics=JSON.parse(this.uploadForm.metrics)}catch(e){return this.$message.error('指标 JSON 格式不正确')}}
      const data=new FormData(); data.append('model',this.uploadForm.file); data.append('name',this.uploadForm.name); data.append('framework',this.uploadForm.framework); data.append('score',this.uploadForm.score); data.append('metrics',JSON.stringify(metrics)); if(this.uploadForm.metricsFile)data.append('metrics_file',this.uploadForm.metricsFile); this.uploading=true
      try{await addModel(this.project.id,data); this.uploadVisible=false; this.uploadForm={name:'',framework:'PyTorch',score:'',file:null,metricsFile:null,metrics:''}; await this.load(); this.$message.success('模型和训练指标已保存')}finally{this.uploading=false}
    },
    async remove(model){ try{await this.$confirm(`确认删除模型“${model.name}”吗？`,'删除模型',{type:'warning'}); await removeModel(this.project.id,model.id); await this.load()}catch(e){/* 用户取消 */} },
    formatSize(size){return size<1048576?`${(size/1024).toFixed(1)} KB`:`${(size/1048576).toFixed(1)} MB`}, formatDate(value){return value?value.replace('T',' '):'—'}
  }
}
</script>

<style scoped>
.detail-page{min-height:calc(100vh - 60px);padding:30px;background:#f8f9fb;box-sizing:border-box;color:#182132;font-family:"Microsoft YaHei",sans-serif}.project-header{position:relative;margin-bottom:25px}.title-block{display:flex;align-items:center;gap:14px}.project-mark{display:grid;place-items:center;width:50px;height:50px;border-radius:11px;background:#f3484e;color:#fff;font-size:20px;font-weight:800}.back{color:#498ee6;font-size:12px;cursor:pointer;margin-bottom:4px}h1{font-size:28px;margin:0}.dark-button{position:absolute;right:0;top:8px;padding:12px 18px;border:0;border-radius:9px;background:#151515;color:#fff;font-weight:700;cursor:pointer}.meta,.description{margin:9px 0 0;color:#7c8696;font-size:13px}.description{font-size:14px}.toolbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px}.toolbar .el-input{width:250px}.toolbar span{color:#8690a0;font-size:13px}.workspace{display:grid;grid-template-columns:270px minmax(0,1fr);gap:18px}.model-panel,.section-card,.compare-tip{border:1px solid #e2e6ec;background:#fff;border-radius:13px;box-shadow:0 3px 12px rgba(30,45,70,.04)}.model-panel{padding-bottom:14px;align-self:start}.panel-head{display:flex;justify-content:space-between;padding:18px;border-bottom:1px solid #ebedf1}.panel-head small{color:#8993a2}.select-all{display:block;padding:13px 18px;color:#697587;font-size:13px}.model-group{padding:8px 18px;color:#697587;font-size:13px;font-weight:700}.model-group span{float:right}.model-row{display:flex;align-items:center;gap:9px;margin:0 10px 7px;padding:11px;border-radius:9px;background:#f5f6f8}.model-row i{width:11px;height:11px;border-radius:50%}.model-row span{min-width:0;flex:1}.model-row strong,.model-row small{display:block;overflow:hidden;text-overflow:ellipsis}.model-row small{margin-top:4px;color:#8993a2;font-size:11px}.model-row button{border:0;background:transparent;color:#a0a8b4;font-size:20px;cursor:pointer}.upload-box{display:flex;flex-direction:column;align-items:center;gap:6px;margin:12px 10px 0;padding:20px 6px;border:2px dashed #d8dce2;border-radius:10px;color:#727d8d;cursor:pointer}.upload-box b{font-size:26px}.upload-box small{font-size:10px}.charts-panel{min-width:0}.compare-tip{display:flex;align-items:center;gap:14px;padding:14px 18px;margin-bottom:13px}.compare-tip span{display:flex;align-items:center;gap:5px;color:#657184;font-size:12px}.compare-tip i{width:9px;height:9px;border-radius:50%}.compare-tip small{color:#98a1af}.section-card{margin-bottom:14px;overflow:hidden}.section-title{display:flex;width:100%;justify-content:space-between;padding:18px 22px;border:0;background:#fff;font-size:18px;font-weight:700;cursor:pointer}.section-title small{color:#8791a0;font-size:13px}.chart-grid{display:grid;gap:13px;padding:0 14px 14px}.chart-grid.two{grid-template-columns:repeat(2,minmax(0,1fr))}.chart-grid.three{grid-template-columns:repeat(3,minmax(0,1fr))}.dialog-note{margin-top:-8px;color:#7f8998;font-size:13px}.form-row{display:grid;grid-template-columns:1fr 1fr;gap:14px}.form-row .el-select{width:100%}.file-name{margin-top:7px;color:#438fe9;font-size:12px}@media(max-width:1100px){.chart-grid.three{grid-template-columns:1fr 1fr}}@media(max-width:780px){.detail-page{padding:20px 14px}.workspace{grid-template-columns:1fr}.chart-grid.two,.chart-grid.three{grid-template-columns:1fr}.dark-button{position:static;margin-top:18px}.compare-tip{flex-wrap:wrap}}
.field-help{display:block;margin-top:6px;color:#8c96a5;font-size:12px}
</style>
