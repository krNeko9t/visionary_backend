# 环境配置与启动

本文档覆盖本地启动流程：启动后端 task-server，可选启动前端 demo 与构建工具镜像。

## 前置条件

- Git
- Docker Desktop
- NVIDIA GPU
- 完整流水线需要可用的 Docker GPU 支持，并提前构建 tools profile worker 镜像
- 运行 `language_model` / LangSplat 时需要 SAM 权重文件 `ckpts/sam_vit_h_4b8939.pth`

下载 SAM 权重：

```powershell
mkdir ckpts -Force
Invoke-WebRequest -Uri "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth" -OutFile "ckpts\sam_vit_h_4b8939.pth"
```

## 拉取代码

```powershell
git clone --recurse-submodules <你的仓库地址>
git submodule update --init --recursive
```

## 启动后端与前端演示页面

```powershell
docker compose up -d --build task-server web-demo
```

启动后可访问：

- 健康检查：`http://localhost:8000/healthz`
- OpenAPI 文档：`http://localhost:8000/docs`
- 前端演示页：`http://localhost:5173`

`web-demo` 会等待 `task-server` 健康后再启动。浏览器请求同源 `/api`，由 Vite 通过 Compose 内部网络转发给后端，因此用局域网 IP 访问页面时也不会错误连接到访问者自己的 `localhost:8000`。

查看启动状态与日志：

```powershell
docker compose ps
docker compose logs -f task-server web-demo
```

### 页面使用步骤

1. 打开 `http://localhost:5173`
2. 选择图片，支持多张
3. 选择目标产物，默认 `point_cloud`
4. 点击创建任务
5. 等待状态变为 `done`
6. 下载产物

## 提前构建工具镜像

完整流水线、`language_model` 或 `native_3dgs_ply` mesh 任务需提前构建 tools profile 镜像：

```powershell
docker compose --profile tools build colmap-worker langsplat-worker gaussian-wrapping-worker 3dgs-to-pc-worker
```

## 配置覆盖

全局默认配置位于 `visionary_tasks/configs/`。单任务配置在 `data/jobs/{job_id}/config/`。

创建任务时可通过 `spec.advanced.stage_overrides` 覆盖阶段参数，详见 `docs/yaml-config.md`。

服务级配置位于 `visionary_tasks/configs/server/active.yaml`，包含 `jobs_root`、`gs_repo_path`、`ckpts_root`、`langsplat_repo_path`、CORS 等。

默认 compose 已挂载：

- `./data:/data`：job 状态、输入、配置与产物
- `./ckpts:/workspace/ckpts:ro`：LangSplat/SAM 权重
- `./docker_workers/LangSplatV2:/workspace/langsplat-src:ro`：LangSplat live code
- `./visionary_tasks:/workspace/visionary_tasks`：服务代码与配置

## 常见问题

- 页面打不开 5173：执行 `docker compose ps`，确认 task-server 为 `healthy` 且 web-demo 在运行
- 页面提示任务服务连接失败：检查 `docker compose logs task-server`；健康检查应返回 `{"status":"ok"}`
- GPU 相关错误：检查 Docker GPU 支持与显卡驱动
- LangSplat 报缺少 SAM 权重：确认 `ckpts/sam_vit_h_4b8939.pth` 存在，并重启 `task-server`
- 构建 gaussian-wrapping-worker 报 BuildKit 错误：执行 `$env:DOCKER_BUILDKIT=1`
