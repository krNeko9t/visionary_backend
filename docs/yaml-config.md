# YAML 阶段参数配置

各算法阶段的参数通过 YAML 管理，由 stage 实现读取后转换为 worker 命令参数。

## 配置文件位置

| 层级 | 路径 | 作用 |
|------|------|------|
| 全局默认 | `visionary_tasks/configs/{stage}/default.yaml` | 所有新任务的初始值 |
| 单任务 | `data/jobs/{job_id}/config/{stage}.yaml` | 创建时物化，可手动修改 |

`{stage}` 取值：`colmap`、`3dgs`、`langsplat`、`gaussian-wrapping`、`3dgs-to-pc`。

创建任务时写入 job 目录。之后修改全局 default 不影响已有 job。

## 合并优先级

从低到高：

1. 仓库 `default.yaml`
2. preset 文件，如 `configs/3dgs/small.yaml`
3. 创建任务时 `spec.advanced.stage_overrides` 中的覆盖
4. 单任务 `config/*.yaml` 中已有内容在加载时作为基础

## 修改方式

改全局默认：编辑 `visionary_tasks/configs/*/default.yaml`。compose 已挂载 `./visionary_tasks`，保存即生效。

改单个 job：编辑 `data/jobs/{job_id}/config/*.yaml`，然后重跑该 job。

创建时覆盖：在 `POST /api/v1/jobs` 的 `spec` 中传入 `advanced.stage_overrides`：

```json
{
  "outputs": ["point_cloud"],
  "preset": "standard",
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

只需上传要改的字段，与 default deep merge。

`preset` 可选 `standard`、`small`、`mid`、`high`。`small`、`mid`、`high` 会加载 `configs/3dgs/` 下对应预设文件。

## 阶段间耦合

**3DGS `training.output_iteration`**

- 决定产物 PLY 与 checkpoint 路径：`output/point_cloud/iteration_{N}/`、`chkpnt{N}.pth`
- 必须同时出现在 `save_iterations` 与 `checkpoint_iterations` 中
- LangSplat 的 `--start_checkpoint` 依赖此值

**Gaussian Wrapping `extraction.iteration`**

- 创建任务时自动对齐 3DGS 的 `output_iteration`
- 每次执行时从 3DGS job config 再次同步

**3dgs-to-pc `extraction.iteration`**

- `native_3dgs_ply` 模式创建任务时对齐 `spec.options.iteration`
- 每次执行时从 3DGS job config 再次同步
- 决定读取的 PLY 路径 `output/point_cloud/iteration_{N}/point_cloud.ply`

**GW 产物文件名**

- `outputs.mesh_ply_names` 与 `outputs.mesh_textured_ply_names` 须与实际输出一致
- 默认期望 `mesh_ours_2pivots_post.ply` 等，依赖 `sdf_mode`、`n_pivots`、`postprocess`、`texture_n_iter`

## 各阶段 YAML 结构

**colmap**：`converter.*` 对应 `convert.py`。`source_path` 由 stage 注入为 `/job`。

**3dgs**：`model`、`optimization`、`pipeline`、`training` 对应 `gaussian-splatting/train.py`。`-s`、`-m` 由 stage 注入。

**langsplat**：`runtime`、`preprocess`、`model`、`optimization`、`pipeline`、`training` 对应 LangSplatV2 的 `preprocess.py` 与 `train.py`。

**gaussian-wrapping**：`extraction`、`texture`、`decimation`、`outputs` 对应 `extract_and_texture_from_native_3dgs.py`。

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
| `training.output_iteration` | `500` | 下游读取的 PLY 与 checkpoint 迭代 |
| `optimization.iterations` | `30000` | 总训练步数 |
| `model.resolution` | `-1` | 训练图像缩放 |
| `model.white_background` | `false` | 白底场景设为 true |
| `optimization.densify_until_iter` | `15000` | 停止增删高斯点的迭代上限 |
| `optimization.densify_grad_threshold` | `0.0002` | 分裂与克隆阈值 |

### langsplat

| 参数 | 默认 | 作用 |
|------|------|------|
| `model.feature_level` | `0` | 语言特征层级 |
| `optimization.vq_layer_num` | `1` | VQ 层数 |
| `optimization.codebook_size` | `64` | 码本大小 |
| `training.topk` | `4` | 特征检索 top-k |
| `training.cos_loss` | `true` | 余弦损失开关 |
| `optimization.iterations` | `30000` | 总训练步数 |
| `preprocess.sam_ckpt_path` | `ckpts/sam_vit_h_4b8939.pth` | SAM 权重路径 |

### gaussian-wrapping

| 参数 | 默认 | 作用 |
|------|------|------|
| `extraction.iteration` | `500` | 读取哪一步的 3DGS PLY |
| `extraction.n_pivots` | `2` | pivot 数量 |
| `extraction.sdf_mode` | `ours` | 等值面提取后端 |
| `extraction.postprocess` | `true` | mesh 清理 |
| `texture.texture_n_iter` | `1000` | 纹理优化步数 |
| `decimation.apply_decimation` | `false` | 纹理前减面 |
| `decimation.decimate_ratio` | `0.3` | 保留面数比例 |
| `outputs.mesh_ply_names` | 见 default | executor 查找 mesh 的文件名 |

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

镜像名在 `config/*.yaml` 的 `worker_image` 或 `runtime.worker_image` 中配置，也可通过 compose 环境覆盖。
