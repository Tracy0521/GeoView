import { historyGetPage } from "@/api/history"
import global from '@/global'

function getUploadImg(type) {
  historyGetPage(1, 20, type).then((res) => {
    this.imgArr = res.data.data.forEach((item)=>{
      item['before_img'] = global.BASEURL+item.before_img
      item['after_img'] = global.BASEURL+item.after_img
    })
    this.imgArr = res.data.data
    this.isUpload = this.imgArr.length !== 0;
  }).catch((rej)=>{})
}

function goCompress(type,num) {
  this.historyGetPage(1, num, type).then((res) => {
    this.atchDownload(
        res.data.data.map((item) => {
          return { after_img: item.after_img, id: item.id };
        })
    );
  }).catch((rej)=>{});
}

async function upload(type,funUrl) {
  if (this.fileList.length === 0) {
    this.$message.error("请上传图片！");
    return;
  }

  const files = this.fileList.map((item) => item && item.raw ? item.raw : item);
  const maxBatchBytes = 20 * 1024 * 1024;
  const maxBatchFiles = 20;
  const batches = [];
  let batch = [];
  let batchBytes = 0;

  files.forEach((file) => {
    const fileSize = Number(file && file.size) || 0;
    if (batch.length && (batch.length >= maxBatchFiles || batchBytes + fileSize > maxBatchBytes)) {
      batches.push(batch);
      batch = [];
      batchBytes = 0;
    }
    batch.push(file);
    batchBytes += fileSize;
  });
  if (batch.length) batches.push(batch);

  this.batchProgress.visible = true;
  this.batchProgress.percentage = 0;
  this.batchProgress.label = `准备上传，共 ${files.length} 张图片`;

  try {
    const uploadedSources = [];
    for (let index = 0; index < batches.length; index += 1) {
      const formData = new FormData();
      batches[index].forEach((file) => formData.append("files", file));
      formData.append("type", type);
      this.batchProgress.label = `正在上传第 ${index + 1}/${batches.length} 批`;
      const response = await this.createSrc(formData);
      uploadedSources.push(...response.data.data.map((item) => item.src));
      this.batchProgress.percentage = Math.round(((index + 1) / batches.length) * 75);
    }

    this.uploadSrc.list = uploadedSources;
    this.batchProgress.percentage = 82;
    this.batchProgress.label = this.uploadSrc.prehandle
      ? `正在批量执行图像增强并检测 ${uploadedSources.length} 张图片`
      : `正在检测 ${uploadedSources.length} 张图片`;
    await this.imgUpload(this.uploadSrc,funUrl);
    this.batchProgress.percentage = 100;
    this.batchProgress.label = `处理完成，共 ${uploadedSources.length} 张图片`;
    this.fileList = [];
    this.$message.success(`上传成功，共处理 ${uploadedSources.length} 张图片！`);
    this.getMore();

    if (this.$refs.upload) this.$refs.upload.clearFiles();
    setTimeout(() => { this.batchProgress.visible = false; }, 1800);
  } catch (error) {
    const status = error && error.response && error.response.status;
    this.batchProgress.label = status === 413 ? "存在超过服务器限制的单张图片" : "上传或处理失败";
    this.$message.error(status === 413
      ? "单张图片体积仍超过服务器限制，请压缩图片后重试"
      : "图片上传或处理失败，请稍后重试");
  }
}


export { getUploadImg, goCompress, upload }
