# YAML 阶段参数配置

各算法阶段的参数通过 YAML 管理，由 stage 实现读取后转换为 worker 命令参数。

## 配置文件位置

| 层级 | 路径 | 作用 |
|------|------|------|
| 全局默认 | `visionary_tasks/configs/{stage}/default.yaml` | 所有新任务的初始值 |
| 阶段预设 | `visionary_tasks/configs/{stage}/{preset}.yaml` | 创建任务时通过 `options.stage_presets` 选择 |
| 单任务 | `data/jobs/{job_id}/config/{stage}.yaml` | 创建时物化，可手动修改 |

`{stage}` 取值：`colmap`、`3dgs`、`langsplat`、`gaussian-wrapping`、`3dgs-to-pc`。

创建任务时写入 job 目录。之后修改全局 default 不影响已有 job。

## 合并优先级

创建任务时从低到高合并：

1. 仓库 `default.yaml`
2. `spec.options.stage_presets` 指定的阶段 preset 文件，如 `configs/3dgs/small.yaml`
3. 创建任务时 `spec.advanced.stage_overrides` 中的覆盖

合并后的结果会写入 `data/jobs/{job_id}/config/{stage}.yaml`。阶段执行时读取单任务配置；之后修改全局 default 或 preset 不影响已有 job。

## 修改方式

改全局默认：编辑 `visionary_tasks/configs/*/default.yaml`。compose 已挂载 `./visionary_tasks`，保存即生效。

改单个 job：编辑 `data/jobs/{job_id}/config/*.yaml`。当前 HTTP API 没有“重跑已有 job”的接口；这类修改只适合在阶段执行前调整，或供手动/调试流程使用。

创建时覆盖：在 `POST /api/v1/jobs` 的 `spec` 中传入 `advanced.stage_overrides`：

```json
{
  "outputs": ["point_cloud"],
  "options": {
    "stage_presets": {
      "3dgs": "small",
      "colmap": "fast"
    }
  },
  "advanced": {
    "stage_overrides": {
      "3dgs": {
        "training": {
          "output_iteration": 30000
        }
      }
    }
  }
}
```

只需上传要改的字段，会与 default 和所选 stage preset deep merge。

`stage_presets` 是按 stage 选择的对象，不存在顶层 `preset` 字段。不传时使用对应 stage 的 `default.yaml`。

可用 preset 以 `GET /api/v1/capabilities` 返回的 `stage_presets` 为准。当前仓库常见值：

| stage | presets |
|-------|---------|
| `colmap` | `fast`、`fisheye`、`general`、`video` |
| `3dgs` | `small`、`mid`、`high` |
| `langsplat` | `small`、`high`、`full` |
| `gaussian-wrapping` | `simple`、`high_geo`、`high_geo_tex` |

## 阶段间耦合

**3DGS `training.output_iteration`**

- 决定产物 PLY 与 checkpoint 路径：`output/point_cloud/iteration_{N}/`、`chkpnt{N}.pth`
- 必须同时出现在 `save_iterations` 与 `checkpoint_iterations` 中
- LangSplat 的 `--start_checkpoint` 依赖此值

**Gaussian Wrapping iteration**

- 不在 `gaussian-wrapping.yaml` 中配置
- 每次执行时从 3DGS job config 的 `training.output_iteration` 注入 worker 命令

**3dgs-to-pc `extraction.iteration`**

- `native_3dgs_ply` 模式创建任务时对齐 `spec.options.iteration`
- 每次执行时从 3DGS job config 再次同步
- 决定读取的 PLY 路径 `output/point_cloud/iteration_{N}/point_cloud.ply`

**GW 产物文件名**

- 服务端会根据 `sdf_mode`、`n_pivots`、`isosurface_value`、`postprocess`、`apply_decimation`、`texture_n_iter` 预测输出文件名
- 默认期望 `mesh_ours_2pivots_post.ply` 与 `mesh_ours_2pivots_post_texture_refined_999.ply`

## 各阶段 YAML 结构

**colmap**：`converter.*` 对应 `convert.py`。`source_path` 由 stage 注入为 `/job`。

**3dgs**：`model`、`optimization`、`pipeline`、`training` 对应 `gaussian-splatting/train.py`。`-s`、`-m` 由 stage 注入。

**langsplat**：`runtime`、`preprocess`、`model`、`optimization`、`pipeline`、`training`、`export` 对应 LangSplatV2 的 `preprocess.py`、`train.py` 与最终导出脚本。

**gaussian-wrapping**：`extraction`、`texture`、`decimation` 对应 `extract_and_texture_from_native_3dgs.py`。

**3dgs-to-pc**：`extraction`、`outputs` 对应 `scripts/ply_to_mesh.py`。

## 关键参数

### colmap

| 参数 | 默认 | 作用 |
|------|------|------|
| `converter.camera` | `OPENCV` | 相机模型 |
| `converter.no_gpu` | `false` | 为 true 时特征提取与匹配走 CPU |
| `converter.skip_matching` | `false` | 为 true 时跳过特征提取与匹配 |
| `converter.resize` | `false` | 为 true 时生成多尺度图像 |

### 3dgs

| 参数 | 默认 | 作用 |
|------|------|------|
| `runtime.worker_image` | `visionary-3dgs-worker:local` | 执行训练的 Docker worker 镜像 |
| `training.output_iteration` | `30000` | 下游读取的 PLY 与 checkpoint 迭代 |
| `optimization.iterations` | `30000` | 总训练步数 |
| `model.resolution` | `-1` | 训练图像缩放 |
| `model.white_background` | `false` | 白底场景设为 true |
| `optimization.densify_until_iter` | `15000` | 停止增删高斯点的迭代上限 |
| `optimization.densify_grad_threshold` | `0.0002` | 分裂与克隆阈值 |

### langsplat

| 参数 | 默认 | 作用 |
|------|------|------|
| `model.feature_levels` | `[0]` | 训练的语言特征层级 |
| `optimization.vq_layer_num` | `1` | VQ 层数 |
| `optimization.codebook_size` | `64` | 码本大小 |
| `training.topk` | `4` | 特征检索 top-k |
| `training.cos_loss` | `true` | 余弦损失开关 |
| `optimization.iterations` | `10000` | 总训练步数 |
| SAM 权重 | `sam_vit_h_4b8939.pth` 放项目 `ckpts/` | 由服务 `ckpts_root`（默认 `/workspace/ckpts`）统一解析，无需在任务 YAML 配置 |
| `export.output_relative` | `langsplat_export` | 最终导出目录 |
| `export.levels` | `[0]` | 最终导出的语言特征层级 |

### gaussian-wrapping

| 参数 | 默认 | 作用 |
|------|------|------|
| 3DGS iteration | 来自 `3dgs.training.output_iteration` | 读取哪一步的 3DGS PLY，由 executor 注入 |
| `extraction.n_pivots` | `2` | pivot 数量 |
| `extraction.sdf_mode` | `ours` | 等值面提取后端 |
| `extraction.postprocess` | `true` | mesh 清理 |
| `texture.texture_n_iter` | `1000` | 纹理优化步数 |
| `decimation.apply_decimation` | `false` | 纹理前减面 |
| `decimation.decimate_ratio` | `0.3` | 保留面数比例 |

### 3dgs-to-pc

| 参数 | 默认 | 作用 |
|------|------|------|
| `extraction.iteration` | `30000` | 读取哪一步的 3DGS PLY |
| `extraction.num_points` | `5000000` | 稠密点云采样数量 |
| `extraction.min_opacity` | `0.05` | 过滤低不透明度高斯 |
| `extraction.poisson_depth` | `10` | Poisson 重建深度 |
| `extraction.clean_pointcloud` | `true` | 点云统计去噪 |
| `outputs.mesh_ply_names` | 见 default | executor 查找 mesh 的文件名 |

## Worker 镜像

镜像名在 `config/*.yaml` 的 `worker_image` 或 `runtime.worker_image` 中配置。3DGS 默认使用 `visionary-3dgs-worker:local`，由 Compose 的 `3dgs-worker` 服务构建。

## mesh 格式导出

`spec.options.mesh_formats` 控制 mesh 派生格式，不属于 stage YAML 参数，也不会写入 `config/*.yaml`。默认 `["ply"]` 仅保留 worker 原始 PLY；需要 OBJ 或 GLB 时在创建任务的 `spec.options` 中指定。
