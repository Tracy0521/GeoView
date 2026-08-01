# GeoView 遥感目标检测平台

GeoView 是一个面向遥感目标检测的数据、模型与推理管理平台。后端基于 Flask、SQLAlchemy、Ultralytics 和 OpenCV，前端基于 Vue 3、Element Plus 与 ECharts。

平台覆盖数据集整理、模型归档与指标对比、图像预处理、目标检测、误差诊断和历史记录，也可以通过 SSH 从远程训练服务器导入数据集与训练产物。

## 功能模块

### 工作台

入口：`/dashboard`

- 展示数据集、图片、标注和模型等全局统计信息。
- 提供样本预览和主要功能入口。
- 前端实现：`frontend/src/views/Dashboard.vue`。

### 数据集管理

入口：`/dataset-management`

- 创建、重命名和删除数据集。
- 上传图片、YOLO 标签文件或 ZIP 数据集，识别 `dataset.yaml` 中的类别。
- 查看数据集详情、样本和类别分布，维护类别信息。
- 支持训练集/验证集/测试集划分、图像预处理和数据集导出。
- 支持扫描远程服务器上的数据集并导入本地。
- 后端实现：`applications/api/dataset.py`、`models/dataset_model.py`、`services/remote_datasets.py`。
- 前端实现：`views/dataset/DatasetManagement.vue`、`views/dataset/DatasetDetail.vue`。

### 模型项目与排行

入口：`/model-ranking`

- 以项目组织同一任务下的多个目标检测模型。
- 上传 Ultralytics `.pt` 权重及训练结果 CSV，维护模型说明和评价指标。
- 对比 mAP、Precision、Recall、训练曲线、小样本指标与类别级指标。
- 扫描远程训练服务器的 `output/*/weights/best.pt`，导入权重、训练结果和类别指标。
- 支持启动和查询远程类别指标生成任务。
- 后端实现：`applications/api/model_rank.py`、`models/model_rank.py`、`services/remote_models.py`。
- 前端实现：`views/models/ModelProjects.vue`、`views/models/ModelProjectDetail.vue`。

### 目标检测与图像预处理

入口：`/detectobjects`

- 上传单张或批量图片，选择模型执行目标检测。
- 支持 CLAHE、增强、锐化、高斯模糊、中值滤波和尺寸调整等预处理。
- 展示检测框、类别和置信度，预览并下载检测结果。
- 推理完成后保存分析记录，供历史记录模块查询。
- 后端实现：`applications/api/analysis.py`、`interface/object_detection.py`、`image_processing/`。
- 前端实现：`views/mainfun/DetectObjects.vue`。

### 模型误差诊断

该功能位于模型项目详情页。

- 上传诊断数据，或基于指定数据集异步生成诊断结果。
- 汇总漏检、误检、分类错误和定位误差等问题。
- 展示任务状态、样本详情、类别指标及可视化分析。
- 后端实现：`applications/api/model_rank.py` 中的 diagnostics 接口。
- 前端实现：`components/ErrorDiagnosisCenter.vue`、`components/ClassMetricAnalysis.vue`。

### 历史记录

入口：`/history`

- 分页查看目标检测记录及其输入、输出和分析信息。
- 预览、下载或批量删除检测结果。
- 后端实现：`applications/api/history.py`、`models/analysis.py`。
- 前端实现：`views/history/History.vue`。

## 系统数据流

```text
浏览器（Vue 3）
    │ Axios / JSON / multipart/form-data
    ▼
Flask API
    ├── 数据集管理 ── SQLAlchemy + 本地数据集目录
    ├── 模型管理   ── 项目索引 + 本地模型目录
    ├── 图像分析   ── OpenCV 预处理 + Ultralytics 推理
    ├── 历史记录   ── MySQL
    └── 远程导入   ── Paramiko / SSH / SFTP
```

典型检测流程：上传图片 → 保存文件 → 可选图像预处理 → 加载 `.pt` 模型 → Ultralytics 推理 → 保存可视化结果和历史记录 → 前端展示或下载。

## 环境要求

- Python 3.7+
- Node.js 16+
- MySQL 5.7+
- 支持 Ultralytics 的 Python 环境
- 可选：可访问的 SSH 训练服务器

## 安装与配置

1. 安装后端依赖（其中包含 Ultralytics）：

   ```shell
   pip install -r backend/requirements.txt
   ```

2. 安装前端依赖：

   ```shell
   cd frontend
   npm install
   ```

3. 创建 MySQL 数据库，参考 `backend/init_db.sql` 初始化基础表。

4. 复制 `backend/.flaskenv_template` 为 `backend/.flaskenv`，配置数据库连接和 `SECRET_KEY`。敏感信息只应保存在本机 `.flaskenv`，不要提交到版本库。

5. 根据实际环境修改根目录 `config.yaml`。默认后端监听 `0.0.0.0:5008`，启动后端时会据此生成 `frontend/.env`。

### 远程服务器配置（可选）

`.flaskenv` 最多可配置 10 台服务器，将编号从 `1` 依次递增：

```dotenv
REMOTE_MODEL_SERVER_1_NAME=训练服务器1
REMOTE_MODEL_SERVER_1_HOST=example.com
REMOTE_MODEL_SERVER_1_PORT=22
REMOTE_MODEL_SERVER_1_USERNAME=root
REMOTE_MODEL_SERVER_1_PASSWORD=
REMOTE_MODEL_SERVER_1_KEY_FILE=/path/to/private_key
REMOTE_MODEL_SERVER_1_ROOT=/root/autodl-tmp
REMOTE_MODEL_SERVER_1_PYTHON=/root/miniconda3/bin/python
REMOTE_MODEL_SERVER_1_YOLO_ROOT=/root/ultralytics-YOLO26
```

远程模型约定存放在 `<ROOT>/output/<实验名>/weights/best.pt`；远程数据集通过 `dataset.yaml` 或 `dataset.yml` 识别。

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

浏览器访问前端地址后，根路由会自动进入 `/dashboard`。模型排行页面位于 `/model-ranking`。

## 构建与测试

```shell
cd frontend
npm run build
```

构建产物输出到 `frontend/dist`。

运行当前后端单元测试：

```shell
python -m unittest tests/test_remote_models.py
```

## 主要目录

```text
GeoView/
├── backend/
│   ├── app.py                         # Flask 启动、异常处理和迁移初始化
│   ├── applications/
│   │   ├── api/                       # 文件、数据集、模型、分析和历史 API
│   │   ├── common/                    # CRUD、路径、校验、响应和上传工具
│   │   ├── configs/                   # Flask 与数据库配置
│   │   ├── extensions/                # SQLAlchemy、上传和 dotenv 初始化
│   │   ├── image_processing/          # CLAHE、模糊、锐化、增强和缩放
│   │   ├── interface/                 # 推理与分析业务封装
│   │   ├── models/                    # SQLAlchemy 模型和模型项目结构
│   │   ├── schemas/                   # Marshmallow 序列化结构
│   │   └── services/                  # 远程模型、数据集 SSH 服务
│   ├── migrations/                    # Alembic 数据库迁移
│   ├── scripts/                       # 远程类别指标生成脚本
│   └── static/
│       ├── dataset_library/           # 数据集、图片和 YOLO 标签
│       ├── model_library/             # 模型项目、权重和指标文件
│       └── upload/                    # 上传图片与检测结果
├── frontend/src/
│   ├── api/                           # Axios 请求封装
│   ├── components/                    # 图表、裁剪、诊断等复用组件
│   ├── router/                        # 页面路由
│   ├── utils/                         # 标注、上传队列、下载和预处理工具
│   └── views/                         # 工作台、数据集、模型、检测、历史页面
├── docs/                              # 功能补充文档
├── tests/                             # 后端测试与代码检查
└── config.yaml                        # 服务地址、端口和调试开关
```

`backend/static/` 中保存的是运行数据。部署或迁移时，应按需单独备份数据库、数据集目录、模型目录和上传结果。

## API 模块概览

| 前缀 | 模块 | 主要职责 |
| --- | --- | --- |
| `/api/file` | 文件 | 上传待处理图片 |
| `/api/analysis` | 分析 | 图像预处理、目标检测 |
| `/api/history` | 历史 | 分页查询和批量删除检测记录 |
| `/api/model` | 模型列表 | 按任务类型获取可用于推理的模型 |
| `/api/model-rank` | 模型项目 | 项目和模型 CRUD、指标、远程导入、误差诊断 |
| `/api/dataset` | 数据集 | CRUD、上传、统计、划分、预处理、导出和远程导入 |

具体请求参数以 `backend/applications/api/` 中的路由和 `frontend/src/api/` 中的调用为准。

## 数据格式约定

- 检测模型：Ultralytics 可加载的 `.pt` 权重。
- 数据集：YOLO 格式，图片与同名 `.txt` 标签对应，类别由 `dataset.yaml` 的 `names` 提供。
- 标签行：`class_id center_x center_y width height`，坐标为相对图片尺寸的归一化值。
- 模型指标：支持训练结果 CSV；类别级指标可从远程 `class_metrics.json` 导入或生成。

## License

本项目沿用原 GeoView 项目的 [Apache License 2.0](LICENSE)。
