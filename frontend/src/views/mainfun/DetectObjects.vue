<template>
  <main class="detect-page">
    <section class="page-hero">
      <div class="hero-copy">
        <span class="eyebrow"><i class="status-dot" /> AI OBJECT DETECTION</span>
        <h1>遥感目标检测</h1>
        <p>上传遥感影像，配置图像预处理与检测模型，一站式完成智能识别。</p>
      </div>
      <div class="hero-flow" aria-label="检测流程">
        <div class="flow-step active">
          <span>01</span>
          <strong>上传影像</strong>
        </div>
        <i class="flow-line" />
        <div class="flow-step">
          <span>02</span>
          <strong>配置参数</strong>
        </div>
        <i class="flow-line" />
        <div class="flow-step">
          <span>03</span>
          <strong>查看结果</strong>
        </div>
      </div>
    </section>

    <section class="workspace-grid">
      <article class="panel upload-panel">
        <div class="panel-heading">
          <div class="heading-icon upload-icon">
            <i class="iconfont icon-yunduanshangchuan" />
          </div>
          <div>
            <span class="section-index">步骤 01</span>
            <h2>上传检测影像</h2>
            <p>支持 JPG、JPEG、PNG，可单选、多选或上传整个文件夹</p>
          </div>
          <span v-if="fileList.length" class="file-count">已选择 {{ fileList.length }} 个文件</span>
        </div>

        <el-upload
          ref="upload"
          v-model:file-list="fileList"
          class="upload-card"
          drag
          action="#"
          multiple
          :auto-upload="false"
          @change="beforeUpload(fileList[fileList.length - 1].raw)"
        >
          <div class="upload-illustration">
            <span class="upload-orbit orbit-one" />
            <span class="upload-orbit orbit-two" />
            <i class="iconfont icon-yunduanshangchuan" />
          </div>
          <div class="upload-title">拖拽影像到这里</div>
          <div class="upload-subtitle">或 <em>点击选择本地图片</em></div>
          <div class="upload-formats">
            <span>JPG</span><span>JPEG</span><span>PNG</span>
          </div>
        </el-upload>

        <input
          id="folder"
          ref="uploadFile"
          type="file"
          webkitdirectory
          directory
          multiple
          @change="uploadMore()"
        >
        <div class="upload-actions">
          <button class="secondary-action" type="button" @click="fileClick">
            <i class="iconfont icon-wenjianshangchuan" />
            <span>上传文件夹</span>
          </button>
          <button
            v-if="fileList.length"
            class="text-action danger-action"
            type="button"
            @click="clearQueue"
          >
            清空已选图片
          </button>
        </div>

        <div class="upload-note">
          <i class="iconfont icon-zidingyi" />
          <p>
            使用自定义模型时，请将模型文件放入
            <strong>backend/model/object_detection</strong> 文件夹。
          </p>
        </div>
      </article>

      <aside class="panel settings-panel">
        <div class="panel-heading compact-heading">
          <div class="heading-icon setting-icon">⌘</div>
          <div>
            <span class="section-index">步骤 02</span>
            <h2>检测参数</h2>
            <p>按需配置影像处理方式与模型</p>
          </div>
        </div>

        <div class="setting-group edit-setting">
          <div class="setting-copy">
            <span class="mini-icon"><i class="iconfont icon-crop-full" /></span>
            <div>
              <strong>上传时编辑图片</strong>
              <small>进入裁剪与区域编辑</small>
            </div>
          </div>
          <label class="switch-control">
            <input ref="cut" type="checkbox" @change="select()">
            <span />
          </label>
        </div>

        <div class="setting-group option-setting">
          <div class="setting-title">
            <span class="mini-icon blue"><i class="iconfont icon-tuxingtuxiangchuli" /></span>
            <div><strong>图像增强</strong><small>提升影像细节与边缘</small></div>
          </div>
          <div class="option-grid">
            <label class="option-chip">
              <input ref="clahe" type="checkbox" @change="selectClahe(2)">
              <span class="chip-check">✓</span>
              <span><strong>CLAHE</strong><small>局部对比度增强</small></span>
            </label>
            <label class="option-chip">
              <input ref="sharpen" type="checkbox" @change="selectSharpen(2)">
              <span class="chip-check">✓</span>
              <span><strong>锐化</strong><small>强化目标轮廓</small></span>
            </label>
          </div>
        </div>

        <div class="setting-group option-setting">
          <div class="setting-title">
            <span class="mini-icon green"><i class="iconfont icon-agora_AIjiangzao" /></span>
            <div><strong>降噪处理</strong><small>减少影像噪点干扰</small></div>
          </div>
          <div class="option-grid">
            <label class="option-chip">
              <input ref="smooth" type="checkbox" @change="selectSmooth()">
              <span class="chip-check">✓</span>
              <span><strong>平滑</strong><small>柔化随机噪点</small></span>
            </label>
            <label class="option-chip">
              <input ref="filter" type="checkbox" @change="selectFilter()">
              <span class="chip-check">✓</span>
              <span><strong>滤波</strong><small>抑制高频干扰</small></span>
            </label>
          </div>
        </div>

        <div class="setting-group model-setting">
          <div class="setting-title model-title">
            <span class="mini-icon purple">M</span>
            <div><strong>检测模型</strong><small>选择本次任务使用的模型</small></div>
          </div>
          <div v-if="modelPathArr.length===0" class="empty-model">
            未检测到模型文件，请检查上传目录
          </div>
          <el-radio-group v-else v-model="uploadSrc.model_path" class="model-list">
            <el-radio
              v-for="(item,index) in modelPathArr"
              :key="index"
              class="model-option"
              :label="item.model_path"
            >
              <span class="model-name">{{ item.model_name }}</span>
              <span class="model-tag">MODEL</span>
            </el-radio>
          </el-radio-group>
        </div>

        <el-button
          type="primary"
          class="start-button"
          @click="upload('目标检测','object_detection')"
        >
          <span>开始智能检测</span>
          <i>→</i>
        </el-button>
        <p class="start-hint">检测时间取决于图片数量、分辨率和所选模型</p>
      </aside>
    </section>

    <section v-if="uploadSrc.prehandle" class="panel preview-panel">
      <div class="panel-heading">
        <div class="heading-icon preview-icon"><i class="iconfont icon-tupiantianjia" /></div>
        <div>
          <span class="section-index">处理预览</span>
          <h2>{{ uploadSrc.prehandle===2 ? 'CLAHE' : '锐化' }} 处理效果</h2>
          <p>对比原始影像与预处理影像，点击图片可放大查看</p>
        </div>
      </div>
      <div class="preview-grid">
        <div v-for="(item,index) in before" :key="`before-${index}`" class="preview-item">
          <el-image :src="item" :preview-src-list="[item]" :preview-teleported="true" />
          <div class="preview-caption"><span>原始影像</span><small>ORIGINAL</small></div>
        </div>
        <template v-if="uploadSrc.prehandle===2">
          <div v-for="(item,index) in claheImg" :key="`clahe-${index}`" class="preview-item">
            <el-image :src="item" :preview-src-list="[item]" :preview-teleported="true" />
            <div class="preview-caption">
              <span>CLAHE 处理后</span>
              <button type="button" @click="downloadimgWithWords(-1,item,`CLAHE处理图.png`)"><i class="iconfont icon-xiazai" /></button>
            </div>
          </div>
        </template>
        <template v-if="uploadSrc.prehandle===4">
          <div v-for="(item,index) in sharpenImg" :key="`sharpen-${index}`" class="preview-item">
            <el-image :src="item" :preview-src-list="[item]" :preview-teleported="true" />
            <div class="preview-caption">
              <span>锐化处理后</span>
              <button type="button" @click="downloadimgWithWords(-1,item,`锐化处理图.png`)"><i class="iconfont icon-xiazai" /></button>
            </div>
          </div>
        </template>
      </div>
    </section>

    <section class="results-section">
      <div class="results-heading">
        <div>
          <span class="eyebrow"><i class="status-dot result-dot" /> DETECTION RESULTS</span>
          <h2>检测结果</h2>
          <p>点击图片进入预览，使用鼠标滚轮可放大或缩小</p>
        </div>
        <div class="result-actions">
          <el-button v-if="isUpload" class="download-button" @click="goCompress('目标检测')">
            <i class="iconfont icon-dabaoxiazai" /> 打包下载
          </el-button>
          <el-button type="primary" class="refresh-button" @click="getMore">
            <i class="iconfont icon-shuaxin" /> 刷新结果
          </el-button>
        </div>
      </div>
      <div class="result-content">
        <ImgShow :img-arr="imgArr" />
      </div>
    </section>

    <el-dialog
      v-model="cutVisible"
      :modal="false"
      title="编辑"
      width="75%"
      top="0"
    >
      <MyVueCropper
        :fileimg="fileimg"
        :funtype="funtype"
        :file="file"
        :child_prehandle="uploadSrc.prehandle"
        :child_denoise="uploadSrc.denoise"
        :child-model-path="uploadSrc.model_path"
        @cut-changed="notvisible"
        @child-refresh="getMore"
      />
    </el-dialog>
    <Bottominfor />
  </main>
</template>
<script>
import {atchDownload, downloadimgWithWords, getImgArrayBuffer} from "@/utils/download.js";
import {createSrc, imgUpload,getCustomModel} from "@/api/upload";
import {historyGetPage} from "@/api/history";
import {getUploadImg, goCompress, upload} from "@/utils/getUploadImg";
import {selectClahe, selectFilter, selectSharpen, selectSmooth,} from "@/utils/preHandle";
import ImgShow from "@/components/ImgShow";
import Bottominfor from "@/components/Bottominfor";
import MyVueCropper from "@/components/MyVueCropper";
export default {
  name: "Detectobjects",
  components: {
    ImgShow,
    Bottominfor,
    MyVueCropper,
  },
  beforeRouteEnter(to, from, next) {
    next((vm) => {
      document.querySelector(".el-main").scrollTop = 0;
    });
  },
  data() {
    return {
      isUpload:true,
      canUpload:true,
      claheImg:[],
      sharpenImg:[],
      before:[],
      fileimg: "",
      file: {},
      isNotCut: true,
      cutVisible: false,
      funtype: "目标检测",
      scrollTop: "",
      fit: "fill",

      fileList: [],
      uploadSrc: {
        list: [],
        prehandle: 0,
        denoise: 0,
        model_path:''
      },
      modelPathArr:[],
      prePhoto:{
        list:[],
        prehandle:0,
        type:4
      },
      imgArr:[]
    };
  },
  watch:{
    uploadSrc:{
      handler(newVal,oldVal){
        this.uploadSrc = newVal
      },
      deep:true,
      immediate:true
    }
  },
  created() {
    this.getUploadImg("目标检测");
    this.getCustomModel('object_detection').then((res)=>{
      this.modelPathArr = res.data.data
      this.uploadSrc.model_path = this.modelPathArr[0]?.model_path
    }).catch((rej)=>{})
  },
  methods: {
    getImgArrayBuffer,
    atchDownload,
    downloadimgWithWords,
    imgUpload,
    getCustomModel,
    historyGetPage,
    createSrc,
    getUploadImg,
    upload,
    goCompress,
    selectSharpen,
    selectFilter,
    selectSmooth,
    selectClahe,
    checkUpload() {
      this.isUpload = this.afterImg.length !== 0;
    },
    clearQueue() {
      this.fileList = [];
      this.$message.success("清除成功");
    },
    notvisible() {
      this.cutVisible = false;
      this.fileList = [];
    },
    getMore() {
      this.getUploadImg("目标检测");
    },
    uploadMore() {
            this.beforeUpload(...this.$refs.uploadFile.files)
        if(this.canUpload){
          this.fileList.push(...this.$refs.uploadFile.files);
        }else{
          setTimeout(() => {
              this.$message.error('检测到您上传的文件夹内存在不符合规范的图片类型')
          }, 1000);
        
        }
    },
    fileClick() {
      document.querySelector("#folder").click();
    },
    beforeUpload(file) {
      this.cutVisible = this.$refs.cut.checked;
        const fileSuffix = file.name.substring(file.name.lastIndexOf(".") + 1)
  const whiteList = ['jpg','jpeg','png','JPG','JPEG']
  if (whiteList.indexOf(fileSuffix) === -1) {
    this.$message.error("只允许上传jpg, jpeg, png, JPG, 或JPEG格式,请重新上传");
    this.fileList= []
    this.canUpload = false
  this.cutVisible = false;
  }
     else{
        this.canUpload = true
    this.fileimg = window.URL.createObjectURL(new Blob([file]));}
    },
    select() {
      this.isNotCut = this.$refs.cut.checked;
    },
  },
};
</script>
<style lang="less" scoped>
.detect-page {
  min-height: calc(100vh - 60px);
  padding: 30px 32px 42px;
  box-sizing: border-box;
  color: #182238;
  background:
    radial-gradient(circle at 90% 0, rgba(53, 143, 255, .09), transparent 25%),
    #f5f7fb;
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
}

.page-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 30px;
  min-height: 150px;
  margin-bottom: 24px;
  padding: 30px 36px;
  overflow: hidden;
  border: 1px solid rgba(207, 224, 245, .9);
  border-radius: 22px;
  box-sizing: border-box;
  background:
    linear-gradient(100deg, rgba(255,255,255,.98) 0%, rgba(248,252,255,.94) 62%, rgba(230,243,255,.88) 100%);
  box-shadow: 0 12px 38px rgba(36, 67, 108, .07);
}

.hero-copy h1,
.hero-copy p,
.panel-heading h2,
.panel-heading p,
.results-heading h2,
.results-heading p {
  margin: 0;
}

.eyebrow {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #2d83ed;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 1.8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #37b47e;
  box-shadow: 0 0 0 5px rgba(55, 180, 126, .12);
}

.hero-copy h1 {
  margin-top: 12px;
  font-size: 32px;
  line-height: 1.2;
  letter-spacing: -.5px;
}

.hero-copy p {
  margin-top: 10px;
  color: #78869a;
  font-size: 14px;
}

.hero-flow {
  display: flex;
  align-items: center;
  min-width: 410px;
  padding: 18px 22px;
  border: 1px solid #e5edf7;
  border-radius: 16px;
  background: rgba(255,255,255,.78);
}

.flow-step {
  display: flex;
  align-items: center;
  gap: 9px;
  white-space: nowrap;
  color: #8390a3;
}

.flow-step span {
  display: grid;
  place-items: center;
  width: 31px;
  height: 31px;
  border-radius: 9px;
  color: #7d899a;
  background: #edf1f6;
  font-size: 11px;
  font-weight: 800;
}

.flow-step strong { font-size: 13px; }
.flow-step.active { color: #2079e8; }
.flow-step.active span { color: #fff; background: linear-gradient(135deg, #2e91ff, #176edc); }
.flow-line { flex: 1; min-width: 24px; height: 1px; margin: 0 12px; background: #dce4ee; }

.workspace-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.42fr) minmax(360px, .88fr);
  align-items: start;
  gap: 22px;
}

.panel {
  border: 1px solid #e4eaf2;
  border-radius: 20px;
  background: #fff;
  box-shadow: 0 8px 30px rgba(35, 57, 88, .055);
}

.upload-panel,
.settings-panel,
.preview-panel { padding: 25px; }

.panel-heading {
  display: flex;
  align-items: center;
  gap: 13px;
  margin-bottom: 22px;
}

.heading-icon {
  display: grid;
  flex: 0 0 44px;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 13px;
  font-size: 19px;
}

.heading-icon .iconfont { font-size: 20px; }
.upload-icon { color: #2785ed; background: #eaf4ff; }
.setting-icon { color: #7656dc; background: #f1edff; font-size: 22px; font-weight: 700; }
.preview-icon { color: #1d9b75; background: #e9f8f2; }

.section-index {
  display: block;
  margin-bottom: 4px;
  color: #3d8cef;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 1.2px;
}

.panel-heading h2 { font-size: 19px; }
.panel-heading p { margin-top: 5px; color: #8994a5; font-size: 12px; }
.file-count {
  margin-left: auto;
  padding: 7px 11px;
  border-radius: 20px;
  color: #277cdc;
  background: #edf6ff;
  font-size: 11px;
  font-weight: 700;
}

.upload-card { width: 100%; }
.upload-card :deep(.el-upload) { width: 100%; }
.upload-card :deep(.el-upload-dragger) {
  width: 100%;
  min-height: 330px;
  padding: 62px 30px 30px;
  border: 1.5px dashed #b8d2ef;
  border-radius: 16px;
  box-sizing: border-box;
  background:
    linear-gradient(180deg, rgba(244,250,255,.82), rgba(250,252,255,.96));
  transition: border-color .25s, background .25s, box-shadow .25s;
}
.upload-card :deep(.el-upload-dragger:hover) {
  transform: none;
  border-color: #3d93f1;
  background: #f5faff;
  box-shadow: inset 0 0 0 3px rgba(61,147,241,.055);
}
.upload-card :deep(.el-upload-list) { text-align: left; }

.upload-illustration {
  position: relative;
  display: grid;
  place-items: center;
  width: 94px;
  height: 94px;
  margin: 0 auto 24px;
  border-radius: 50%;
  background: linear-gradient(145deg, #edf7ff, #d9edff);
}
.upload-illustration .iconfont { position: relative; z-index: 2; color: #3189ed; font-size: 46px; }
.upload-orbit { position: absolute; border: 1px solid rgba(49,137,237,.19); border-radius: 50%; }
.orbit-one { inset: -9px; }
.orbit-two { inset: -19px; opacity: .55; }
.upload-title { color: #25334b; font-size: 18px; font-weight: 700; }
.upload-subtitle { margin-top: 8px; color: #8793a5; font-size: 13px; }
.upload-subtitle em { color: #2580e8; font-style: normal; font-weight: 700; }
.upload-formats { display: flex; justify-content: center; gap: 7px; margin-top: 23px; }
.upload-formats span { padding: 4px 8px; border-radius: 5px; color: #8995a6; background: #edf2f7; font-size: 9px; font-weight: 800; }

#folder { display: none; }
.upload-actions { display: flex; align-items: center; justify-content: center; gap: 15px; margin-top: 18px; }
.secondary-action,
.text-action,
.preview-caption button {
  border: 0;
  cursor: pointer;
  font-family: inherit;
}
.secondary-action {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border: 1px solid #dbe7f4;
  border-radius: 10px;
  color: #357dce;
  background: #f6faff;
  font-size: 13px;
  font-weight: 700;
}
.secondary-action:hover { border-color: #9ec8f4; background: #eef7ff; }
.text-action { padding: 9px 4px; color: #8993a3; background: transparent; font-size: 12px; }
.danger-action:hover { color: #e06161; }
.upload-note {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-top: 22px;
  padding: 13px 15px;
  border-radius: 11px;
  color: #718096;
  background: #f7f9fc;
  font-size: 11px;
  line-height: 1.7;
}
.upload-note i { margin-top: 2px; color: #5c91cd; }
.upload-note p { margin: 0; }
.upload-note strong { color: #42536a; }

.compact-heading { margin-bottom: 17px; }
.setting-group { padding: 17px 0; border-top: 1px solid #edf1f5; }
.edit-setting { display: flex; align-items: center; justify-content: space-between; }
.setting-copy,
.setting-title { display: flex; align-items: center; gap: 11px; }
.setting-copy strong,
.setting-copy small,
.setting-title strong,
.setting-title small { display: block; }
.setting-copy strong,
.setting-title strong { color: #344056; font-size: 13px; }
.setting-copy small,
.setting-title small { margin-top: 3px; color: #9aa4b3; font-size: 10px; }
.mini-icon {
  display: grid;
  place-items: center;
  width: 33px;
  height: 33px;
  border-radius: 10px;
  color: #63758c;
  background: #eef2f6;
  font-size: 12px;
  font-weight: 800;
}
.mini-icon .iconfont { font-size: 15px; }
.mini-icon.blue { color: #2e86ed; background: #eaf4ff; }
.mini-icon.green { color: #2c9c72; background: #e8f7f1; }
.mini-icon.purple { color: #7957dd; background: #f0ecff; }

.switch-control { position: relative; width: 41px; height: 23px; cursor: pointer; }
.switch-control input { position: absolute; opacity: 0; }
.switch-control span { position: absolute; inset: 0; border-radius: 20px; background: #d7dee7; transition: .2s; }
.switch-control span::after { content: ""; position: absolute; top: 3px; left: 3px; width: 17px; height: 17px; border-radius: 50%; background: #fff; box-shadow: 0 1px 4px rgba(0,0,0,.18); transition: .2s; }
.switch-control input:checked + span { background: #348bee; }
.switch-control input:checked + span::after { transform: translateX(18px); }

.option-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; margin-top: 13px; }
.option-chip { position: relative; display: flex; align-items: center; gap: 9px; min-height: 48px; padding: 9px 10px; border: 1px solid #e4eaf1; border-radius: 11px; box-sizing: border-box; cursor: pointer; transition: .2s; }
.option-chip:hover { border-color: #a9caf0; background: #f9fcff; }
.option-chip input { position: absolute; opacity: 0; }
.chip-check { display: grid; flex: 0 0 20px; place-items: center; width: 20px; height: 20px; border: 1px solid #d5dce6; border-radius: 6px; color: transparent; font-size: 12px; transition: .2s; }
.option-chip > span:last-child strong,
.option-chip > span:last-child small { display: block; }
.option-chip > span:last-child strong { color: #4d596d; font-size: 11px; }
.option-chip > span:last-child small { margin-top: 2px; color: #a0a9b6; font-size: 9px; }
.option-chip input:checked + .chip-check { border-color: #368beb; color: #fff; background: #368beb; }
.option-chip:has(input:checked) { border-color: #a8cef8; background: #f3f9ff; }

.model-title { margin-bottom: 12px; }
.model-list { display: flex; flex-direction: column; gap: 7px; width: 100%; }
.model-option {
  position: relative;
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 43px;
  height: auto;
  margin: 0;
  padding: 8px 10px;
  border: 1px solid #e5eaf1;
  border-radius: 10px;
  box-sizing: border-box;
  background: #fbfcfe;
}
.model-option :deep(.el-radio__label) { display: flex; align-items: center; width: calc(100% - 22px); padding-left: 8px; }
.model-option :deep(.el-radio__input.is-checked + .el-radio__label) { color: #2f7ed7; }
.model-name { overflow: hidden; color: #4b586c; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.model-tag { margin-left: auto; padding: 3px 5px; border-radius: 4px; color: #8a96a8; background: #edf1f6; font-size: 7px; font-weight: 800; letter-spacing: .7px; }
.empty-model { padding: 13px; border-radius: 9px; color: #a27642; background: #fff8ed; font-size: 11px; }

.start-button {
  width: 100%;
  height: 46px;
  margin-top: 8px;
  border: 0;
  border-radius: 12px;
  background: linear-gradient(100deg, #2f91f6, #216fd9);
  box-shadow: 0 9px 22px rgba(42, 127, 225, .24);
  font-size: 14px;
  font-weight: 700;
}
.start-button span { letter-spacing: .5px; }
.start-button i { margin-left: 11px; font-size: 18px; font-style: normal; }
.start-button:hover { transform: translateY(-1px); box-shadow: 0 12px 26px rgba(42,127,225,.3); }
.start-hint { margin: 10px 0 0; color: #9ca5b2; font-size: 9px; text-align: center; }

.preview-panel { margin-top: 22px; }
.preview-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.preview-item { overflow: hidden; border: 1px solid #e5eaf1; border-radius: 14px; background: #fafbfd; }
.preview-item :deep(.el-image) { display: block; width: 100%; min-height: 260px; max-height: 420px; border-radius: 0; }
.preview-caption { display: flex; align-items: center; padding: 13px 15px; color: #435067; font-size: 12px; font-weight: 700; }
.preview-caption small { margin-left: auto; color: #a2aab7; font-size: 8px; letter-spacing: 1px; }
.preview-caption button { margin-left: auto; color: #2f83e6; background: transparent; }

.results-section { margin-top: 30px; }
.results-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin: 0 2px 17px; }
.results-heading h2 { margin-top: 9px; font-size: 23px; }
.results-heading p { margin-top: 6px; color: #8c97a7; font-size: 12px; }
.result-dot { background: #318bf0; box-shadow: 0 0 0 5px rgba(49,139,240,.11); }
.result-actions { display: flex; gap: 9px; }
.result-actions :deep(.el-button) { height: 38px; margin: 0; border-radius: 10px; font-size: 12px; font-weight: 700; }
.download-button { color: #397fcf; border-color: #d6e4f3; background: #fff; }
.refresh-button { border: 0; background: #2f85e7; }
.result-actions .iconfont { margin-right: 5px; }
.result-content :deep(.el-card) { border: 1px solid #e3e9f1; border-radius: 18px; box-shadow: 0 8px 28px rgba(35,57,88,.05); }
.result-content :deep(.el-empty) { min-height: 310px; }
.result-content :deep(.img-display-item) { gap: 20px; padding: 10px 8px 25px; }
.result-content :deep(.img-display) { border: 1px solid #e6ebf2; box-shadow: 0 5px 18px rgba(42,63,92,.07); }
.result-content :deep(.img-infor) { color: #536075; font-family: inherit; font-size: 13px; }
.result-content :deep(.index-number) { color: #3187e9; font-size: 23px; }

@media (max-width: 1180px) {
  .page-hero { align-items: flex-start; flex-direction: column; }
  .hero-flow { width: 100%; min-width: 0; box-sizing: border-box; }
  .workspace-grid { grid-template-columns: 1fr; }
  .settings-panel { display: grid; grid-template-columns: 1fr 1fr; column-gap: 24px; }
  .settings-panel .compact-heading,
  .settings-panel .model-setting,
  .settings-panel .start-button,
  .settings-panel .start-hint { grid-column: 1 / -1; }
  .setting-group:nth-of-type(2) { border-top: 1px solid #edf1f5; }
}

@media (max-width: 720px) {
  .detect-page { padding: 18px 14px 30px; }
  .page-hero { min-height: 0; padding: 23px 20px; border-radius: 17px; }
  .hero-copy h1 { font-size: 27px; }
  .hero-flow { padding: 13px; }
  .flow-step { flex-direction: column; gap: 5px; text-align: center; }
  .flow-step strong { font-size: 10px; }
  .flow-line { margin: 0 7px; }
  .upload-panel,
  .settings-panel,
  .preview-panel { padding: 18px; }
  .panel-heading { align-items: flex-start; }
  .file-count { display: none; }
  .upload-card :deep(.el-upload-dragger) { min-height: 290px; padding: 58px 18px 25px; }
  .settings-panel { display: block; }
  .option-grid,
  .preview-grid { grid-template-columns: 1fr; }
  .results-heading { align-items: flex-start; flex-direction: column; }
  .result-actions { width: 100%; }
  .result-actions :deep(.el-button) { flex: 1; }
  .upload-note strong { word-break: break-all; }
}
</style>
