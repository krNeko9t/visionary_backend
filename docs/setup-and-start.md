# 环境配置与启动

本文档覆盖本地启动流程：启动后端 task-server，可选启动前端 demo 与构建工具镜像。

## 前置条件

- Git
- Docker Desktop
- NVIDIA GPU

## 拉取代码

```powershell
git clone --recurse-submodules <你的仓库地址>
git submodule update --init --recursive
```

## 启动后端

```powershell
docker compose up --build task-server
docker compose stop task-server
```

启动后可访问：

- 健康检查：`http://localhost:8000/healthz`
- OpenAPI 文档：`http://localhost:8000/docs`

## 启动前端演示页面

```powershell
docker compose up -d web-demo
```

访问：`http://localhost:5173`

页面默认请求 `http://localhost:8000`。

### 页面使用步骤

1. 打开 `http://localhost:5173`
2. 选择图片，支持多张
3. 选择目标产物，默认 `point_cloud`
4. 点击创建任务
5. 等待状态变为 `done`
6. 下载产物

## 提前构建工具镜像

完整流水线或 `native_3dgs_ply` mesh 任务需提前构建 tools profile 镜像：

```powershell
docker compose --profile tools build colmap-worker langsplat-worker gaussian-wrapping-worker 3dgs-to-pc-worker
```

## 配置覆盖

全局默认配置位于 `visionary_tasks/configs/`。单任务配置在 `data/jobs/{job_id}/config/`。

创建任务时可通过 `spec.advanced.stage_overrides` 覆盖阶段参数，详见 `docs/yaml-config.md`。

服务级配置位于 `visionary_tasks/configs/server/active.yaml`，包含 `jobs_root`、`gs_repo_path`、CORS 等。

## 常见问题

- 页面打不开 5173：执行 `docker compose ps` 确认 web-demo 在运行
- 创建任务失败：检查 `http://localhost:8000/healthz` 是否返回 `{"status":"ok"}`
- GPU 相关错误：检查 Docker GPU 支持与显卡驱动
- 构建 gaussian-wrapping-worker 报 BuildKit 错误：执行 `$env:DOCKER_BUILDKIT=1`
