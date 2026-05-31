# YAML 阶段参数配置

流水线四个算法阶段（colmap / 3dgs / langsplat / gaussian-wrapping）的参数均通过 YAML 管理，由 orchestrator 读取后转换为各 worker 的 CLI 参数。

## 配置文件位置

| 层级 | 路径 | 作用 |
|------|------|------|
| 全局默认 | `visionary_tasks/configs/{stage}/default.yaml` | 新 job 的初始值 |
| 单 job | `data/jobs/{job_id}/config/{stage}.yaml` | 创建时物化，可手改 |

`{stage}` 取值：`colmap`、`3dgs`、`langsplat`、`gaussian-wrapping`。

创建 job 时会把合并后的完整配置写入 job 目录。之后改全局 `default.yaml` **不影响已有 job**。

## 合并优先级

从低到高：

1. 仓库 `default.yaml`
2. 创建 job 时上传的 override（API 表单字段，见下）
3. 环境变量（最高）

## 修改方式

**改全局默认** — 编辑 `visionary_tasks/configs/*/default.yaml`。`compose.yaml` 已挂载 `./visionary_tasks`，保存即生效，无需 rebuild。

**改单个 job** — 编辑 `data/jobs/{job_id}/config/*.yaml`，然后重跑该 job（当前无 rerun API，需自行触发）。

**创建时上传 override** — `POST /api/jobs` 可选字段：

| 表单字段 | 对应阶段 |
|----------|----------|
| `colmap_config` | colmap |
| `gs_config` | 3dgs |
| `langsplat_config` | langsplat |
| `gaussian_wrapping_config` | gaussian-wrapping |

只需上传要改的字段（partial YAML），会与 default deep merge。

## 阶段间耦合

**3DGS `training.output_iteration`**

- 决定产物 PLY / checkpoint 路径（`output/point_cloud/iteration_{N}/`、`chkpnt{N}.pth`）
- 必须同时出现在 `save_iterations` 和 `checkpoint_iterations` 中（加载时校验）
- LangSplat 的 `--start_checkpoint` 依赖此值

**Gaussian Wrapping `extraction.iteration`**

- 创建 job 时自动对齐 3DGS 的 `output_iteration`
- 每次执行时再次从 3DGS job config 同步；`WRAPPING_ITERATION` 环境变量可覆盖

**GW 产物文件名**

- `outputs.mesh_ply_names` / `outputs.mesh_textured_ply_names` 须与实际输出一致
- 默认期望 `mesh_ours_2pivots_post.ply` 等，依赖 `sdf_mode`、`n_pivots`、`postprocess`、`texture_n_iter` 等参数

## 各阶段 YAML 结构

**colmap** — `converter.*`：对应 `convert.py`（`camera`、`no_gpu`、`skip_matching`、`resize` 等）。`source_path` 由 executor 注入为 `/job`。

**3dgs** — `model` / `optimization` / `pipeline` / `training`：对应 `gaussian-splatting/train.py`。`-s` / `-m` 由 executor 注入。

**langsplat** — `runtime` / `preprocess` / `model` / `optimization` / `pipeline` / `training`：对应 LangSplatV2 的 `preprocess.py` 与 `train.py`。部署项 `worker_image`、`ckpts_host` 不在 YAML 内。

**gaussian-wrapping** — `extraction` / `texture` / `decimation` / `outputs`：对应 `extract_and_texture_from_native_3dgs.py`。`-s` / `-m` 由 executor 注入。

## 关键参数

完整字段见各 `default.yaml`。日常最常改的是下面这些。

### colmap

| 参数 | 默认 | 作用 |
|------|------|------|
| `converter.camera` | `OPENCV` | 相机模型，须与拍摄设备匹配；错设会导致标定失败或精度差 |
| `converter.no_gpu` | `false` | 为 `true` 时特征提取/匹配走 CPU |
| `converter.skip_matching` | `false` | 为 `true` 时跳过特征提取与匹配，仅做去畸变（需已有 sparse） |
| `converter.resize` | `false` | 为 `true` 时额外生成 `images_2/4/8` 多尺度图像 |

### 3dgs

| 参数 | 默认 | 作用 |
|------|------|------|
| `training.output_iteration` | `500` | 下游读取的 PLY / checkpoint 迭代；改此项须同步 `save_iterations`、`checkpoint_iterations` |
| `optimization.iterations` | `30000` | 总训练步数 |
| `model.resolution` | `-1` | 训练图像缩放（`-1` 为原图；正整数表示最长边像素） |
| `model.white_background` | `false` | 白底场景设为 `true` |
| `optimization.densify_until_iter` | `15000` | 停止增删高斯点的迭代上限 |
| `optimization.densify_grad_threshold` | `0.0002` | 分裂/克隆阈值；越小点越密 |

### langsplat

| 参数 | 默认 | 作用 |
|------|------|------|
| `model.feature_level` | `0` | 语言特征层级（0–3）；越高语义越抽象，train 输出目录会带 `_0` 等后缀 |
| `optimization.vq_layer_num` | `1` | VQ 层数 |
| `optimization.codebook_size` | `64` | 码本大小 |
| `training.topk` | `4` | 特征检索 top-k |
| `training.cos_loss` | `true` | 为 `true` 用余弦损失；`false` 时可配合 `l1_loss` |
| `optimization.iterations` | `30000` | 总训练步数 |
| `preprocess.sam_ckpt_path` | `ckpts/sam_vit_h_4b8939.pth` | SAM 权重路径（容器内，依赖 `ckpts` 挂载） |

### gaussian-wrapping

| 参数 | 默认 | 作用 |
|------|------|------|
| `extraction.iteration` | `500` | 读取哪一步的 3DGS PLY；通常与 3DGS `output_iteration` 一致 |
| `extraction.n_pivots` | `2` | pivot 数量；影响 mesh 拓扑与文件名（如 `2pivots`） |
| `extraction.sdf_mode` | `ours` | 等值面提取后端；`exact_computation` 更准但更慢 |
| `extraction.postprocess` | `true` | 抽取后 mesh 清理（去大边等） |
| `texture.texture_n_iter` | `1000` | 纹理优化步数；影响输出文件名末缀（如 `_999.ply`） |
| `decimation.apply_decimation` | `false` | 纹理前是否 Blender 减面 |
| `decimation.decimate_ratio` | `0.3` | 保留面数比例 |
| `outputs.mesh_ply_names` | 见 default | executor 查找 mesh 的文件名，改抽取参数后须同步 |

## 环境变量覆盖

仍可用于部署级覆盖，优先级高于 YAML：

| 变量 | 阶段 |
|------|------|
| `COLMAP_CAMERA_MODEL` | colmap |
| `GS_ITERATIONS`、`GS_SAVE_ITERATION` | 3dgs |
| `LANGSPLAT_FEATURE_LEVEL`、`LANGSPLAT_VQ_LAYER_NUM`、`LANGSPLAT_CODEBOOK_SIZE`、`LANGSPLAT_TOPK`、`LANGSPLAT_COS_LOSS`、`LANGSPLAT_MODEL_RELATIVE` | langsplat |
| `WRAPPING_PIVOTS`、`WRAPPING_ITERATION`、`WRAPPING_SDF_MODE`、`WRAPPING_RASTERIZER`、`WRAPPING_MESH_PLY_NAMES`、`WRAPPING_MESH_TEXTURED_PLY_NAMES` | gaussian-wrapping |

Worker 镜像名（`COLMAP_WORKER_IMAGE`、`LANGSPLAT_WORKER_IMAGE`、`WRAPPING_WORKER_IMAGE`）只在 `Settings` / `compose.yaml` 中配置，不进 job YAML。
