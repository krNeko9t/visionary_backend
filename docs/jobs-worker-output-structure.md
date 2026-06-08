# Jobs 目录与 Worker 产物

本文说明单个任务目录的文件结构，以及各 worker 的输入要求与产出位置。

## 任务根目录

默认 `JOBS_ROOT` 为 `/data/jobs`，单个任务目录为 `/data/jobs/{job_id}`。

```text
jobs/{job_id}/
  state/job.json
  input/
  config/
  stages/
  events/
  colmap/
  output/
  langsplatv2/
```

## 固定目录含义

| 路径 | 含义 |
|------|------|
| `state/job.json` | 任务总状态、阶段状态、产物索引 |
| `input/` | 上传的输入图片 |
| `config/*.yaml` | 创建任务时物化的阶段配置 |
| `stages/{stage_id}/result.json` | 阶段标准结果，含 artifact 列表 |
| `events/{stage_id}.jsonl` | 阶段进度事件，每行一条 JSON |
| `colmap/`、`output/`、`langsplatv2/` | worker 实际产物目录 |

## colmap

输入要求：`input/` 下至少一张图片。

产出位置：容器先将产物写到 job 根目录，服务端整理到 `colmap/`。

- `colmap/sparse/0`
- `colmap/images`
- `colmap/distorted`
- `colmap/stereo`

阶段结果写入 `stages/colmap/result.json`，登记 artifact：

- `colmap_sparse` → `colmap/sparse/0`
- `colmap_images` → `colmap/images`

## 3dgs

输入要求：`colmap/sparse` 存在。

产出位置：`output/`，目录名可由 `config/3dgs.yaml` 中 `runtime.output_relative` 覆盖。

- `output/point_cloud/iteration_{N}/point_cloud.ply`
- `output/chkpnt{N}.pth`

`N` 来自 `config/3dgs.yaml` 的 `training.output_iteration`。

阶段结果登记 artifact：

- `point_cloud` → ply 文件路径
- `gs_checkpoint` → checkpoint 路径

## langsplat

输入要求：

- `colmap/sparse` 存在
- `output/chkpnt{N}.pth` 存在，`N` 与 3DGS `output_iteration` 对齐

产出位置：`langsplatv2/`，目录名由 `config/langsplat.yaml` 中 `runtime.model_relative` 决定。

阶段结果登记 artifact：

- `language_model` → 模型目录路径

## gaussian-wrapping

用于 `input_mode=images` 的 mesh 输出。

输入要求：

- `colmap/sparse` 存在
- `output/point_cloud/iteration_{N}/point_cloud.ply` 存在

产出位置：`output/` 下，文件名由 `config/gaussian-wrapping.yaml` 的 `outputs` 段定义。

默认查找：

- `mesh_ours_2pivots_post.ply`
- `mesh_ours_2pivots_post_texture_refined_999.ply`

阶段结果登记 artifact：

- `mesh` → mesh ply 路径
- `mesh_textured` → 带纹理 mesh ply 路径

## 3dgs-to-pc

用于 `input_mode=native_3dgs_ply` 的 mesh 输出。

输入要求：

- `output/point_cloud/iteration_{N}/point_cloud.ply` 存在

产出位置：`output/` 下，文件名由 `config/3dgs-to-pc.yaml` 的 `outputs` 段定义。

默认查找：

- `mesh_poisson.ply`

阶段结果登记 artifact：

- `mesh` → mesh ply 路径



## mesh 多格式导出

`gaussian-wrapping` 与 `3dgs-to-pc` 均产出 PLY mesh。若 `spec.options.mesh_formats` 包含 `obj` 或 `glb`，Task Server 在对应 mesh 阶段完成后将 PLY 转换为派生产物，写入与源 PLY 同目录：

| artifact_id | 文件 | 说明 |
|-------------|------|------|
| `mesh` | 原始 mesh ply | worker 产物 |
| `mesh_obj` | `mesh.obj` | PLY 转换 |
| `mesh_glb` | `mesh.glb` | PLY 转换 |
| `mesh_textured` | 原始 textured ply | 仅 gaussian-wrapping |
| `mesh_textured_obj` | `mesh_textured.obj` | PLY 转换 |
| `mesh_textured_glb` | `mesh_textured.glb` | PLY 转换 |

下载示例：

- `GET /api/v1/jobs/{job_id}/artifacts/mesh_glb/download`
- `GET /api/v1/jobs/{job_id}/artifacts/mesh_textured_glb/download`

## 下载接口

产物通过 artifact id 下载：

- `GET /api/v1/jobs/{job_id}/artifacts/point_cloud/download`
- `GET /api/v1/jobs/{job_id}/artifacts/mesh/download`
- `GET /api/v1/jobs/{job_id}/artifacts/mesh_textured/download`
- `GET /api/v1/jobs/{job_id}/artifacts/mesh_glb/download`

## native_3dgs_ply 模式

`input/` 可为空。上传的 ply 由服务端写入：

```text
output/point_cloud/iteration_{N}/point_cloud.ply
output/cfg_args
```

`N` 来自 `spec.options.iteration`。

仅执行 `3dgs-to-pc` 阶段，产物为 `mesh`，对应 `output/mesh_poisson.ply`。

