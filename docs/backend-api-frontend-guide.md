# 后端 API 对接指南（前端向）

本文面向前端接入，覆盖任务流程、接口契约、调用顺序、最小示例。

## 1. 核心流程

任务按固定顺序执行：

1. `colmap`
2. `3dgs`
3. `langsplat`
4. `gaussian-wrapping`

前端通过 `enabled` 控制本次任务启用的阶段，后端按顺序串行执行已启用阶段。

推荐调用链路：

1. 读流水线定义：`GET /api/pipeline`
2. 上传图片并创建任务：`POST /api/jobs`
3. 轮询任务状态：`GET /api/jobs/{job_id}`
4. 状态为 `done` 后下载产物：`/download/3dgs` 或 `/download/mesh`

## 2. 关键设计

- **异步执行模型**：`POST /api/jobs` 仅创建任务并返回 `job_id`，实际执行在后台任务中完成。
- **状态来源单一**：每个任务的进度、阶段状态、产物信息都来自 `progress.json`，前端只需轮询一个状态接口。
- **阶段产物标准化**：各阶段产物路径集中放在 `artifacts` 字段，前端可据此决定下载按钮可用状态。
- **配置可覆盖**：创建任务时可上传阶段 YAML 覆盖默认参数，后端会与默认配置做 deep merge。

## 3. API 列表

### 3.1 健康检查

- `GET /healthz`
- 功能：服务健康探测
- 返回示例：

```json
{ "status": "ok" }
```

### 3.2 获取流水线阶段

- `GET /api/pipeline`
- 功能：返回可选阶段、顺序、输入提示
- 返回关键字段：
  - `stages[].id`：阶段标识
  - `stages[].order`：执行顺序
  - `stages[].inputs`：输入要求提示

### 3.3 创建任务

- `POST /api/jobs`
- `Content-Type: multipart/form-data`
- 功能：上传图像并提交任务

表单字段：

- `files`（必填，可多文件）：输入图片，支持 `jpg/jpeg/png/bmp/webp`
- `enabled`（必填，字符串）：JSON 对象，示例
  - `{"colmap":true,"3dgs":true,"langsplat":false,"gaussian-wrapping":false}`
- `gs_config`（可选）：3DGS 覆盖 YAML 文件
- `colmap_config`（可选）：COLMAP 覆盖 YAML 文件
- `langsplat_config`（可选）：LangSplat 覆盖 YAML 文件
- `gaussian_wrapping_config`（可选）：Mesh 阶段覆盖 YAML 文件

返回示例：

```json
{
  "job_id": "9c4f7428e2aa",
  "status": "queued",
  "message": "任务已创建",
  "enabled": ["colmap", "3dgs"]
}
```

### 3.4 查询任务状态

- `GET /api/jobs/{job_id}`
- 功能：查询任务整体状态、进度、当前阶段、阶段产物

返回关键字段：

- `status`：`queued | running | done | error`
- `progress`：0-100
- `current_stage`：当前运行阶段
- `stages[]`：每阶段状态、时间、错误、产物
- `artifacts`：阶段产物字典

示例（片段）：

```json
{
  "job_id": "9c4f7428e2aa",
  "status": "running",
  "progress": 50,
  "current_stage": "3dgs",
  "artifacts": {
    "colmap": {
      "sparse_dir": "colmap/sparse/0",
      "images_dir": "colmap/images",
      "result": "artifacts/colmap/result.json"
    },
    "3dgs": null
  }
}
```

### 3.5 下载 3DGS 结果

- `GET /api/jobs/{job_id}/download/3dgs`
- 功能：下载 3DGS 产物 `ply` 文件
- 成功时返回文件流（`.ply`）

### 3.6 下载 Mesh 结果

- `GET /api/jobs/{job_id}/download/mesh`
- 功能：下载 `gaussian-wrapping` 阶段 mesh 文件（优先 textured mesh）
- 成功时返回文件流（`.ply`）

### 3.7 下载最终结果

- `GET /api/jobs/{job_id}/result`
- 功能：返回任务最终 `output_ply` 指向的结果文件
- 适用场景：只关心任务最终产物

### 3.8 获取某阶段产物

- `GET /api/jobs/{job_id}/artifacts/{stage}`
- 功能：按阶段获取产物
- 返回形态：
  - 若该阶段产物可定位到可下载 `ply`，直接返回文件流
  - 其余场景返回 JSON：`{ job_id, stage, artifact }`

## 4. 前端接入步骤

1. 页面初始化请求 `GET /api/pipeline`，渲染阶段勾选框，按 `order` 排序。
2. 上传时构造 `FormData`：
   - 多图字段全部追加为 `files`
   - `enabled` 以 `JSON.stringify` 后写入字符串字段
   - 需要覆盖参数时追加对应 YAML 文件字段
3. 保存 `job_id` 后，每 2 秒轮询 `GET /api/jobs/{job_id}`。
4. 依据 `status` 处理 UI：
   - `running`：展示 `progress` 和 `current_stage`
   - `done`：开放下载入口
   - `error`：展示 `error` 或 `message`
5. 下载：
   - 3DGS：`/api/jobs/{job_id}/download/3dgs`
   - Mesh：`/api/jobs/{job_id}/download/mesh`

## 5. 最小前端 Demo（原生 JS）

```html
<input id="files" type="file" multiple accept=".jpg,.jpeg,.png,.bmp,.webp" />
<button id="createBtn">创建任务</button>
<pre id="log"></pre>

<script>
  const API_BASE = "http://localhost:8000";
  const log = (v) => (document.getElementById("log").textContent = JSON.stringify(v, null, 2));

  async function createJob() {
    const input = document.getElementById("files");
    const files = Array.from(input.files || []);
    if (!files.length) {
      log({ error: "请选择图片" });
      return;
    }

    const enabled = {
      colmap: true,
      "3dgs": true,
      langsplat: false,
      "gaussian-wrapping": false
    };

    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    fd.append("enabled", JSON.stringify(enabled));

    const res = await fetch(`${API_BASE}/api/jobs`, { method: "POST", body: fd });
    const created = await res.json();
    if (!res.ok) {
      log(created);
      return;
    }

    const jobId = created.job_id;
    log(created);

    const timer = setInterval(async () => {
      const r = await fetch(`${API_BASE}/api/jobs/${jobId}`);
      const status = await r.json();
      log(status);
      if (status.status === "done" || status.status === "error") {
        clearInterval(timer);
        if (status.status === "done") {
          window.open(`${API_BASE}/api/jobs/${jobId}/download/3dgs`, "_blank");
        }
      }
    }, 2000);
  }

  document.getElementById("createBtn").addEventListener("click", createJob);
</script>
```

## 6. 联调建议

- 基础连通性：`GET /healthz`
- 接口自查：`http://localhost:8000/docs`
- 本地 demo：`client-demo/main.js` 已实现完整创建、轮询、下载链路
