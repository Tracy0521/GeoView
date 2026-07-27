<template>
  <div class="image-editor">
    <div class="editor-tabs">
      <button :class="{ active: mode === 'crop' }" type="button" @click="mode = 'crop'">
        <i class="iconfont icon-crop-full" /> 单区域裁剪
      </button>
      <button :class="{ active: mode === 'tiles' }" type="button" @click="mode = 'tiles'">
        <span class="grid-icon">▦</span> 网格切片
      </button>
    </div>

    <div v-if="mode === 'crop'" class="crop-layout">
      <div class="crop-stage">
        <vueCropper
          ref="cropper"
          :img="fileimg"
          :output-size="1"
          output-type="png"
          :info="true"
          :full="false"
          :can-move="true"
          :can-move-box="true"
          :original="false"
          :auto-crop="true"
          :auto-crop-width="800"
          :auto-crop-height="800"
          :fixed-box="false"
        />
      </div>
      <aside class="tool-panel">
        <div class="panel-title"><strong>裁剪工具</strong><small>拖动选框选择需要检测的区域</small></div>
        <div class="icon-actions">
          <el-button circle title="向左旋转" @click="rotateLeft">↶</el-button>
          <el-button circle title="向右旋转" @click="rotateRight">↷</el-button>
          <el-button circle title="放大" @click="changeScale(1)">＋</el-button>
          <el-button circle title="缩小" @click="changeScale(-1)">－</el-button>
        </div>
        <el-button type="primary" class="submit-button" :loading="uploading" @click="saveCrop">
          保存裁剪结果
        </el-button>
      </aside>
    </div>

    <div v-else class="tile-layout">
      <section class="tile-preview">
        <div class="grid-preview-stage">
          <canvas ref="previewCanvas" />
          <div v-if="imageLoading" class="canvas-loading">正在读取影像…</div>
        </div>
        <div v-if="tilePreviews.length" class="result-preview">
          <div class="result-preview-head">
            <div>
              <strong>预计切片结果</strong>
              <small>根据当前宽高与重叠程度生成</small>
            </div>
            <span>展示 {{ tilePreviews.length }} / {{ tilePlan.length }} 张</span>
          </div>
          <div class="result-preview-list">
            <figure v-for="item in tilePreviews" :key="item.index">
              <img :src="item.src" :alt="`预计切片 ${item.index}`">
              <figcaption>
                <strong>#{{ item.index }}</strong>
                <small>{{ item.x }}, {{ item.y }}</small>
              </figcaption>
            </figure>
          </div>
          <p v-if="tilePlan.length > previewLimit" class="preview-more">
            其余 {{ tilePlan.length - previewLimit }} 张将在保存时完整生成
          </p>
        </div>
      </section>
      <aside class="tool-panel tile-settings">
        <div class="panel-title">
          <strong>切片参数</strong>
          <small v-if="sourceSize.width">{{ sourceSize.width }} × {{ sourceSize.height }} px 原始影像</small>
        </div>
        <div class="size-fields">
          <label>
            <span>切片宽度</span>
            <el-input-number v-model="tileWidth" :min="64" :max="maxTileWidth" :step="64" controls-position="right" />
            <small>px</small>
          </label>
          <label>
            <span>切片高度</span>
            <el-input-number v-model="tileHeight" :min="64" :max="maxTileHeight" :step="64" controls-position="right" />
            <small>px</small>
          </label>
        </div>
        <label class="overlap-setting">
          <span><strong>重叠程度</strong><em>{{ overlap }}%</em></span>
          <el-slider v-model="overlap" :min="0" :max="80" :step="5" />
          <small>适当重叠可避免目标在切片边缘被截断，推荐 10%–25%</small>
        </label>
        <div class="tile-summary">
          <div><span>预计生成</span><strong>{{ tilePlan.length }}</strong><small>张切片</small></div>
          <div><span>移动步长</span><strong>{{ stepX }} × {{ stepY }}</strong><small>px</small></div>
        </div>
        <p v-if="tilePlan.length > 200" class="warning">切片数量较多，处理耗时可能明显增加。</p>
        <el-button
          type="primary"
          class="submit-button"
          :loading="uploading"
          :disabled="!tilePlan.length || imageLoading"
          @click="saveTiles"
        >
          生成并保存 {{ tilePlan.length }} 张切片
        </el-button>
      </aside>
    </div>
  </div>
</template>

<script>
import "vue-cropper/dist/index.css";
import { VueCropper } from "vue-cropper";
export default {
  name: "MyVueCropper",
  components: { VueCropper },
  props: {
    childPrehandle: { type: Number, default: 0 },
    childDenoise: { type: Number, default: 0 },
    childModelPath: { type: String, default: "" },
    fileimg: { type: String, default: "" },
    funtype: { type: String, default: "" },
    file: { type: Object, default: () => ({}) },
  },
  emits: ["cut-changed", "save-files"],
  data() {
    return {
      mode: "crop",
      tileWidth: 1024,
      tileHeight: 1024,
      overlap: 20,
      sourceImage: null,
      sourceSize: { width: 0, height: 0 },
      tilePreviews: [],
      previewLimit: 24,
      imageLoading: false,
      uploading: false,
    };
  },
  computed: {
    maxTileWidth() { return Math.max(64, this.sourceSize.width || 8192); },
    maxTileHeight() { return Math.max(64, this.sourceSize.height || 8192); },
    effectiveTileWidth() { return Math.min(this.tileWidth, this.sourceSize.width || this.tileWidth); },
    effectiveTileHeight() { return Math.min(this.tileHeight, this.sourceSize.height || this.tileHeight); },
    stepX() { return Math.max(1, Math.round(this.effectiveTileWidth * (1 - this.overlap / 100))); },
    stepY() { return Math.max(1, Math.round(this.effectiveTileHeight * (1 - this.overlap / 100))); },
    tilePlan() {
      if (!this.sourceSize.width || !this.sourceSize.height) return [];
      const xs = this.axisPositions(this.sourceSize.width, this.effectiveTileWidth, this.stepX);
      const ys = this.axisPositions(this.sourceSize.height, this.effectiveTileHeight, this.stepY);
      return ys.flatMap((y) => xs.map((x) => ({
        x, y, width: this.effectiveTileWidth, height: this.effectiveTileHeight,
      })));
    },
  },
  watch: {
    fileimg: { immediate: true, handler() { this.loadSourceImage(); } },
    mode(value) { if (value === "tiles") this.$nextTick(this.drawPreview); },
    tileWidth() { this.drawPreview(); },
    tileHeight() { this.drawPreview(); },
    overlap() { this.drawPreview(); },
  },
  methods: {
    axisPositions(total, size, step) {
      if (size >= total) return [0];
      const positions = [];
      for (let value = 0; value < total - size; value += step) positions.push(value);
      const finalPosition = total - size;
      if (positions[positions.length - 1] !== finalPosition) positions.push(finalPosition);
      return positions;
    },
    loadSourceImage() {
      if (!this.fileimg) return;
      this.imageLoading = true;
      const image = new Image();
      image.onload = () => {
        this.sourceImage = image;
        this.sourceSize = { width: image.naturalWidth, height: image.naturalHeight };
        this.tileWidth = Math.min(1024, image.naturalWidth);
        this.tileHeight = Math.min(1024, image.naturalHeight);
        this.imageLoading = false;
        this.$nextTick(this.drawPreview);
      };
      image.onerror = () => {
        this.imageLoading = false;
        this.$message.error("图片读取失败，请重新选择");
      };
      image.src = this.fileimg;
    },
    drawPreview() {
      if (this.mode !== "tiles" || !this.sourceImage || !this.$refs.previewCanvas) return;
      const canvas = this.$refs.previewCanvas;
      const maxWidth = Math.min(920, canvas.parentElement.clientWidth || 920);
      const maxHeight = 650;
      const scale = Math.min(maxWidth / this.sourceSize.width, maxHeight / this.sourceSize.height, 1);
      canvas.width = Math.max(1, Math.round(this.sourceSize.width * scale));
      canvas.height = Math.max(1, Math.round(this.sourceSize.height * scale));
      const context = canvas.getContext("2d");
      context.drawImage(this.sourceImage, 0, 0, canvas.width, canvas.height);
      context.fillStyle = "rgba(38,132,235,.10)";
      context.strokeStyle = "rgba(26,112,213,.92)";
      context.lineWidth = Math.max(1, 1.5 * window.devicePixelRatio);
      this.tilePlan.forEach((tile, index) => {
        const x = tile.x * scale;
        const y = tile.y * scale;
        const width = tile.width * scale;
        const height = tile.height * scale;
        context.fillRect(x, y, width, height);
        context.strokeRect(x, y, width, height);
        if (width > 42 && height > 30) {
          context.fillStyle = "rgba(255,255,255,.9)";
          context.fillRect(x + 5, y + 5, 26, 18);
          context.fillStyle = "#176fd5";
          context.font = "11px sans-serif";
          context.fillText(String(index + 1), x + 10, y + 18);
          context.fillStyle = "rgba(38,132,235,.10)";
        }
      });
      this.createTilePreviews();
    },
    createTilePreviews() {
      if (!this.sourceImage) {
        this.tilePreviews = [];
        return;
      }
      this.tilePreviews = this.tilePlan.slice(0, this.previewLimit).map((tile, index) => {
        const canvas = document.createElement("canvas");
        const scale = Math.min(1, 220 / tile.width, 150 / tile.height);
        canvas.width = Math.max(1, Math.round(tile.width * scale));
        canvas.height = Math.max(1, Math.round(tile.height * scale));
        canvas.getContext("2d").drawImage(
          this.sourceImage,
          tile.x, tile.y, tile.width, tile.height,
          0, 0, canvas.width, canvas.height
        );
        return {
          index: index + 1,
          x: tile.x,
          y: tile.y,
          src: canvas.toDataURL("image/jpeg", .78),
        };
      });
    },
    changeScale(value) { this.$refs.cropper.changeScale(value || 1); },
    rotateLeft() { this.$refs.cropper.rotateLeft(); },
    rotateRight() { this.$refs.cropper.rotateRight(); },
    saveCrop() {
      this.$refs.cropper.getCropBlob((blob) => {
        const file = new File([blob], this.outputName("crop", 1), { type: blob.type || "image/png" });
        this.$emit("save-files", [file]);
      });
    },
    async saveTiles() {
      if (this.tilePlan.length > 500) {
        this.$message.warning("切片数量超过 500 张，请增大切片尺寸或降低重叠程度");
        return;
      }
      this.uploading = true;
      try {
        const files = [];
        for (let index = 0; index < this.tilePlan.length; index += 1) {
          const tile = this.tilePlan[index];
          const canvas = document.createElement("canvas");
          canvas.width = tile.width;
          canvas.height = tile.height;
          canvas.getContext("2d").drawImage(
            this.sourceImage,
            tile.x, tile.y, tile.width, tile.height,
            0, 0, tile.width, tile.height
          );
          const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
          files.push(new File([blob], this.outputName("tile", index + 1), { type: "image/png" }));
        }
        this.$emit("save-files", files);
      } catch (error) {
        this.$message.error("切片生成失败，请调整参数后重试");
      } finally {
        this.uploading = false;
      }
    },
    outputName(kind, index) {
      const base = (this.file.name || "image").replace(/\.[^.]+$/, "");
      return `${base}_${kind}_${String(index).padStart(3, "0")}.png`;
    },
  },
};
</script>

<style scoped>
.image-editor{color:#26344a;font-family:"Microsoft YaHei","PingFang SC",sans-serif}
.editor-tabs{display:flex;gap:6px;margin:-8px 0 16px;padding:5px;border-radius:12px;background:#f2f5f9}
.editor-tabs button{display:flex;align-items:center;justify-content:center;gap:7px;flex:1;height:40px;border:0;border-radius:9px;background:transparent;color:#778398;font-weight:700;cursor:pointer}
.editor-tabs button.active{background:#fff;color:#247fdc;box-shadow:0 3px 12px rgba(41,73,112,.1)}
.grid-icon{font-size:19px}.crop-layout,.tile-layout{display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:18px;min-height:560px}
.crop-stage,.tile-preview{overflow:hidden;border:1px solid #dfe6ef;border-radius:14px;background:#111923}
.crop-stage{height:620px}.tool-panel{padding:20px;border:1px solid #e2e8f0;border-radius:14px;background:#fafbfd}
.panel-title strong,.panel-title small{display:block}.panel-title strong{font-size:16px}.panel-title small{margin-top:6px;color:#8995a6;font-size:11px;line-height:1.6}
.icon-actions{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-top:22px}.icon-actions :deep(.el-button){width:43px;height:43px;margin:0;font-size:18px}
.submit-button{width:100%;height:43px;margin-top:24px;border:0;border-radius:10px;background:linear-gradient(100deg,#338ff0,#1e70d5);font-weight:700}
.tile-preview{display:block;min-height:560px;padding:16px;box-sizing:border-box;background:#172231}
.grid-preview-stage{position:relative;display:flex;align-items:center;justify-content:center;min-height:390px}
.tile-preview canvas{display:block;max-width:100%;max-height:560px;box-shadow:0 8px 35px rgba(0,0,0,.28)}
.canvas-loading{position:absolute;color:#fff}.tile-settings{background:#fff}.size-fields{display:grid;gap:13px;margin-top:22px}
.result-preview{margin-top:18px;padding:14px;border:1px solid rgba(177,202,230,.2);border-radius:12px;background:rgba(255,255,255,.06)}
.result-preview-head{display:flex;align-items:flex-end;justify-content:space-between;gap:15px;margin-bottom:12px;color:#fff}
.result-preview-head strong,.result-preview-head small{display:block}.result-preview-head strong{font-size:13px}.result-preview-head small{margin-top:4px;color:#9cabbc;font-size:9px}
.result-preview-head>span{color:#7fc0ff;font-size:10px;font-weight:700}
.result-preview-list{display:grid;grid-auto-flow:column;grid-auto-columns:138px;gap:10px;overflow-x:auto;padding:0 0 8px;scrollbar-width:thin;scrollbar-color:#60778f transparent}
.result-preview-list::-webkit-scrollbar{height:6px}.result-preview-list::-webkit-scrollbar-thumb{border-radius:8px;background:#60778f}
.result-preview-list figure{overflow:hidden;margin:0;border:1px solid rgba(203,221,240,.17);border-radius:9px;background:#0e1721}
.result-preview-list img{display:block;width:100%;height:92px;object-fit:cover;background:#0b1118}
.result-preview-list figcaption{display:flex;align-items:center;justify-content:space-between;gap:6px;padding:7px 8px;color:#dce9f7}
.result-preview-list figcaption strong{font-size:10px}.result-preview-list figcaption small{overflow:hidden;color:#8095aa;font-size:8px;text-overflow:ellipsis;white-space:nowrap}
.preview-more{margin:8px 0 0;color:#8fa2b6;font-size:9px;text-align:right}
.size-fields label{position:relative;display:grid;grid-template-columns:1fr 125px 18px;align-items:center;gap:7px;color:#57657a;font-size:12px}
.size-fields :deep(.el-input-number){width:125px}.size-fields small{color:#99a4b3}
.overlap-setting{display:block;margin-top:24px}.overlap-setting>span{display:flex;justify-content:space-between;color:#56647a;font-size:12px}.overlap-setting em{color:#247fdc;font-style:normal;font-weight:800}
.overlap-setting>small{display:block;color:#98a3b2;font-size:10px;line-height:1.6}.overlap-setting :deep(.el-slider){margin:10px 7px 5px}
.tile-summary{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:20px}
.tile-summary>div{padding:12px;border-radius:10px;background:#f3f7fc}.tile-summary span,.tile-summary small{display:block;color:#8a96a7;font-size:9px}
.tile-summary strong{display:inline-block;margin:5px 4px 2px 0;color:#257bd7;font-size:18px}.warning{margin:12px 0 0;padding:9px;border-radius:8px;background:#fff6e8;color:#b47422;font-size:10px}
@media(max-width:900px){.crop-layout,.tile-layout{grid-template-columns:1fr}.crop-stage{height:500px}.tool-panel{min-height:0}}
</style>
