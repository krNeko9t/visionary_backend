# Jobs 目录与 Worker 产物说明

本文说明单个任务目录（`jobs/{job_id}`）的文件结构，以及每个 worker 实际会产出的文件类型与位置。

## 1. 任务根目录结构

默认情况下，`JOBS_ROOT` 为 `/data/jobs`，单个任务目录为：

`/data/jobs/{job_id}`

典型结构如下（`[]` 表示可选，`...` 表示该目录下还有其它内容）：

```text
jobs/{job_id}/
├─ progress.json
├─ input/
│  ├─ *.jpg|*.jpeg|*.png|*.bmp|*.webp
├─ colmap/
│  ├─ sparse/
│  │  └─ 0/
│  ├─ images/
│  ├─ distorted/
│  ├─ stereo/
│  ├─ run-colmap-geometric.sh
│  └─ run-colmap-photometric.sh
├─ output/
│  ├─ point_cloud/
│  │  └─ iteration_{N}/
│  │     └─ point_cloud.ply
│  ├─ chkpnt{N}.pth
│  ├─ [mesh_*.ply]
│  └─ ...
├─ langsplatv2/  # 默认值，可被 LANGSPLAT_MODEL_RELATIVE 覆盖
│  └─ ...
├─ artifacts/
│  ├─ colmap/result.json
│  ├─ 3dgs/result.json
│  ├─ langsplat/result.json
│  └─ gaussian-wrapping/result.json
└─ config/
   ├─ colmap.yaml
   ├─ 3dgs.yaml
   ├─ langsplat.yaml
   └─ gaussian-wrapping.yaml
```

## 2. 固定目录与文件含义

- `progress.json`：任务总状态、阶段状态、时间、错误信息与 `artifacts` 聚合来源。
- `input/`：上传的输入图片（创建任务时写入）。
- `config/*.yaml`：创建任务时物化的阶段配置，后续执行按该配置读取。
- `artifacts/{stage}/result.json`：每个阶段完成后写入的标准产物索引文件（相对路径形式）。
- `colmap/`、`output/`、`langsplat*`：各 worker 运行后的实际产物目录。

## 3. 每个 Worker 产物

### 3.1 colmap worker

### 输入要求

- `input/` 下至少一张图片。

### 产出位置

- 产出先由容器写到 job 根目录，再被整理进 `colmap/`：
  - `colmap/sparse/0`（稀疏重建，后续阶段关键输入）
  - `colmap/images`
  - `colmap/distorted`
  - `colmap/stereo`
  - `colmap/run-colmap-geometric.sh`
  - `colmap/run-colmap-photometric.sh`

### 对应 artifacts 文件

- `artifacts/colmap/result.json`（关键字段）：
  - `sparse_dir: "colmap/sparse/0"`
  - `images_dir: "colmap/images"`
  - `result: "artifacts/colmap/result.json"`

### 3.2 3dgs worker

### 输入要求

- `colmap/sparse` 存在。

### 产出位置

- 固定输出根目录：`output/`（可由 `GS_OUTPUT_RELATIVE` 覆盖）。
- 至少需要存在：
  - `output/point_cloud/iteration_{N}/point_cloud.ply`
- 通常同时会产生：
  - `output/chkpnt{N}.pth`

其中 `N` 来自 `config/3dgs.yaml` 的 `training.output_iteration`。

### 对应 artifacts 文件

- `artifacts/3dgs/result.json`（关键字段）：
  - `ply: "output/point_cloud/iteration_{N}/point_cloud.ply"`
  - `result: "artifacts/3dgs/result.json"`

### 3.3 langsplat worker

### 输入要求

- `colmap/sparse` 存在；
- `output/chkpnt{N}.pth` 存在（`N` 与 3DGS 的 `output_iteration` 对齐）。

### 产出位置

- 模型目录：`{model_relative}/`（默认 `langsplatv2/`，可配置/环境变量覆盖）。
- 后端只校验“目录存在且非空”，因此内部文件结构由 LangSplatV2 自身决定（例如 checkpoint、特征文件、日志等）。

### 对应 artifacts 文件

- `artifacts/langsplat/result.json`（关键字段）：
  - `model_dir: "{model_relative}"`
  - `result: "artifacts/langsplat/result.json"`

### 3.4 gaussian-wrapping worker

### 输入要求

- `colmap/sparse` 存在；
- `output/point_cloud/iteration_{N}/point_cloud.ply` 存在。

### 产出位置

- 产物写入 `output/`。
- 后端按 `config/gaussian-wrapping.yaml -> outputs` 中的候选文件名查找：
  - `mesh_ply_names`（默认常见：`mesh_ours_2pivots_post.ply`）
  - `mesh_textured_ply_names`（默认常见：`mesh_ours_2pivots_post_texture_refined_999.ply`）

只要两类里任意一个命中即视为成功。

### 对应 artifacts 文件

- `artifacts/gaussian-wrapping/result.json` 可能包含：
  - `mesh_ply: "output/xxx.ply"`
  - `mesh_textured_ply: "output/yyy.ply"`
  - `result: "artifacts/gaussian-wrapping/result.json"`

## 4. 下载接口与产物键对应

- `/api/jobs/{job_id}/download/3dgs` -> `artifacts["3dgs"]["ply"]`
- `/api/jobs/{job_id}/download/mesh` -> 优先 `mesh_textured_ply`，其次 `mesh_ply`
- `/api/jobs/{job_id}/result` -> 当前实现仅返回 `output_ply`（即 `3dgs` 的 `ply`）

如果需要让 `/result` 返回 mesh，需要另行调整状态聚合逻辑。
