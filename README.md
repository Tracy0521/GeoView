# GeoView 目标检测平台

GeoView 是一个基于 PaddleRS、Flask 和 Vue 3 的遥感图像目标检测 Web 平台。当前精简版仅保留两个页面：

- **目标检测**：上传单张图片或图片文件夹，选择目标检测模型，可选 CLAHE、锐化、平滑或滤波预处理，执行检测并预览、下载结果。
- **历史记录**：分页查看目标检测记录，预览、下载或删除检测结果。

原有的变化检测、地物分类、场景分类、图像复原和在线地图功能，以及对应的前后端路由和实现，均已移除。

## 环境要求

- Python 3.7+
- Node.js 16+
- MySQL 5.7+
- PaddlePaddle `>=2.2.0,<2.5.0`

## 安装

1. 安装 PaddlePaddle（以下为 CPU 版本示例）：

   ```shell
   pip install paddlepaddle -i https://mirror.baidu.com/pypi/simple
   ```

2. 安装 PaddleRS 和后端依赖：

   ```shell
   pip install -r PaddleRS/requirements.txt
   pip install -e PaddleRS/
   pip install -r backend/requirements.txt
   ```

3. 安装前端依赖：

   ```shell
   cd frontend
   npm install
   ```

## 配置

1. 根据实际环境修改根目录的 `config.yaml`，配置前后端地址和端口。
2. 根据 `backend/.flaskenv_template` 创建或调整 `backend/.flaskenv`，配置数据库连接。
3. 将 PaddleRS 导出的目标检测模型目录放在：

   ```text
   backend/model/object_detection/<模型目录>/
   ```

   模型元信息中的 `model_type` 必须为 `detector`。

## 启动

后端：

```shell
cd backend
python app.py
```

前端（新终端）：

```shell
cd frontend
npm run serve
```

浏览器访问前端地址后，根路由会自动进入 `/detectobjects`。历史记录页面位于 `/history`。

## 构建前端

```shell
cd frontend
npm run build
```

构建产物输出到 `frontend/dist`。

## 主要目录

```text
GeoView/
├─ backend/
│  ├─ applications/api/          # 上传、目标检测、模型和历史记录接口
│  ├─ applications/interface/    # 目标检测推理封装
│  ├─ model/object_detection/    # 目标检测模型
│  └─ static/upload/             # 上传图片与检测结果
├─ frontend/
│  └─ src/
│     ├─ views/mainfun/DetectObjects.vue
│     └─ views/history/History.vue
└─ PaddleRS/
```

## 接口概览

- `POST /api/file/upload`：上传待检测图片
- `GET /api/model/list/object_detection`：获取可用目标检测模型
- `POST /api/analysis/image_pre`：执行目标检测页所需的图像预处理
- `POST /api/analysis/object_detection`：执行目标检测并写入历史记录
- `GET /api/history/list`：分页获取目标检测历史记录
- `DELETE /api/history/batchRemove`：批量删除目标检测历史记录

## License

本项目沿用原 GeoView 项目的 [Apache License 2.0](LICENSE)。
