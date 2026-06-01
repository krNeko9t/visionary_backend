# Visionary Backend Upload

接收多张图片输入，按阶段顺序执行 `colmap -> 3dgs -> langsplat -> gaussian-wrapping`，并提供任务状态查询与结果下载接口。

详细文档见 `docs/`。

## Quick Start

### 1) 前置条件

- Windows/macOS/Linux + Docker Desktop
- NVIDIA GPU（建议；相关 worker 依赖 CUDA）
- Git

### 2) 拉代码

```powershell
git clone --recurse-submodules <repo-url>
cd visionary_backend_upload
git submodule update --init --recursive
```

### 3) 启动后端

```powershell
docker compose up --build task-server
```

### 4) 启动前端 demo

```powershell
docker compose up -d web-demo
```

访问：`http://localhost:5173`

### 5)  **(建议)** 提前构建工具镜像

如果要跑完整流水线（尤其 `langsplat` 和 `gaussian-wrapping`），建议提前构建 tools profile，由于镜像体积很大，整个过程可能花费若干小时：

```powershell
docker compose --profile tools build colmap-worker langsplat-worker gaussian-wrapping-worker
```

> `gaussian-wrapping-worker` 构建依赖 BuildKit；若报错可先执行：
> `\$env:DOCKER_BUILDKIT=1`

## Jobs 目录结构（核心）

单个任务目录：`/data/jobs/{job_id}`（或你自定义的 `JOBS_ROOT/{job_id}`）。

关键内容：

- `progress.json`：任务与阶段状态的唯一事实源（前端轮询依赖）
- `input/`：上传原图
- `config/*.yaml`：创建任务时物化出的阶段配置
- `artifacts/{stage}/result.json`：阶段结果索引
- `colmap/`：COLMAP 产物（如 `sparse/0`）
- `output/`：3DGS 与 mesh 常见产物目录（如 `point_cloud/.../point_cloud.ply`）
- `langsplatv2/`（默认名，可改）：LangSplat 模型目录

## YAML 配置

### 配置文件位置

- 全局默认：`visionary_tasks/configs/{stage}/default.yaml`
- 单任务生效配置：`jobs/{job_id}/config/{stage}.yaml`

`{stage}` 包括：`colmap`、`3dgs`、`langsplat`、`gaussian-wrapping`。

## API 最小调用链路

1. `GET /api/pipeline`：拿阶段定义与顺序
2. `POST /api/jobs`：上传图片并创建任务（异步）
3. `GET /api/jobs/{job_id}`：轮询状态
4. 完成后下载：
   - `GET /api/jobs/{job_id}/download/3dgs`
   - `GET /api/jobs/{job_id}/download/mesh`

## 常见问题

- `5173` 打不开：确认 `web-demo` 已启动且端口未占用
- 任务创建失败：先检查 `http://localhost:8000/healthz`
- GPU 报错：检查 Docker GPU 支持和显卡驱动
- `gaussian-wrapping` 构建失败：优先确认 BuildKit 已开启

## 进一步阅读

- `docs/setup-and-start.md`：环境与启动细节
- `docs/backend-api-frontend-guide.md`：前端对接 API
- `docs/jobs-worker-output-structure.md`：任务目录与各 worker 产物
- `docs/yaml-config.md`：YAML 参数体系与覆盖规则
