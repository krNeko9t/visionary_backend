# 后端 API 对接指南

本文说明 Task Server 对外 API 的设计与调用方式。

## 设计原则

调用方通过 `outputs` 声明目标产物，服务端规划并执行所需阶段。产物通过稳定的 `artifact_id` 访问，不依赖内部阶段名称。

任务创建后立即返回 `job_id`，执行在后台完成。任务状态、阶段状态、产物索引统一保存在 `state/job.json`。进度由阶段权重与 `events/*.jsonl` 中的事件共同计算。

## 产物与阶段映射

| output | 规划阶段 |
|--------|----------|
| `point_cloud` | colmap → 3dgs |
| `mesh` | colmap → 3dgs → gaussian-wrapping |
| `language_model` | colmap → 3dgs → langsplat |

`spec.options.language_features: true` 时自动追加 `language_model` 输出。

## API 列表

### 健康检查

`GET /healthz`

```json
{ "status": "ok" }
```

### 查询能力

`GET /api/v1/capabilities`

返回支持的 `outputs`、`presets`、`stages`。

### 创建任务

`POST /api/v1/jobs`

`Content-Type: multipart/form-data`

| 字段 | 说明 |
|------|------|
| `files` | 输入图片，支持 jpg、jpeg、png、bmp、webp，可多文件 |
| `spec` | JSON 字符串，见下方结构 |

`spec` 结构：

```json
{
  "outputs": ["point_cloud"],
  "preset": "standard",
  "options": {
    "language_features": false
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
- `preset`：质量预设，可选 `standard`、`small`、`mid`、`high`
- `options`：业务选项
- `advanced`：调试用途，可显式指定阶段列表与阶段配置覆盖

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
| `mesh_textured` | 带纹理 mesh ply |
| `language_model` | LangSplat 模型目录，不可下载 |

### 下载产物

`GET /api/v1/jobs/{job_id}/artifacts/{artifact_id}/download`

返回文件流。仅 `downloadable: true` 的产物可下载。

### 查询进度事件

`GET /api/v1/jobs/{job_id}/events`

返回各阶段写入的进度事件列表，包含 `event_type`、`progress`、`iteration`、`message`。

### 取消任务

`POST /api/v1/jobs/{job_id}/cancel`

记录取消请求。执行中的 worker 将逐步支持响应取消。

## 前端接入步骤

1. 初始化时请求 `GET /api/v1/capabilities`，展示可选 outputs 与 preset
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

    const spec = { outputs: ["point_cloud"], preset: "standard" };
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
