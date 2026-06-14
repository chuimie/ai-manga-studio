# AI 动态漫剧 IP 孵化系统

基于 AI 大模型的动态漫画（动态漫剧）自动化生产系统。通过 LLM 生成剧本、TTS 配音、AI 绘图、视频合成、质检等流水线引擎，实现从角色卡创建到完整剧集产出的全流程自动化。

---

## 项目结构

```
ai-manga-studio/
├── backend/                        # 后端服务
│   ├── main_app.py                 # FastAPI 主服务（API + WebSocket）
│   ├── requirements.txt            # Python 依赖
│   ├── .env                        # 环境配置（API Key 等）
│   ├── pipeline/                   # 生产流水线（六大引擎）
│   │   ├── main.py                 # 流水线主控入口
│   │   ├── script_engine.py        # 剧本引擎（LLM 生成分镜脚本）
│   │   ├── image_engine.py         # 图像引擎（AI 逐帧绘图）
│   │   ├── video_engine.py         # 视频引擎（逐帧合成视频）
│   │   ├── tts_engine.py           # 配音引擎（TTS 语音合成）
│   │   ├── merge_engine.py         # 合并引擎（音视频合成为成片）
│   │   └── qc_engine.py            # 质检引擎（自动评分 + 重试）
│   ├── character_creator/          # 角色卡工坊
│   │   ├── app.py                  # 角色卡 WebSocket 服务
│   │   ├── state_machine.py        # 对话状态机
│   │   ├── fuzzy_detector.py       # 模糊意图检测
│   │   ├── prompt_builder.py       # Prompt 组装
│   │   └── card_generator.py       # 角色卡生成与存储
│   ├── utils/                      # 工具模块
│   │   ├── prompt_logger.py        # Prompt 审计日志
│   │   ├── scheduler.py            # 自动调度器（定时生产）
│   │   ├── lora_manager.py         # LoRA 训练管理
│   │   ├── story_evolution.py      # AI 剧情进化（风格权重自适应）
│   │   ├── copyright_manager.py    # 版权存证管理
│   │   ├── ip_value_engine.py      # IP 价值评估（三层过滤）
│   │   ├── ip_comparator.py        # IP 对比分析
│   │   └── distribution_manager.py # 内容分发素材生成
│   └── config/                     # 配置文件
│       ├── style_matrix.json       # 风格矩阵
│       └── emotion_tts_map.json    # 情感-TTS 映射
├── frontend/                       # 前端 SPA（纯 HTML/CSS/JS）
│   ├── index.html                  # 入口页面
│   ├── css/style.css               # 全局样式
│   └── js/
│       ├── utils.js                # 工具函数
│       ├── app.js                  # 全局状态 & 路由
│       └── pages/                  # 各页面模块
│           ├── dashboard.js        # 仪表盘
│           ├── ip-manager.js       # IP 管理
│           ├── creator.js          # 角色卡工坊（WebSocket 对话）
│           ├── production.js       # 生产中心
│           ├── library.js          # 剧集库
│           ├── qc-reports.js       # 质检报告
│           ├── settings.js         # 系统设置
│           ├── audit.js            # Prompt 审计
│           ├── lora.js             # LoRA 训练管理
│           ├── scheduler.js        # 自动调度器
│           ├── ipvalue.js          # IP 价值判断
│           ├── copyright.js        # 版权备案
│           ├── compare.js          # IP 对比分析
│           ├── distribution.js     # 内容分发
│           └── evolution.js        # AI 剧情进化
├── assets/                         # 资源文件（剧集、图片等）
├── models/lora/                    # LoRA 权重文件
├── exports/                        # 导出文件
├── logs/                           # 运行日志
└── qc_reports/                     # 质检报告
```

---

## 快速启动

### 环境要求

- Python ≥ 3.10
- FFmpeg（用于视频合成）
- Node.js（非必需，前端纯静态无需构建）

### 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 配置 API Key

复制 `backend/.env` 文件并填入你的 API Key：

| 配置项 | 说明 | 获取方式 |
|--------|------|---------|
| `AGNES_API_KEY` | Agnes AI 大模型 API | [Agnes 平台](https://console.agnes.ai) |
| `MIMO_API_KEY` | MiMo TTS 语音合成 | [MiMo 平台](https://console.mimo.ai) |
| `RUNPOD_API_KEY` | RunPod 云端 GPU（LoRA 训练） | [RunPod](https://www.runpod.io) |

### 启动服务

#### 方式 1：直接运行

```bash
cd backend
python main_app.py
```

#### 方式 2：Docker 部署（推荐）

**前提条件：** Docker Engine 24+。命令 `docker-compose`（v1）或 `docker compose`（v2）任一可用。

#### 方式 3：Docker 开发模式（源码热重载）

源码挂载到容器内，修改后即时生效，无需 rebuild：

```bash
# 首次需要构建镜像
docker-compose build manga-studio
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# 后端 API: http://localhost:8000/docs（带 --reload）
# 前端页面: http://localhost:80

# 查看日志
docker-compose -f docker-compose.yml -f docker-compose.dev.yml logs -f
```
#### LoRA 训练容器

训练需要 PyTorch（~3.5GB），不会随主服务自动启动，按需单独管理：

```bash
# 构建训练容器（首次或依赖变更时）
docker-compose -f docker-compose.yml -f docker-compose.training.yml build lora-trainer

# 启动训练容器（在后台运行）
docker-compose -f docker-compose.yml -f docker-compose.training.yml up -d lora-trainer

# 查看训练容器日志
docker-compose -f docker-compose.training.yml logs -f lora-trainer

# 查看训练 API 文档
# http://localhost:8001/docs

# 停止训练容器
docker-compose -f docker-compose.yml -f docker-compose.training.yml down
```

#### 日常命令（API + 前端）

```bash
# 1. 配置 API Key（将模板复制为实际配置文件）
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入你的 API Key

# 2. 构建并启动
docker-compose up -d

# 3. 查看日志
docker-compose logs -f

# 4. 停止服务
docker-compose down
```

首次构建需要 1-3 分钟（下载 Python 基础镜像）。运行时目录（`assets/`、`models/`、`exports/`、`logs/`、`qc_reports/`）自动挂载到宿主机，容器销毁后数据不丢失。

##### 更新镜像

```bash
git pull
docker-compose build --no-cache
docker-compose up -d
```

服务默认运行在 `http://localhost:8000`，自动提供前端页面。

---

## 核心功能

### 1. 角色卡工坊
对话式 AI 角色创建。通过多轮对话与 AI 交互，逐步完善角色的世界观、题材、基调等设定，最终生成结构化的 IP 角色卡。支持实时预览和语音试听。

### 2. 全自动生产流水线
一键触发多集连产，流水线按序执行：

```
剧本生成 → 逐帧绘图 → 视频合成 → TTS 配音 → 音视频合并 → 质检评分
```

质检未通过（< 0.80）自动重试，最多 3 次。

### 3. LoRA 训练管理
为每个 IP 角色训练专属 LoRA 模型，确保角色视觉一致性。支持云端 RunPod 训练，训练完成后自动应用于后续生产。

### 4. IP 价值评估
三层漏斗评估体系：
- **自动初筛**：AI 自动评估 IP 潜力
- **人工复审**：人工介入评估
- **市场验证**：市场数据辅助决策

最终输出立项决策（立项 / 观察 / 放弃）。

### 5. AI 剧情进化
基于历史剧集表现数据，自动调整风格权重（题材、基调、叙事、节奏），并通过 A/B 测试验证优化效果，实现剧情风格的持续进化。

### 6. 版权存证
为每个 IP 生成版权存证包（PDF），包含角色设计说明、AI 工具声明、创作过程证明、内容指纹（SHA-256）、Prompt 调用记录等。

### 7. 内容分发
一键生成多平台发布素材（标题、正文、话题标签、置顶评论等），支持抖音、B 站、小红书、微博、YouTube。

### 8. Prompt 审计
完整记录每次生产的 Prompt 调用日志，支持按日期、引擎、IP 筛选查询和导出。

---

## API 概览

| 路径 | 说明 |
|------|------|
| `GET /api/ips` | 获取所有 IP 列表 |
| `POST /api/ips` | 创建新 IP |
| `GET /api/ips/{ip_id}` | 获取单个 IP 详情 |
| `POST /api/produce` | 触发生产 |
| `GET /api/stats` | 系统统计概览 |
| `GET /api/episodes` | 剧集列表 |
| `GET /api/qc` | 质检报告列表 |
| `GET /api/audit/logs` | Prompt 审计日志 |
| `GET /api/audit/stats` | 审计统计 |
| `GET /api/evolution/weights/{ip_id}` | 剧情进化权重 |
| `POST /api/evolution/abtest/{ip_id}` | 创建 A/B 测试 |
| `POST /api/lora/train/{ip_id}` | 触发 LoRA 训练 |
| `POST /api/copyright/generate/{ip_id}` | 生成版权存证 |
| `GET /api/compare/all` | IP 对比分析 |
| `POST /api/distribution/generate/{ep_id}` | 生成分发素材 |
| `WS /ws/creator` | 角色卡工坊 WebSocket |
| `WS /ws/production/{task_id}` | 生产日志流 WebSocket |

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端框架 | FastAPI + Uvicorn |
| AI 模型 | Agnes AI (GPT-兼容 API) |
| TTS | MiMo AI |
| LoRA 训练 | RunPod Serverless GPU |
| 前端 | 原生 HTML/CSS/JS (无框架) |
| 视频处理 | FFmpeg |
| 其他 | Pydantic, ReportLab, SciPy |

---

## 开发

### 代码规范

```bash
# 后端代码检查
cd backend
ruff check .
```

### 添加新页面

1. 在 `backend/main_app.py` 中添加 API 路由
2. 在 `frontend/js/pages/` 下创建页面 JS 文件
3. 在 `frontend/index.html` 的 `<script>` 标签列表中添加引用
4. 在 `app.js` 的 `PAGES` 对象中注册页面路由