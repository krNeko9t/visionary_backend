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

### 页面使用步骤

1. 打开 `http://localhost:5173`
2. 选择图片（支持多张）
3. 保持默认勾选（`colmap` + `3dgs`）即可先跑通
4. 点击「上传 / 创建任务」
5. 等待状态从 `queued/running` 变为 `done`
6. 点击下载按钮获取结果（3DGS 或 Mesh）

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
- **页面打不开 `5173`**
  - 执行 `docker compose ps` 确认 `web-demo` 在运行
  - 如果端口被占用，先释放本机 `5173` 端口再重启

- **创建任务失败 / 接口报错**
  - 先检查 `http://localhost:8000/healthz` 是否返回 `{"status":"ok"}`
  - 确保 `task-server` 已正常启动且没有构建失败

- **GPU 相关错误**
  - 检查 Docker Desktop 是否开启 GPU 支持
  - 检查显卡驱动是否可用

- **构建 `gaussian-wrapping-worker` 报 BuildKit 错误**
  - 在 PowerShell 先执行：`$env:DOCKER_BUILDKIT=1`