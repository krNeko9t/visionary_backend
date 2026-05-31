# 环境配置与启动

本文档只覆盖本项目最基础的本地启动流程：先把后端 `task-server` 跑起来，再给出可选的前端 demo 与工具镜像构建。

## 1. 前置条件

- `Git`
- `Docker Desktop`
- NVIDIA GPU

## 2. 拉取代码

```powershell
# 首次克隆
git clone --recurse-submodules <你的仓库地址>
# 如果已经克隆过但不确定子模块是否完整
git submodule update --init --recursive
```

## 3. 启动后端

```powershell
# 启动后端
docker compose up --build task-server
# 停止服务
docker compose stop task-server
```

启动成功后可访问：

- 健康检查：`http://localhost:8000/healthz`
- OpenAPI 文档：`http://localhost:8000/docs`

## 4. 启动前端演示页面

```powershell
docker compose up -d web-demo
```

访问：`http://localhost:5173`

该页面默认请求 `http://localhost:8000`（见 `compose.yaml` 里的 `API_BASE_URL`）。

## 5. 提前构建工具镜像

如果你后续要跑 `colmap / langsplat / gaussian-wrapping` 阶段，建议先构建 `tools` profile 下的镜像：

```powershell
docker compose --profile tools build colmap-worker langsplat-worker gaussian-wrapping-worker
```

## 6. 可选环境变量

项目默认值已经可直接跑通，只有在你需要改路径或改阶段参数时才需要设置。常用变量包括：

- `DATA_ROOT`（默认 `/data`）
- `JOBS_ROOT`（默认 `${DATA_ROOT}/jobs`）
- `COLMAP_WORKER_IMAGE`（默认 `visionary-colmap-worker:local`）
- `LANGSPLAT_WORKER_IMAGE`（默认 `langsplatv2:pt241`）
- `WRAPPING_WORKER_IMAGE`（默认 `gaussian-wrapping`）
- `GS_ITERATIONS`（默认 `30000`）
- `GS_SAVE_ITERATION`（默认 `500`）

如果你要配置这些变量，最直接的方式是在 `compose.yaml` 的 `task-server` 下增加 `environment:` 字段，然后重新 `docker compose up --build task-server`。

## 7. 常见问题

- 构建 `gaussian-wrapping-worker` 时报 BuildKit 相关错误：先执行  
  `$env:DOCKER_BUILDKIT=1`
- 启动时报 GPU 相关错误：检查 Docker Desktop 的 GPU 支持是否开启、驱动是否正常
- `task-server` 构建时报找不到 `gaussian-splatting`：通常是子模块没初始化，重新执行  
  `git submodule update --init --recursive`