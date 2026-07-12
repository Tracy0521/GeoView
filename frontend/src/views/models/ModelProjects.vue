<template>
  <main class="projects-page">
    <header>
      <div><span class="eyebrow">模型管理</span><h1>模型排行项目</h1><p>创建项目来组织、保存和比较已经训练完成的模型。</p></div>
      <button class="dark-button" @click="dialogVisible=true">＋ 新项目</button>
    </header>

    <section class="project-panel">
      <div class="panel-title"><span class="folder">□</span><div><h2>项目</h2><p>每个项目可以保存多个模型，并对训练指标进行统一比较。</p></div></div>
      <div class="drop-hint"><span>⇧</span><strong>上传模型请先创建或进入一个项目</strong><small>支持 PyTorch、PaddlePaddle 与 ONNX 已训练模型</small></div>
      <div v-if="projects.length" class="project-list">
        <article v-for="project in projects" :key="project.id" @click="$router.push(`/model-ranking/${project.id}`)">
          <span class="project-mark">{{ project.name.slice(0,1).toUpperCase() }}</span>
          <div><h3>{{ project.name }}</h3><p>◇ {{ project.models.length }} 个模型 · {{ formatSize(totalSize(project)) }}</p></div>
          <span class="go">→</span>
        </article>
      </div>
      <div v-else class="empty">还没有模型项目，点击右上角创建第一个项目。</div>
    </section>

    <el-dialog v-model="dialogVisible" title="创建新项目" width="480px">
      <el-form label-position="top">
        <el-form-item label="项目名称"><el-input v-model="form.name" maxlength="60" placeholder="例如：建筑物检测模型" /></el-form-item>
        <el-form-item label="项目说明"><el-input v-model="form.description" type="textarea" maxlength="300" :rows="3" placeholder="简单说明该项目的用途" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="save">创建项目</el-button></template>
    </el-dialog>
  </main>
</template>

<script>
import { createProject, getProjects } from '@/api/modelRank'
export default {
  name: 'ModelProjects',
  data: () => ({ projects: [], dialogVisible: false, saving: false, form: { name: '', description: '' } }),
  mounted() { this.load() },
  methods: {
    async load() { const res = await getProjects(); this.projects = res.data.data },
    async save() {
      if (!this.form.name.trim()) return this.$message.warning('请输入项目名称')
      this.saving = true
      try { const res = await createProject(this.form); this.dialogVisible = false; this.form = { name:'', description:'' }; this.$router.push(`/model-ranking/${res.data.data.id}`) } finally { this.saving = false }
    },
    totalSize(project) { return project.models.reduce((sum, item) => sum + item.size, 0) },
    formatSize(size) { return size < 1048576 ? `${(size/1024).toFixed(1)} KB` : `${(size/1048576).toFixed(1)} MB` }
  }
}
</script>

<style scoped>
.projects-page { min-height:calc(100vh - 60px); box-sizing:border-box; padding:38px; background:#f7f9fc; color:#192234; font-family:"Microsoft YaHei",sans-serif; }.projects-page header { display:flex; justify-content:space-between; align-items:flex-end; max-width:1100px; margin:0 auto 25px; }.eyebrow { color:#3388ee; font-size:12px; font-weight:800; letter-spacing:1.5px; }h1{margin:7px 0;font-size:30px}header p{margin:0;color:#7f899b}.dark-button{padding:13px 20px;border:0;border-radius:10px;background:#151515;color:white;font-weight:700;cursor:pointer}.project-panel{max-width:1100px;margin:auto;padding:28px;border:1px solid #e3e8ef;border-radius:18px;background:#fff;box-shadow:0 6px 24px rgba(31,45,70,.05)}.panel-title{display:flex;gap:13px;align-items:center}.panel-title h2,.panel-title p{margin:0}.panel-title h2{font-size:21px;margin-bottom:6px}.panel-title p{font-size:13px;color:#8791a2}.folder{display:grid;place-items:center;width:38px;height:38px;border-radius:9px;background:#f0e9ff;color:#8755e9;font-size:21px}.drop-hint{display:flex;flex-direction:column;align-items:center;gap:6px;margin:25px 0 18px;padding:20px;border:2px dashed #d9dee6;border-radius:14px;color:#747f91}.drop-hint span{font-size:27px}.drop-hint small{color:#9ca5b3}.project-list{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}.project-list article{display:flex;align-items:center;gap:14px;padding:17px;border:1px solid #e5e9ef;border-radius:13px;cursor:pointer;transition:.2s}.project-list article:hover{transform:translateY(-2px);border-color:#bcd8fb;box-shadow:0 7px 16px rgba(45,100,165,.08)}.project-mark{display:grid;place-items:center;width:48px;height:48px;border-radius:11px;background:#f4494f;color:#fff;font-size:20px;font-weight:800}.project-list h3,.project-list p{margin:0}.project-list h3{margin-bottom:6px}.project-list p{font-size:12px;color:#7f8998}.go{margin-left:auto;color:#7f8998;font-size:21px}.empty{text-align:center;padding:35px;color:#9aa3b1}@media(max-width:750px){.projects-page{padding:24px 16px}.projects-page header{align-items:flex-start;flex-direction:column;gap:20px}.project-list{grid-template-columns:1fr}}
</style>
