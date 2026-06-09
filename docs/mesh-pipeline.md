# 图像到 Mesh 流水线

本文说明从多张图片生成 mesh 的完整路线、路线选择方式，以及各阶段职责与产物。

## 概览

图片输入（`input_mode=images`，`outputs: ["mesh"]`）时，Task Server 会规划 COLMAP 稀疏重建、高斯训练、mesh 提取与纹理优化。训练阶段有两种路线可选：

| `options.mesh_route` | 阶段链 | 说明 |
|----------------------|--------|------|
| `mesh_first`（默认） | `colmap → gw-train → gaussian-wrapping` | 使用 Gaussian Wrapping 自带训练，训练与提取在同一技术栈内完成 |
| `3dgs_first` | `colmap → 3dgs → gaussian-wrapping` | 旧路线：先用 Inria 3DGS 训练，再从 native PLY 提取 mesh |

对外接口保持一致：无论走哪条路线，最终 mesh 产物仍登记为 `mesh`、`mesh_textured`（以及可选的 `mesh_obj`、`mesh_glb` 等），客户端无需感知内部阶段差异。

查询可用路线：

```http
GET /api/v1/capabilities
```

响应中包含 `mesh_routes`、`default_mesh_route` 与 `stage_presets["gw-train"]`。

## 数据流

### mesh_first（默认）

```text
input/*.jpg|png
    ↓
colmap/                    ← COLMAP 稀疏重建
    ↓
output/                    ← GW train（gaussian_wrapping/train.py）
  point_cloud/iteration_N/point_cloud.ply
  chkpntN.pth
    ↓
output/                    ← GW extract + texture
  mesh_*.ply
  mesh_*_texture_refined_*.ply
```

### 3dgs_first（回退）

```text
input/*.jpg|png
    ↓
colmap/
    ↓
output/                    ← Inria 3DGS train（gaussian-splatting/train.py）
  point_cloud/iteration_N/point_cloud.ply
  chkpntN.pth
    ↓
output/                    ← GW extract + texture（同上）
  mesh_*.ply
```

两条路线在 `gaussian-wrapping` 阶段使用相同的提取脚本 `extract_and_texture_from_native_3dgs.py`，读取路径均为 `output/point_cloud/iteration_{N}/point_cloud.ply`。区别在于 `N` 及训练参数来自 `gw-train` 还是 `3dgs` 配置。

## 何时用哪条路线

| 场景 | 建议路线 |
|------|----------|
| 仅需 mesh，追求 GW 一体化训练质量 | `mesh_first`（默认，无需传参） |
| 需与旧版 3DGS → GW extract 流程对比或回退 | `3dgs_first` |
| 同时请求 `mesh` 与 `language_model` | 自动合并：`colmap → 3dgs → gw-train → langsplat → gaussian-wrapping`（LangSplat 仍依赖 Inria 3DGS checkpoint） |
| 同时请求 `mesh` 与 `point_cloud` | `colmap → 3dgs → gw-train → gaussian-wrapping`（点云来自 3dgs，mesh 来自 gw-train） |
| 已有 native 3DGS PLY，跳过重建 | `input_mode: native_3dgs_ply`，仅 `3dgs-to-pc`（见 [jobs-worker-output-structure.md](jobs-worker-output-structure.md)） |

## 请求示例

### 默认 mesh_first

```json
{
  "outputs": ["mesh"],
  "options": {
    "stage_presets": {
      "colmap": "fast",
      "gw-train": "mid",
      "gaussian-wrapping": "high_geo_tex"
    },
    "mesh_formats": ["ply", "obj", "glb"]
  }
}
```

### 回退 3dgs_first

```json
{
  "outputs": ["mesh"],
  "options": {
    "mesh_route": "3dgs_first",
    "stage_presets": {
      "3dgs": "mid",
      "gaussian-wrapping": "high_geo_tex"
    }
  }
}
```

### mesh + 语言特征

```json
{
  "outputs": ["mesh", "language_model"],
  "options": {
    "stage_presets": {
      "3dgs": "mid",
      "gw-train": "mid",
      "langsplat": "small",
      "gaussian-wrapping": "high_geo"
    }
  }
}
```

## 阶段职责

### colmap

- Worker：`colmap-worker`
- 输入：`input/` 下的图片
- 产出：`colmap/sparse/0`、`colmap/images`

### gw-train（mesh_first）

- Worker：`gaussian-wrapping` 镜像
- 脚本：`gaussian_wrapping/train.py`
- 输入：`colmap/sparse`
- 产出：
  - `output/point_cloud/iteration_{N}/point_cloud.ply`
  - `output/chkpnt{N}.pth`
- 配置：`config/gw-train.yaml`，分区见 [yaml-config.md](yaml-config.md#gw-train)
- 训练档位 preset：`small`（12000 iter）、`mid`（30000）、`high`（45000）

### 3dgs（3dgs_first 或混合输出）

- Worker：task-server 内子进程
- 脚本：`gaussian-splatting/train.py`
- 配置：`config/3dgs.yaml`
- 产物路径格式与 gw-train 相同，但训练算法为 Inria 原生 3DGS

### gaussian-wrapping

- Worker：`gaussian-wrapping` 镜像
- 脚本：`extract_and_texture_from_native_3dgs.py`
- 输入：COLMAP 数据 + 上游训练产出的 PLY
- `--iteration` 由上游训练的 `training.output_iteration` 自动注入，不在 `gaussian-wrapping.yaml` 中配置
- 产出：几何 mesh PLY、纹理优化后的 mesh PLY
- 提取/纹理参数独立配置，preset 如 `simple`、`high_geo`、`high_geo_tex`

## 参数档位

训练档位与提取档位分开选择，互不影响：

| 用途 | stage | preset 示例 |
|------|-------|-------------|
| GW 训练速度与质量 | `gw-train` | `small` / `mid` / `high` |
| Inria 3DGS 训练（3dgs_first 或混合输出） | `3dgs` | `small` / `mid` / `high` |
| mesh 几何与纹理质量 | `gaussian-wrapping` | `simple` / `high_geo` / `high_geo_tex` |
| COLMAP 速度 | `colmap` | `fast` / `general` / `video` |

`gw-train` 默认使用 `rasterizer: ours`，与 `gaussian-wrapping` 默认提取参数 `sdf_mode: ours` 对齐。

## 产物与下载

| artifact_id | 来源阶段 | 说明 |
|-------------|----------|------|
| `point_cloud` | `3dgs` 或 `gw-train` | 训练产出的高斯点云 PLY |
| `mesh` | `gaussian-wrapping` | 几何 mesh PLY |
| `mesh_textured` | `gaussian-wrapping` | 纹理优化后的 mesh PLY |
| `mesh_obj` / `mesh_glb` | Task Server 转换 | 由 `mesh_formats` 触发 |

下载方式不变：

```http
GET /api/v1/jobs/{job_id}/artifacts/mesh/download
GET /api/v1/jobs/{job_id}/artifacts/mesh_textured/download
```

## 任务状态中的阶段名

对外 artifact id 与请求格式不变，但任务状态 `planned_stages`、`current_stage_id` 会反映实际执行的阶段。`mesh_first` 默认计划中包含 `gw-train` 而非 `3dgs`。

## 进一步阅读

- [yaml-config.md](yaml-config.md)：各阶段 YAML 参数与覆盖规则
- [backend-api-frontend-guide.md](backend-api-frontend-guide.md)：API 字段与对接流程
- [jobs-worker-output-structure.md](jobs-worker-output-structure.md)：job 目录与各 worker 产物路径
