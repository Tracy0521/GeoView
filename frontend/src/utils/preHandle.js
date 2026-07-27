import { createSrc, prePhotoHandle } from "@/api/upload";
import global from "@/global";

async function loadEnhancementPreview(context, prehandle, targetKey, type) {
  // The preview is intentionally sampled. Full-batch enhancement runs after
  // all source files are uploaded by the main detection action.
  const previewFiles = context.fileList
    .slice(0, 3)
    .map((item) => item && item.raw ? item.raw : item);
  const formData = new FormData();
  previewFiles.forEach((file) => formData.append("files", file));
  formData.append("type", type);

  const uploadResponse = await createSrc(formData);
  const sources = uploadResponse.data.data.map((item) => global.BASEURL + item.src);
  context.before = sources;
  context.prePhoto.list = sources;
  context.prePhoto.prehandle = prehandle;

  const previewResponse = await prePhotoHandle(context.prePhoto);
  context[targetKey] = previewResponse.data.data.map((item) => global.BASEURL + item);
}

function selectSharpen(type) {
  if (this.fileList.length === 0) {
    this.$refs.sharpen.checked = false;
    if (this.uploadSrc.prehandle === 4) this.uploadSrc.prehandle = 0;
    else this.$message.error("请先上传图片");
    return;
  }

  if (this.$refs.clahe.checked) this.$refs.clahe.checked = false;
  if (!this.$refs.sharpen.checked) {
    this.uploadSrc.prehandle = 0;
    this.$message.success("取消锐化处理");
    return;
  }

  this.uploadSrc.prehandle = 4;
  this.$message.success("已启用批量锐化处理");
  loadEnhancementPreview(this, 4, "sharpenImg", type)
    .catch(() => this.$message.error("锐化预览生成失败，但仍可直接开始批量检测"));
}

function selectClahe(type) {
  if (this.fileList.length === 0) {
    this.$refs.clahe.checked = false;
    if (this.uploadSrc.prehandle === 2) this.uploadSrc.prehandle = 0;
    else this.$message.error("请先上传图片");
    return;
  }

  if (this.$refs.sharpen.checked) this.$refs.sharpen.checked = false;
  if (!this.$refs.clahe.checked) {
    this.uploadSrc.prehandle = 0;
    this.$message.success("取消 CLAHE 处理");
    return;
  }

  this.uploadSrc.prehandle = 2;
  this.$message.success("已启用批量 CLAHE 处理");
  loadEnhancementPreview(this, 2, "claheImg", type)
    .catch(() => this.$message.error("CLAHE 预览生成失败，但仍可直接开始批量检测"));
}

function selectFilter() {
  if (this.$refs.smooth.checked) this.$refs.smooth.checked = false;
  if (!this.$refs.filter.checked) {
    this.uploadSrc.denoise = 0;
    this.$message.success("取消高斯滤波处理");
  } else {
    this.uploadSrc.denoise = 5;
    this.$message.success("已启用批量高斯滤波处理");
  }
}

function selectSmooth() {
  if (this.$refs.filter.checked) this.$refs.filter.checked = false;
  if (!this.$refs.smooth.checked) {
    this.uploadSrc.denoise = 0;
    this.$message.success("取消平滑处理");
  } else {
    this.uploadSrc.denoise = 3;
    this.$message.success("已启用批量平滑处理");
  }
}

export { selectSharpen, selectFilter, selectSmooth, selectClahe };
