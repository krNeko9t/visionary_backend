# Visionary Backend Upload

接收多张图片输入，按规划执行重建流水线，并提供任务状态查询与产物下载接口。

详细文档见 `docs/`。

## Quick Start

### 1) 前置条件

- Windows/macOS/Linux + Docker Desktop
- NVIDIA GPU，相关 worker 依赖 CUDA
- Git
- 运行语义识别算法时需下载神经网络权重：

```powershell
mkdir ckpts -Force
Invoke-WebRequest -Uri "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth" -OutFile "ckpts\sam_vit_h_4b8939.pth"
```

### 2) 拉代码

```powershell
git clone --recurse-submodules <repo-url>
cd visionary_backend_upload
git submodule update --init --recursive
```

### 3) 构建 Worker 镜像

默认的点云重建需要 COLMAP 和 3DGS 两个 worker：

```powershell
docker compose --profile tools build colmap-worker 3dgs-worker
```

要使用全部流水线，首次使用及 worker 依赖变化后构建全部工具镜像：

```powershell
docker compose --profile tools build
```

构建 3DGS 时如需指定显卡 CUDA 架构，例如 `8.6`：

```powershell
docker compose --profile tools build --build-arg TORCH_CUDA_ARCH_LIST=8.6 3dgs-worker
```

构建 `gaussian-wrapping-worker` 需 BuildKit。失败时先执行：

```powershell
$env:DOCKER_BUILDKIT=1
```

### 4) 启动后端和前端 demo

```powershell
docker compose up -d --build task-server web-demo
```

查看启动状态与日志：

```powershell
docker compose ps
docker compose logs -f task-server web-demo
```

访问：`http://localhost:5173`

`web-demo` 会等待 `task-server` 健康后再启动，并通过 Compose 内部网络访问 API。

## 架构概览

Task Server 是不需要 GPU 的轻量 CPU 服务，负责接收任务、规划阶段、通过 Docker 启动一次性 worker、汇总状态。COLMAP、3DGS、LangSplat、Gaussian Wrapping 和 3DGS-to-PC 均在各自的 worker 镜像中运行，通过挂载的 job 目录交换输入与产物。

调用方通过 `outputs` 表达目标产物，服务端自动规划所需阶段。高级调试可通过 `spec.advanced` 覆盖阶段列表与阶段配置。

## Jobs 目录结构

单个任务目录：`/data/jobs/{job_id}`。

```text
jobs/{job_id}/
  state/job.json
  input/
  config/
  stages/{stage_id}/result.json
  events/{stage_id}.jsonl
  colmap/
  output/
  langsplatv2/
  langsplat_export/
```

任务之外的共享运行数据位于 `data/cache/models/`。LangSplat 的一次性 worker 会在这里缓存 OpenCLIP 等自动下载的模型；人工准备的固定权重仍放在只读的 `ckpts/`。

- `state/job.json`：任务状态、阶段状态、产物索引
- `input/`：上传原图
- `config/*.yaml`：创建任务时物化的阶段配置
- `stages/{stage_id}/result.json`：阶段标准结果
- `events/{stage_id}.jsonl`：阶段进度事件
- `colmap/`、`output/`、`langsplatv2/`、`langsplat_export/`：各 worker 实际产物目录

## YAML 配置

- 全局默认：`visionary_tasks/configs/{stage}/default.yaml`
- 单任务配置：`jobs/{job_id}/config/{stage}.yaml`

阶段标识：`colmap`、`3dgs`、`langsplat`、`gaussian-wrapping`、`3dgs-to-pc`。

## API 调用链路

1. `GET /api/v1/capabilities`：查询支持的 outputs、input modes、stage presets、stages、mesh_formats
2. `POST /api/v1/jobs`：上传图片与 `spec`，创建任务
3. `GET /api/v1/jobs/{job_id}`：轮询状态与进度
4. `GET /api/v1/jobs/{job_id}/artifacts`：列出产物
5. `GET /api/v1/jobs/{job_id}/artifacts/{artifact_id}/download`：下载产物

创建任务时 `spec` 示例：

```json
{
  "outputs": ["point_cloud"]
}
```

按阶段选择 YAML 预设：

```json
{
  "outputs": ["point_cloud"],
  "options": {
    "stage_presets": {
      "3dgs": "small",
      "colmap": "fast"
    }
  }
}
```

从已有 native 3DGS ply 提取几何 mesh：

```json
{
  "outputs": ["mesh"],
  "options": {
    "input_mode": "native_3dgs_ply",
    "iteration": 30000
  }
}
```

此模式上传一个 `point_cloud.ply`，仅规划 `3dgs-to-pc` 阶段，产物为 `mesh`，文件 `output/mesh_poisson.ply`。

图片全流程使用 `gaussian-wrapping` 提取 mesh，可产出 `mesh` 与 `mesh_textured`。

可选导出 OBJ、GLB：

```json
{
  "outputs": ["mesh"],
  "options": {
    "mesh_formats": ["ply", "obj", "glb"]
  }
}
```

默认 `mesh_formats` 为 `["ply"]`，保留 worker 原始 PLY。额外格式在 mesh 阶段完成后由 Task Server 转换，登记为 `mesh_obj`、`mesh_glb`；存在 `mesh_textured` 时同步生成 `mesh_textured_obj`、`mesh_textured_glb`。

## 常见问题

- `5173` 打不开：执行 `docker compose ps`，确认 `task-server` 为 `healthy` 且 `web-demo` 已启动
- 页面提示任务服务连接失败：检查 `docker compose logs task-server` 和 `http://localhost:8000/healthz`
- 提示找不到 `visionary-3dgs-worker:local`：执行 `docker compose --profile tools build 3dgs-worker`
- GPU 报错：检查 Docker GPU 支持与显卡驱动
- 3DGS 上游源码固定在 `docker_workers/GaussianSplatting/source` 子模块；镜像构建时提示源码缺失，执行 `git submodule update --init --recursive`
- `gaussian-wrapping` 构建失败：确认 BuildKit 已开启

## 进一步阅读

- `docs/setup-and-start.md`：环境与启动
- `docs/backend-api-frontend-guide.md`：API 对接
- `docs/jobs-worker-output-structure.md`：任务目录与 worker 产物
- `docs/yaml-config.md`：YAML 参数与覆盖规则
