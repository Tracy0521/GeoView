<template>
  <main v-if="project" class="detail-page">
    <header class="project-header">
      <div class="title-block"><span class="project-mark">{{ project.name.slice(0,1).toUpperCase() }}</span><div><div class="back" @click="$router.push('/model-ranking')">← 返回模型项目</div><h1>{{ project.name }}</h1></div></div>
      <button class="dark-button" @click="openUploadDialog">＋ 增加模型</button>
      <p class="meta">◇ {{ project.models.length }} 个模型 · ✓ {{ project.models.length }} 个已保存 · {{ formatSize(totalSize) }} · 更新于 {{ formatDate(project.updated_at) }}</p>
      <p class="description">{{ project.description || '保存已经训练完成的模型，并在同一图表中比较它们的指标表现。' }}</p>
    </header>

    <nav class="detail-tabs" aria-label="项目页面切换">
      <button :class="{active:activeView==='charts'}" @click="switchView('charts')">指标对比</button>
      <button :class="{active:activeView==='ranking'}" @click="switchView('ranking')">数据排行</button>
      <button :class="{active:activeView==='classAnalysis'}" @click="switchView('classAnalysis')">类别分析</button>
    </nav>

    <div v-show="activeView==='charts'" class="charts-view">
    <div class="toolbar"><el-input v-model="keyword" clearable placeholder="搜索模型…" /><span>{{ selected.length }} 个已选择</span></div>
    <div class="workspace">
      <aside class="model-panel">
        <div class="panel-head"><strong>◇ 模型</strong><small>{{ selected.length }} 个已选</small></div>
        <label class="select-all"><input type="checkbox" :checked="allSelected" @change="toggleAll"> {{ allSelected ? '取消全选' : '选择全部' }}</label>
        <div class="model-group">⌄ 已训练模型 <span>{{ filteredModels.length }}</span></div>
        <label v-for="(model,index) in filteredModels" :key="model.id" class="model-row">
          <input v-model="selected" type="checkbox" :value="model.id">
          <i :style="{background: colors[index % colors.length]}" />
          <span class="model-info" title="点击修改模型" @click.prevent.stop="openEdit(model)"><strong>{{ model.name }}</strong><small>{{ model.score ? model.score + ' 分 · ' : '' }}{{ formatSize(model.size) }}</small><small v-if="model.source_type==='remote'" class="source-meta">{{ model.source_server }} · 已同步<br>{{ model.remote_path }}</small></span>
          <button class="edit-button" title="修改模型" @click.prevent.stop="openEdit(model)">✎</button>
          <button title="删除模型" @click.prevent.stop="remove(model)">×</button>
        </label>
        <div class="upload-box" @click="openUploadDialog"><b>⇧</b><span>添加已训练模型</span><small>本地上传 / 远程服务器</small></div>
      </aside>

      <section class="charts-panel">
        <div class="compare-tip"><strong>指标对比</strong><span v-for="line in legend" :key="line.id"><i :style="{background:line.color}" />{{ line.name }}</span><small v-if="!legend.length">请在左侧勾选模型</small></div>
        <div class="section-card">
          <button class="section-title" @click="open.metrics=!open.metrics"><span>{{ open.metrics ? '⌄' : '›' }} 指标 <small>(4/4)</small></span><b>•••</b></button>
          <div v-show="open.metrics" class="chart-grid two">
            <MetricChart v-for="metric in metricCharts" :key="metric.key" :title="metric.title" :lines="chartLines(metric.key)" />
            <SmallSampleChart :datasets="smallSampleDatasets" />
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
    </div>

    <section v-show="activeView==='ranking'" class="ranking-panel">
      <div class="ranking-head"><div><h2>模型数据排行</h2><p>当前项目共 {{ projectModels.length }} 个模型，点击表头切换升序或降序。</p></div><el-input v-model="keyword" clearable placeholder="搜索模型或框架…" /></div>
      <div class="ranking-table-wrap"><table class="ranking-table" :style="{minWidth:`${Math.max(970,(rankingColumns.length+1)*108)}px`}">
        <thead><tr><th class="rank-column">排名</th><th v-for="column in rankingColumns" :key="column.key" @click="changeSort(column.key)">{{ column.label }} <span>{{ sortMark(column.key) }}</span></th></tr></thead>
        <tbody>
          <tr v-for="(row,index) in pagedRankingRows" :key="row.id"><td class="rank-number">{{ (rankingPage-1)*rankingPageSize+index+1 }}</td><td v-for="column in rankingColumns" :key="column.key" :class="{'rank-model':column.type==='model','primary-metric':column.key==='map5095','class-metric':column.type==='classMetric'}"><button v-if="column.type==='model'" @click="openEdit(row.model)">{{ row.name }}</button><template v-else>{{ formatRankingValue(row,column) }}</template></td></tr>
          <tr v-if="!pagedRankingRows.length"><td :colspan="rankingColumns.length+1" class="ranking-empty">暂无可排行的模型数据</td></tr>
        </tbody>
      </table></div>
      <div class="ranking-footer"><span>共 {{ sortedRankingRows.length }} 个模型</span><div class="ranking-pagination"><button :disabled="rankingPage===1" @click="rankingPage--">上一页</button><button v-for="number in rankingPages" :key="number" :class="{active:number===rankingPage}" @click="rankingPage=number">{{ number }}</button><button :disabled="rankingPage===rankingTotalPages" @click="rankingPage++">下一页</button></div></div>
    </section>

    <ClassMetricAnalysis v-show="activeView==='classAnalysis'" :models="projectModels" :colors="colors" />

    <el-dialog v-model="uploadVisible" title="增加已训练模型" width="720px" :close-on-click-modal="false">
      <p class="dialog-note">这里只保存已经完成训练的模型，不提供云训练功能。</p>
      <el-radio-group v-model="uploadSource" class="source-switch" @change="changeUploadSource">
        <el-radio-button label="local">本地上传</el-radio-button>
        <el-radio-button label="remote">远程服务器</el-radio-button>
      </el-radio-group>
      <el-form v-if="uploadSource==='local'" label-position="top">
        <el-form-item label="模型名称"><el-input v-model="uploadForm.name" placeholder="例如：YOLOv8 建筑物检测" /></el-form-item>
        <div class="form-row"><el-form-item label="框架"><el-select v-model="uploadForm.framework"><el-option label="PyTorch" value="PyTorch"/><el-option label="PaddlePaddle" value="PaddlePaddle"/><el-option label="ONNX" value="ONNX"/></el-select></el-form-item><el-form-item label="综合得分（可选）"><el-input v-model="uploadForm.score" placeholder="例如：91.5" /></el-form-item></div>
        <el-form-item label="模型文件"><input ref="modelFile" type="file" accept=".pt,.pth,.pdparams,.onnx" @change="pickModel"><div v-if="uploadForm.file" class="file-name">{{ uploadForm.file.name }} · {{ formatSize(uploadForm.file.size) }}</div></el-form-item>
        <el-form-item label="训练结果 results.csv（推荐）"><input type="file" accept=".csv,text/csv" @change="pickResultsCsv"><div v-if="uploadForm.metricsFile" class="file-name">{{ uploadForm.metricsFile.name }} · 将自动读取精确率、召回率、mAP 和损失曲线</div><small class="field-help">请选择 Ultralytics 训练输出目录中的 results.csv。</small></el-form-item>
        <el-form-item label="指标 JSON（可多选，自动合并）"><el-input v-model="uploadForm.metrics" type="textarea" :rows="5" placeholder='{"small_sample":[...],"class_metrics":[...]}' /><input type="file" accept=".json,application/json" multiple @change="loadMetricsFile"><small class="field-help">可以同时选择小样本 JSON 和类别指标 JSON，系统会按顶层字段自动合并；缺少 F1 时会自动计算。</small></el-form-item>
      </el-form>
      <div v-else class="remote-source">
        <div class="remote-toolbar"><div><strong>远程训练结果</strong><small>仅扫描 output/*/weights/best.pt</small></div><el-button size="small" :loading="remoteLoading" @click="loadRemoteModels">刷新</el-button></div>
        <div v-if="remoteServers.length" class="server-list">
          <span v-for="server in remoteServers" :key="server.id" :class="['server-chip',server.status]"><i />{{ server.name }}：{{ server.status==='online' ? `${server.model_count} 个模型` : server.message }}</span>
        </div>
        <div v-loading="remoteLoading" class="remote-model-list">
          <label v-for="model in remoteModels" :key="`${model.server_id}:${model.remote_path}`" :class="['remote-model-row',{selected:selectedRemotePath===model.remote_path&&selectedRemoteServer===model.server_id,disabled:model.sync_status==='synced'}]">
            <input v-model="selectedRemoteKey" type="radio" :value="`${model.server_id}::${model.remote_path}`" :disabled="model.sync_status==='synced'">
            <span class="remote-main"><strong>{{ model.name }}</strong><small>{{ model.server_name }} · {{ formatSize(model.size) }}</small><small class="remote-path">{{ model.remote_path }}</small><small :class="['results-state',{missing:!model.has_results}]">{{ model.has_results ? `results.csv · ${formatSize(model.results_size)}` : '未找到 results.csv' }}</small></span>
            <em :class="model.sync_status">{{ model.sync_status==='synced' ? '已同步' : '可同步' }}</em>
          </label>
          <div v-if="!remoteLoading&&!remoteModels.length" class="remote-empty">暂无可用的 best.pt，请检查远程实例状态和 output 目录。</div>
        </div>
      </div>
      <template #footer><el-button @click="uploadVisible=false">取消</el-button><el-button type="primary" :loading="uploading" :disabled="uploadSource==='remote'&&!selectedRemoteModel" @click="upload">{{ uploadSource==='remote' ? '同步到本地模型库' : '保存模型' }}</el-button></template>
    </el-dialog>

    <el-dialog v-model="editVisible" title="修改已导入模型" width="560px" :close-on-click-modal="false">
      <p class="dialog-note">可更新模型信息和指标数据，模型权重文件保持不变。</p>
      <el-form label-position="top">
        <el-form-item label="模型名称"><el-input v-model="editForm.name" maxlength="80" /></el-form-item>
        <div class="form-row"><el-form-item label="框架"><el-select v-model="editForm.framework"><el-option label="PyTorch" value="PyTorch"/><el-option label="PaddlePaddle" value="PaddlePaddle"/><el-option label="ONNX" value="ONNX"/></el-select></el-form-item><el-form-item label="综合得分（可选）"><el-input v-model="editForm.score" /></el-form-item></div>
        <div class="form-row"><el-form-item label="训练日期"><el-date-picker v-model="editForm.trainingDate" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" /></el-form-item><el-form-item label="训练轮数"><el-input v-model="editForm.trainingEpochs" type="number" min="1" step="1" placeholder="例如：100" /></el-form-item></div>
        <el-form-item label="重新导入 results.csv（可选）"><input type="file" accept=".csv,text/csv" @change="pickEditResultsCsv"><div v-if="editForm.metricsFile" class="file-name">{{ editForm.metricsFile.name }} · 将更新训练曲线</div></el-form-item>
        <el-form-item label="指标 JSON（可多选，自动合并）"><el-input v-model="editForm.metrics" type="textarea" :rows="8" /><input type="file" accept=".json,application/json" multiple @change="loadEditMetricsFile"><small class="field-help">可同时选择 small_sample 和 class_metrics 两个 JSON，合并后仍可直接修改内容。</small></el-form-item>
      </el-form>
      <template #footer><el-button @click="editVisible=false">取消</el-button><el-button type="primary" :loading="editing" @click="saveEdit">保存修改</el-button></template>
    </el-dialog>
  </main>
</template>

<script>
import MetricChart from '@/components/MetricChart.vue'
import SmallSampleChart from '@/components/SmallSampleChart.vue'
import ClassMetricAnalysis from '@/components/ClassMetricAnalysis.vue'
import { addModel, getProject, getRemoteModels, importRemoteModel, removeModel, updateModel } from '@/api/modelRank'
export default {
  name: 'ModelProjectDetail', components: { MetricChart, SmallSampleChart, ClassMetricAnalysis },
  data: () => ({ project:null, activeView:'charts', keyword:'', selected:[], rankingSortKey:'map5095', rankingSortDirection:'desc', rankingPage:1, rankingPageSize:10, uploadVisible:false, uploading:false, uploadSource:'local', remoteLoading:false, remoteServers:[], remoteModels:[], selectedRemoteKey:'', editVisible:false, editing:false, colors:['#18a4c4','#8b5bd9','#ed8b2f','#35a86c','#ec5269','#527ce8'], open:{metrics:true,loss:true}, uploadForm:{name:'',framework:'PyTorch',score:'',file:null,metricsFile:null,metrics:''}, editForm:{id:'',name:'',framework:'PyTorch',score:'',trainingDate:'',trainingEpochs:'',metricsFile:null,metrics:''}, baseRankingColumns:[{key:'name',label:'模型',type:'model'},{key:'framework',label:'框架',type:'text'},{key:'precision',label:'精确率',type:'metric'},{key:'recall',label:'召回率',type:'metric'},{key:'map50',label:'mAP@50',type:'metric'},{key:'map5095',label:'mAP@50-95',type:'metric'}], trailingRankingColumns:[{key:'score',label:'得分',type:'text'},{key:'epochs',label:'轮数',type:'text'},{key:'date',label:'日期',type:'text'}], metricCharts:[{key:'precision',title:'精确率（Precision）'},{key:'recall',title:'召回率（Recall）'},{key:'map50',title:'mAP@50'},{key:'map5095',title:'mAP@50-95'}], lossCharts:[{key:'box_loss',title:'定位损失（box_loss）'},{key:'cls_loss',title:'分类损失（cls_loss）'},{key:'dfl_loss',title:'分布焦点损失（dfl_loss）'}] }),
  computed: {
    projectModels(){return this.project&&Array.isArray(this.project.models)?this.project.models:[]},
    filteredModels(){ return this.projectModels.filter(item=>item.name.toLowerCase().includes(this.keyword.toLowerCase())) },
    allSelected(){ return this.filteredModels.length>0 && this.filteredModels.every(item=>this.selected.includes(item.id)) },
    totalSize(){ return this.projectModels.reduce((sum,item)=>sum+item.size,0) },
    legend(){ return this.projectModels.filter(item=>this.selected.includes(item.id)).map(item=>({id:item.id,name:item.name,color:this.modelColor(item.id)})) },
    smallSampleDatasets(){return this.projectModels.filter(item=>this.selected.includes(item.id)&&item.metrics&&Array.isArray(item.metrics.small_sample)&&item.metrics.small_sample.length).map(item=>({id:item.id,name:item.name,color:this.modelColor(item.id),values:item.metrics.small_sample}))},
    classRankingColumns(){const classes=[];this.projectModels.forEach(model=>(model.metrics&&Array.isArray(model.metrics.small_sample)?model.metrics.small_sample:[]).forEach(item=>{if(item.class&&!classes.some(current=>current.label===item.class))classes.push({key:`class::${item.class}`,label:item.class,type:'classMetric',instances:Number(item.instances)||0})}));return classes.sort((left,right)=>left.instances-right.instances||left.label.localeCompare(right.label))},
    rankingColumns(){return[...this.baseRankingColumns,...this.classRankingColumns,...this.trailingRankingColumns]},
    rankingRows(){return this.projectModels.map(model=>{const row={id:model.id,model,name:model.name,framework:model.framework||'—',precision:this.lastMetric(model,'precision'),recall:this.lastMetric(model,'recall'),map50:this.lastMetric(model,'map50'),map5095:this.lastMetric(model,'map5095'),score:model.score!==''&&Number.isFinite(Number(model.score))?Number(model.score):(model.score||null),epochs:this.modelEpochs(model),date:model.training_date||(model.created_at||'').slice(0,10)};const samples=model.metrics&&Array.isArray(model.metrics.small_sample)?model.metrics.small_sample:[];const isRawBaseline=/raw.*yolo26/i.test(model.name);this.classRankingColumns.forEach(column=>{const item=samples.find(sample=>sample.class===column.label);if(item&&Number.isFinite(Number(item.strpn)))row[column.key]=Number(item.strpn);else if(isRawBaseline){const source=this.projectModels.flatMap(current=>current.metrics&&Array.isArray(current.metrics.small_sample)?current.metrics.small_sample:[]).find(sample=>sample.class===column.label&&Number.isFinite(Number(sample.baseline)));row[column.key]=source?Number(source.baseline):null}else row[column.key]=null});return row})},
    filteredRankingRows(){const word=this.keyword.trim().toLowerCase();return word?this.rankingRows.filter(row=>[row.name,row.framework].some(value=>String(value).toLowerCase().includes(word))):this.rankingRows},
    sortedRankingRows(){return[...this.filteredRankingRows].sort((left,right)=>{const a=left[this.rankingSortKey],b=right[this.rankingSortKey],ae=a===''||a===null||a===undefined,be=b===''||b===null||b===undefined;if(ae||be)return ae===be?0:(ae?1:-1);const result=typeof a==='number'&&typeof b==='number'?a-b:String(a).localeCompare(String(b),'zh-CN',{numeric:true});return this.rankingSortDirection==='asc'?result:-result})},
    rankingTotalPages(){return Math.max(1,Math.ceil(this.sortedRankingRows.length/this.rankingPageSize))},
    pagedRankingRows(){const start=(this.rankingPage-1)*this.rankingPageSize;return this.sortedRankingRows.slice(start,start+this.rankingPageSize)},
    rankingPages(){const start=Math.max(1,Math.min(this.rankingPage-2,this.rankingTotalPages-4));return Array.from({length:Math.min(5,this.rankingTotalPages)},(_,index)=>start+index)},
    selectedRemoteServer(){return this.selectedRemoteKey.split('::',1)[0]||''},
    selectedRemotePath(){return this.selectedRemoteKey.includes('::')?this.selectedRemoteKey.slice(this.selectedRemoteKey.indexOf('::')+2):''},
    selectedRemoteModel(){return this.remoteModels.find(model=>model.server_id===this.selectedRemoteServer&&model.remote_path===this.selectedRemotePath)||null}
  },
  watch:{keyword(){this.rankingPage=1},rankingTotalPages(value){if(this.rankingPage>value)this.rankingPage=value}},
  mounted(){ this.load() },
  methods: {
    async load(){ const res=await getProject(this.$route.params.id); this.project=res.data.data; this.selected=this.project.models.map(item=>item.id) },
    switchView(view){this.activeView=view;this.keyword='';this.rankingPage=1},
    changeSort(key){if(this.rankingSortKey===key)this.rankingSortDirection=this.rankingSortDirection==='asc'?'desc':'asc';else{this.rankingSortKey=key;this.rankingSortDirection='desc'};this.rankingPage=1},
    sortMark(key){return this.rankingSortKey===key?(this.rankingSortDirection==='asc'?'↑':'↓'):'↕'},
    lastMetric(model,key){const values=model.metrics&&model.metrics[key];return Array.isArray(values)&&values.length?Number(values[values.length-1]):null},
    modelEpochs(model){if(model.training_epochs)return Number(model.training_epochs);const epochs=model.metrics&&model.metrics.epochs;if(Array.isArray(epochs)&&epochs.length)return Math.max(...epochs);const lengths=['precision','recall','map50','map5095'].map(key=>model.metrics&&Array.isArray(model.metrics[key])?model.metrics[key].length:0);return Math.max(...lengths)||''},
    formatMetric(value){return Number.isFinite(value)?value.toFixed(4):'—'},
    formatRankingValue(row,column){const value=row[column.key];if(column.type==='metric'||column.type==='classMetric')return this.formatMetric(value);return value===null||value===undefined||value===''?'—':value},
    modelColor(id){ const index=this.project.models.findIndex(item=>item.id===id); return this.colors[index%this.colors.length] },
    chartLines(key){ return this.project.models.filter(item=>this.selected.includes(item.id) && item.metrics && item.metrics[key] && item.metrics[key].length).map(item=>({id:item.id,name:item.name,color:this.modelColor(item.id),values:item.metrics[key],epochs:item.metrics.epochs})) },
    toggleAll(){ const ids=this.filteredModels.map(item=>item.id); this.selected=this.allSelected?this.selected.filter(id=>!ids.includes(id)):[...new Set([...this.selected,...ids])] },
    pickModel(event){ this.uploadForm.file=event.target.files[0]; if(this.uploadForm.file && !this.uploadForm.name) this.uploadForm.name=this.uploadForm.file.name.replace(/\.[^.]+$/,'') },
    openUploadDialog(){this.uploadVisible=true;if(this.uploadSource==='remote')this.loadRemoteModels()},
    changeUploadSource(source){if(source==='remote'&&!this.remoteServers.length)this.loadRemoteModels()},
    async loadRemoteModels(){this.remoteLoading=true;try{const res=await getRemoteModels(this.project.id);this.remoteServers=res.data.data.servers||[];this.remoteModels=res.data.data.models||[];if(this.selectedRemoteModel&&this.selectedRemoteModel.sync_status==='synced')this.selectedRemoteKey=''}finally{this.remoteLoading=false}},
    pickResultsCsv(event){ this.uploadForm.metricsFile=event.target.files[0] || null },
    loadMetricsFile(event){return this.mergeMetricsFiles(event,this.uploadForm)},
    openEdit(model){this.editForm={id:model.id,name:model.name,framework:model.framework||'PyTorch',score:model.score||'',trainingDate:model.training_date||'',trainingEpochs:model.training_epochs||'',metricsFile:null,metrics:JSON.stringify(model.metrics||{},null,2)};this.editVisible=true},
    pickEditResultsCsv(event){this.editForm.metricsFile=event.target.files[0]||null},
    loadEditMetricsFile(event){return this.mergeMetricsFiles(event,this.editForm)},
    readFileText(file){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(reader.error);reader.readAsText(file)})},
    async mergeMetricsFiles(event,target){
      const files=Array.from(event.target.files||[]);if(!files.length)return
      try{const merged=target.metrics.trim()?JSON.parse(target.metrics):{};for(const file of files){const value=JSON.parse(await this.readFileText(file));if(!value||Array.isArray(value)||typeof value!=='object')throw new Error(`${file.name} 顶层必须是 JSON 对象`);Object.assign(merged,value)}target.metrics=JSON.stringify(merged,null,2);this.$message.success(`已合并 ${files.length} 个指标 JSON 文件`)}catch(error){this.$message.error(`JSON 合并失败：${error.message}`)}finally{event.target.value=''}
    },
    async saveEdit(){
      if(!this.editForm.name.trim())return this.$message.warning('请输入模型名称')
      let metrics={};try{metrics=JSON.parse(this.editForm.metrics||'{}')}catch(e){return this.$message.error('指标 JSON 格式不正确')}
      const data=new FormData();data.append('name',this.editForm.name);data.append('framework',this.editForm.framework);data.append('score',this.editForm.score);data.append('training_date',this.editForm.trainingDate||'');data.append('training_epochs',this.editForm.trainingEpochs||'');data.append('metrics',JSON.stringify(metrics));if(this.editForm.metricsFile)data.append('metrics_file',this.editForm.metricsFile);this.editing=true
      try{const res=await updateModel(this.project.id,this.editForm.id,data);this.editVisible=false;await this.load();if(!this.hasCategoryMetrics(res.data.data.metrics))this.$message.warning('修改已保存，但指标 JSON 中未识别到小样本或类别级指标数据');else this.$message.success('模型修改成功')}finally{this.editing=false}
    },
    async upload(){
      if(this.uploadSource==='remote')return this.importRemote()
      if(!this.uploadForm.file)return this.$message.warning('请选择已训练好的模型文件')
      let metrics={}; if(this.uploadForm.metrics.trim()){try{metrics=JSON.parse(this.uploadForm.metrics)}catch(e){return this.$message.error('指标 JSON 格式不正确')}}
      const data=new FormData(); data.append('model',this.uploadForm.file); data.append('name',this.uploadForm.name); data.append('framework',this.uploadForm.framework); data.append('score',this.uploadForm.score); data.append('metrics',JSON.stringify(metrics)); if(this.uploadForm.metricsFile)data.append('metrics_file',this.uploadForm.metricsFile); this.uploading=true
      try{const res=await addModel(this.project.id,data); this.uploadVisible=false; this.uploadForm={name:'',framework:'PyTorch',score:'',file:null,metricsFile:null,metrics:''}; await this.load(); if(!this.hasCategoryMetrics(res.data.data.metrics))this.$message.warning('模型已保存，但指标 JSON 中未识别到小样本或类别级指标数据'); else this.$message.success('模型和训练指标已保存')}finally{this.uploading=false}
    },
    async importRemote(){const model=this.selectedRemoteModel;if(!model)return this.$message.warning('请选择远程模型');this.uploading=true;try{await importRemoteModel(this.project.id,{server_id:model.server_id,remote_path:model.remote_path,name:model.name,framework:'PyTorch'});this.uploadVisible=false;this.selectedRemoteKey='';await this.load();this.$message.success(model.has_results?'模型和 results.csv 已同步':'模型已同步，但远程目录没有 results.csv')}finally{this.uploading=false}},
    async remove(model){ try{await this.$confirm(`确认删除模型“${model.name}”吗？`,'删除模型',{type:'warning'}); await removeModel(this.project.id,model.id); await this.load()}catch(e){/* 用户取消 */} },
    hasCategoryMetrics(metrics){return Boolean(metrics&&((Array.isArray(metrics.small_sample)&&metrics.small_sample.length)||(Array.isArray(metrics.class_metrics)&&metrics.class_metrics.length)))},
    formatSize(size){return size<1048576?`${(size/1024).toFixed(1)} KB`:`${(size/1048576).toFixed(1)} MB`},
    formatDate(value){return value?value.replace('T',' '):'—'}
  }
}
</script>

<style scoped>
.detail-page{min-height:calc(100vh - 60px);padding:30px;background:#f8f9fb;box-sizing:border-box;color:#182132;font-family:"Microsoft YaHei",sans-serif}.project-header{position:relative;margin-bottom:25px}.title-block{display:flex;align-items:center;gap:14px}.project-mark{display:grid;place-items:center;width:50px;height:50px;border-radius:11px;background:#f3484e;color:#fff;font-size:20px;font-weight:800}.back{color:#498ee6;font-size:12px;cursor:pointer;margin-bottom:4px}h1{font-size:28px;margin:0}.dark-button{position:absolute;right:0;top:8px;padding:12px 18px;border:0;border-radius:9px;background:#151515;color:#fff;font-weight:700;cursor:pointer}.meta,.description{margin:9px 0 0;color:#7c8696;font-size:13px}.description{font-size:14px}.toolbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px}.toolbar .el-input{width:250px}.toolbar span{color:#8690a0;font-size:13px}.workspace{display:grid;grid-template-columns:270px minmax(0,1fr);gap:18px}.model-panel,.section-card,.compare-tip{border:1px solid #e2e6ec;background:#fff;border-radius:13px;box-shadow:0 3px 12px rgba(30,45,70,.04)}.model-panel{padding-bottom:14px;align-self:start}.panel-head{display:flex;justify-content:space-between;padding:18px;border-bottom:1px solid #ebedf1}.panel-head small{color:#8993a2}.select-all{display:block;padding:13px 18px;color:#697587;font-size:13px}.model-group{padding:8px 18px;color:#697587;font-size:13px;font-weight:700}.model-group span{float:right}.model-row{display:flex;align-items:center;gap:7px;margin:0 10px 7px;padding:11px;border-radius:9px;background:#f5f6f8}.model-row>i{width:11px;height:11px;border-radius:50%;flex:none}.model-row span{min-width:0;flex:1}.model-row strong,.model-row small{display:block;overflow:hidden;text-overflow:ellipsis}.model-row small{margin-top:4px;color:#8993a2;font-size:11px}.model-info{cursor:pointer}.model-info:hover strong{color:#438fe9}.model-row button{flex:none;border:0;background:transparent;color:#a0a8b4;font-size:20px;cursor:pointer}.model-row .edit-button{font-size:16px}.model-row .edit-button:hover{color:#438fe9}.upload-box{display:flex;flex-direction:column;align-items:center;gap:6px;margin:12px 10px 0;padding:20px 6px;border:2px dashed #d8dce2;border-radius:10px;color:#727d8d;cursor:pointer}.upload-box b{font-size:26px}.upload-box small{font-size:10px}.charts-panel{min-width:0}.compare-tip{display:flex;align-items:center;gap:14px;padding:14px 18px;margin-bottom:13px}.compare-tip span{display:flex;align-items:center;gap:5px;color:#657184;font-size:12px}.compare-tip i{width:9px;height:9px;border-radius:50%}.compare-tip small{color:#98a1af}.section-card{margin-bottom:14px;overflow:hidden}.section-title{display:flex;width:100%;justify-content:space-between;padding:18px 22px;border:0;background:#fff;font-size:18px;font-weight:700;cursor:pointer}.section-title small{color:#8791a0;font-size:13px}.chart-grid{display:grid;gap:13px;padding:0 14px 14px}.chart-grid.two{grid-template-columns:repeat(2,minmax(0,1fr))}.chart-grid.three{grid-template-columns:repeat(3,minmax(0,1fr))}.dialog-note{margin-top:-8px;color:#7f8998;font-size:13px}.form-row{display:grid;grid-template-columns:1fr 1fr;gap:14px}.form-row .el-select{width:100%}.file-name{margin-top:7px;color:#438fe9;font-size:12px}@media(max-width:1100px){.chart-grid.three{grid-template-columns:1fr 1fr}}@media(max-width:780px){.detail-page{padding:20px 14px}.workspace{grid-template-columns:1fr}.chart-grid.two,.chart-grid.three{grid-template-columns:1fr}.dark-button{position:static;margin-top:18px}.compare-tip{flex-wrap:wrap}}
.field-help{display:block;margin-top:6px;color:#8c96a5;font-size:12px}.form-row :deep(.el-date-editor){width:100%}
.source-meta{max-width:190px;color:#4e8f78!important;font-size:10px!important;white-space:normal;word-break:break-all}.source-switch{margin:3px 0 20px}.remote-source{min-height:330px}.remote-toolbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}.remote-toolbar strong,.remote-toolbar small{display:block}.remote-toolbar small{margin-top:4px;color:#8a94a3}.server-list{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:13px}.server-chip{display:inline-flex;align-items:center;gap:5px;padding:6px 9px;border-radius:7px;background:#f3f5f8;color:#687486;font-size:11px}.server-chip i{width:7px;height:7px;border-radius:50%;background:#aab2bd}.server-chip.online i{background:#35a86c}.server-chip.offline i{background:#ec5269}.remote-model-list{max-height:390px;overflow:auto;border:1px solid #e3e7ed;border-radius:10px}.remote-model-row{display:flex;align-items:flex-start;gap:10px;padding:13px 14px;border-bottom:1px solid #edf0f3;cursor:pointer}.remote-model-row:last-child{border-bottom:0}.remote-model-row:hover,.remote-model-row.selected{background:#f3f8ff}.remote-model-row.disabled{cursor:not-allowed;opacity:.7}.remote-model-row input{margin-top:4px}.remote-main{min-width:0;flex:1}.remote-main strong,.remote-main small{display:block}.remote-main small{margin-top:3px;color:#7f8998;font-size:11px}.remote-main .remote-path{overflow:hidden;color:#53657a;font-family:Consolas,monospace;text-overflow:ellipsis;white-space:nowrap}.remote-main .results-state{color:#2a9466}.remote-main .results-state.missing{color:#d88932}.remote-model-row em{padding:4px 7px;border-radius:10px;background:#e9f5ef;color:#23865b;font-size:10px;font-style:normal;white-space:nowrap}.remote-model-row em.remote{background:#eaf3ff;color:#337fd1}.remote-empty{padding:55px 20px;text-align:center;color:#929baa;font-size:12px}
.detail-tabs{display:flex;gap:31px;margin-bottom:20px;border-bottom:1px solid #dfe4eb}.detail-tabs button{position:relative;padding:10px 3px 14px;border:0;background:transparent;color:#7b8594;font-size:15px;font-weight:700;cursor:pointer}.detail-tabs button.active{color:#172033}.detail-tabs button.active::after{position:absolute;right:0;bottom:-1px;left:0;height:3px;border-radius:3px 3px 0 0;background:#3b91eb;content:""}.ranking-panel{overflow:hidden;border:1px solid #e2e6ec;border-radius:13px;background:#fff;box-shadow:0 3px 12px rgba(30,45,70,.04)}.ranking-head{display:flex;align-items:flex-end;justify-content:space-between;gap:25px;padding:24px}.ranking-head h2{margin:0 0 7px;font-size:21px}.ranking-head p{margin:0;color:#7f8998;font-size:13px}.ranking-head .el-input{width:260px}.ranking-table-wrap{overflow-x:auto;border-top:1px solid #e6eaf0}.ranking-table{width:100%;min-width:970px;border-collapse:collapse}.ranking-table th,.ranking-table td{padding:14px 13px;border-bottom:1px solid #e8ebef;text-align:left;white-space:nowrap;font-size:12px}.ranking-table th{background:#f8fafc;color:#637084;font-weight:700;cursor:pointer;user-select:none}.ranking-table th:hover{background:#f0f5fb;color:#3388ee}.ranking-table tbody tr:hover{background:#f8fbff}.ranking-table tbody tr:last-child td{border-bottom:0}.ranking-table .rank-column{width:45px;cursor:default}.rank-number{color:#8590a0;font-weight:700}.rank-model button{max-width:230px;overflow:hidden;border:0;background:transparent;color:#277fd9;font-weight:700;text-overflow:ellipsis;cursor:pointer}.primary-metric{color:#172f50;font-weight:800}.class-metric{background:#fbfcfe;color:#31415a;font-variant-numeric:tabular-nums}.ranking-table tbody tr:hover .class-metric{background:#f5f9fe}.ranking-empty{padding:45px!important;text-align:center!important;color:#9aa3b1}.ranking-footer{display:flex;align-items:center;justify-content:space-between;padding:16px 22px;color:#7f8998;font-size:12px;border-top:1px solid #edf0f3}.ranking-pagination{display:flex;gap:5px}.ranking-pagination button{min-width:31px;height:30px;padding:0 9px;border:1px solid #dfe4eb;border-radius:6px;background:#fff;color:#657184;cursor:pointer}.ranking-pagination button:hover:not(:disabled),.ranking-pagination button.active{border-color:#3388ee;background:#3388ee;color:#fff}.ranking-pagination button:disabled{opacity:.45;cursor:not-allowed}@media(max-width:780px){.ranking-head{align-items:flex-start;flex-direction:column}.ranking-head .el-input{width:100%}.ranking-footer{align-items:flex-start;flex-direction:column;gap:12px}}
</style>
