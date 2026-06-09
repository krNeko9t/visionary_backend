# 后端 API 对接指南

本文说明 Task Server 对外 API 的设计与调用方式。

## 设计原则

调用方通过 `outputs` 声明目标产物，服务端规划并执行所需阶段。产物通过稳定的 `artifact_id` 访问，不依赖内部阶段名称。

任务创建后立即返回 `job_id`，执行在后台完成。任务状态、阶段状态、产物索引统一保存在 `state/job.json`。进度由阶段权重与 `events/*.jsonl` 中的事件共同计算。

## 产物与阶段映射

| output | input_mode | 规划阶段 |
|--------|------------|----------|
| `point_cloud` | `images` | colmap → 3dgs |
| `mesh` | `images` | colmap → 3dgs → gaussian-wrapping |
| `mesh` | `native_3dgs_ply` | 3dgs-to-pc |
| `language_model` | `images` | colmap → 3dgs → langsplat |

`spec.options.language_features: true` 时自动追加 `language_model` 输出。

一次请求可以同时声明多个 `outputs`，服务端会按阶段并集合并规划结果。常规调用只需要传 `outputs` 和必要的 `options`；`advanced` 主要用于调试或精确覆盖阶段参数。

## API 列表

### 健康检查

`GET /healthz`

```json
{ "status": "ok" }
```

### 查询能力

`GET /api/v1/capabilities`

返回支持的 `outputs`、`input_modes`、`stage_presets`、`stages`、`mesh_formats`。调用方应优先使用这个接口动态生成 UI 选项，不要在前端硬编码 preset 名称。

关键字段：

| 字段 | 说明 |
|------|------|
| `outputs` | 可请求的目标产物，含自动规划阶段提示 |
| `input_modes` | 输入模式、允许文件类型、该模式下允许的 outputs |
| `stage_presets` | 按 stage 分组的 YAML 预设，例如 `{"3dgs": ["high", "mid", "small"]}` |
| `stages` | 阶段顺序、依赖与输入提示 |
| `mesh_formats` | `spec.options.mesh_formats` 可选值 |

### 创建任务

`POST /api/v1/jobs`

`Content-Type: multipart/form-data`

| 字段 | 说明 |
|------|------|
| `files` | 输入文件。`images` 模式上传图片，支持 jpg、jpeg、png、bmp、webp。`native_3dgs_ply` 模式上传一个 `.ply` |
| `spec` | JSON 字符串，见下方结构 |

`spec` 结构：

```json
{
  "outputs": ["point_cloud"],
  "options": {
    "input_mode": "images",
    "language_features": false,
    "mesh_formats": ["ply"],
    "stage_presets": {
      "3dgs": "small",
      "colmap": "fast"
    }
  },
  "advanced": {
    "stages": ["colmap", "3dgs"],
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

- `outputs`：必填，目标产物列表
- `options.input_mode`：默认 `images`；可选值以 `GET /api/v1/capabilities` 返回为准
- `options.stage_presets`：按 stage 选择 YAML 预设。不传时使用各 stage 的 `default.yaml`；不存在顶层 `preset` 字段
- `options.language_features`：为 `true` 时自动追加 `language_model` 输出，仅支持 `images`
- `options.mesh_formats`：控制 mesh 导出格式，默认 `["ply"]`，可选 `ply`、`obj`、`glb`。仅 `outputs` 包含 `mesh` 时可设置
- `advanced.stages`：调试用途，可显式覆盖自动规划阶段；必须满足阶段依赖
- `advanced.stage_overrides`：创建任务时覆盖阶段 YAML 参数，按字段 deep merge

返回示例：

```json
{
  "job_id": "9c4f7428e2aa",
  "status": "queued",
  "message": "任务已创建",
  "outputs": ["point_cloud"],
  "planned_stages": ["colmap", "3dgs"]
}
```

### 查询任务状态

`GET /api/v1/jobs/{job_id}`

| 字段 | 说明 |
|------|------|
| `status` | queued、running、done、error、cancelled |
| `progress` | 0 到 100 |
| `current_stage_id` | 当前运行阶段 |
| `planned_stages` | 本次规划的阶段列表 |
| `stages` | 各阶段状态与进度 |
| `artifacts` | 产物列表 |

### 列出产物

`GET /api/v1/jobs/{job_id}/artifacts`

返回该任务全部产物，每项包含 `id`、`stage_id`、`type`、`path`、`downloadable`。

常见 `artifact_id`：

| artifact_id | 说明 |
|-------------|------|
| `point_cloud` | 3DGS 点云 ply |
| `mesh` | mesh ply |
| `mesh_obj` | mesh OBJ |
| `mesh_glb` | mesh GLB |
| `mesh_textured` | 带纹理 mesh ply |
| `mesh_textured_obj` | 带纹理 mesh OBJ |
| `mesh_textured_glb` | 带纹理 mesh GLB |
| `language_model` | LangSplat 最终导出目录，路径形如 `langsplat_export/chkpnt{N}/` |

### 下载产物

`GET /api/v1/jobs/{job_id}/artifacts/{artifact_id}/download`

返回文件流。仅普通文件类型的 `downloadable: true` 产物适合直接下载。

`language_model` 当前登记为目录型产物，状态接口会返回路径和 metadata，但下载接口使用文件流响应；调用方不要把它当单个文件直接下载。

常见错误响应：

| HTTP 状态 | 场景 |
|-----------|------|
| `400` | `spec` JSON 解析失败、字段校验失败、文件类型不支持、产物不可下载 |
| `404` | job 不存在、artifact id 不存在、产物文件不存在 |
| `409` | 任务尚未完成时下载尚未落盘的产物 |

### 查询进度事件

`GET /api/v1/jobs/{job_id}/events`

返回各阶段写入的进度事件列表，包含 `event_type`、`progress`、`iteration`、`message`。

### 取消任务

`POST /api/v1/jobs/{job_id}/cancel`

记录取消请求。取消是异步语义：任务会进入取消流程，但不保证正在运行的 worker 立刻停止。已经结束的任务不会被重新取消。

## 前端接入步骤

1. 初始化时请求 `GET /api/v1/capabilities`，展示可选 outputs、input modes、stage presets 与 mesh formats
2. 构建 `FormData`：图片写入 `files`，`spec` 序列化为 JSON 字符串
3. 保存返回的 `job_id`，每 2 秒轮询 `GET /api/v1/jobs/{job_id}`
4. 依据 `status` 更新界面：running 展示 `progress` 与 `current_stage_id`，done 开放下载，error 展示 `error`
5. 下载时请求 `/api/v1/jobs/{job_id}/artifacts/{artifact_id}/download`

## 最小示例

```html
<input id="files" type="file" multiple accept=".jpg,.jpeg,.png,.bmp,.webp" />
<button id="createBtn">创建任务</button>
<pre id="log"></pre>

<script>
  const API_BASE = "http://localhost:8000";
  const log = (v) => (document.getElementById("log").textContent = JSON.stringify(v, null, 2));

  async function createJob() {
    const files = Array.from(document.getElementById("files").files || []);
    if (!files.length) return log({ error: "请选择图片" });

    const spec = { outputs: ["point_cloud"] };
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    fd.append("spec", JSON.stringify(spec));

    const res = await fetch(`${API_BASE}/api/v1/jobs`, { method: "POST", body: fd });
    const created = await res.json();
    if (!res.ok) return log(created);

    const jobId = created.job_id;
    log(created);

    const timer = setInterval(async () => {
      const r = await fetch(`${API_BASE}/api/v1/jobs/${jobId}`);
      const status = await r.json();
      log(status);
      if (status.status === "done" || status.status === "error") {
        clearInterval(timer);
        if (status.status === "done") {
          window.open(`${API_BASE}/api/v1/jobs/${jobId}/artifacts/point_cloud/download`, "_blank");
        }
      }
    }, 2000);
  }

  document.getElementById("createBtn").addEventListener("click", createJob);
</script>
```

## 联调

- 健康检查：`GET /healthz`
- 接口文档：`http://localhost:8000/docs`

## 输入模式

| input_mode | 上传文件 | 允许 outputs | 规划阶段 |
|------------|----------|--------------|----------|
| `images` | 图片 | point_cloud、mesh、language_model | 按 output 自动展开 |
| `native_3dgs_ply` | 一个 native 3DGS point_cloud.ply | mesh | 3dgs-to-pc |

图片全流程的 mesh 由 `gaussian-wrapping` 生成，可产出 `mesh` 与 `mesh_textured`。

`native_3dgs_ply` 的 mesh 由 `3dgs-to-pc` 生成，从 PLY 采样稠密点云后做 Poisson 重建，产出 `mesh`，无纹理。

`native_3dgs_ply` 模式必须上传恰好一个 `.ply` 文件。该文件需要是 native 3DGS point cloud，PLY header 至少包含 `x`、`y`、`z`、`opacity`、`f_dc_0`、`f_dc_1`、`f_dc_2`，并包含 `f_rest_*`、`scale_*`、`rot_*` 字段。

### 从已有 ply 提取 mesh

`spec` 示例：

```json
{
  "outputs": ["mesh"],
  "options": {
    "input_mode": "native_3dgs_ply",
    "iteration": 30000
  }
}
```

multipart 上传一个 `.ply` 文件到 `files`。

服务端将 ply 写入 `output/point_cloud/iteration_{N}/point_cloud.ply`，并写入 `output/cfg_args`。

`N` 来自 `spec.options.iteration`，默认 30000。

产物 artifact id 为 `mesh`，文件名为 `output/mesh_poisson.ply`。

