const apiBase = window.location.hostname === "localhost"
  ? "http://localhost:8000"
  : (import.meta.env.API_BASE_URL || "http://localhost:8000");

const fileInput = document.getElementById("fileInput");
const dirInput = document.getElementById("dirInput");
const uploadBtn = document.getElementById("uploadBtn");
const download3dgsBtn = document.getElementById("download3dgsBtn");
const downloadMeshBtn = document.getElementById("downloadMeshBtn");
const jobIdEl = document.getElementById("jobId");
const statusEl = document.getElementById("status");
const messageEl = document.getElementById("message");
const progressEl = document.getElementById("progress");
const debugOutput = document.getElementById("debugOutput");

let currentJobId = null;
let timer = null;
let pipelineStages = [];

function setDebug(payload) {
  debugOutput.textContent = JSON.stringify(payload, null, 2);
}

function resetDownloadButtons() {
  download3dgsBtn.disabled = true;
  downloadMeshBtn.disabled = true;
  download3dgsBtn.textContent = "下载 3DGS PLY";
  downloadMeshBtn.textContent = "下载 Mesh PLY";
}

function ensureStageSelector() {
  if (document.getElementById("stageSelector")) return;
  const panel = uploadBtn.closest(".panel");
  if (!panel) return;
  const block = document.createElement("div");
  block.id = "stageSelector";
  block.innerHTML = "<p><strong>执行阶段</strong>（按固定顺序，勾选本任务要跑的步骤）</p>";
  panel.insertBefore(block, uploadBtn);
}

function renderStageCheckboxes(stages) {
  ensureStageSelector();
  const container = document.getElementById("stageSelector");
  if (!container) return;
  const sorted = [...stages].sort((a, b) => a.order - b.order);
  container.innerHTML = "<p><strong>执行阶段</strong>（按固定顺序，勾选本任务要跑的步骤）</p>";
  for (const stage of sorted) {
    const row = document.createElement("label");
    row.style.display = "block";
    const checked = stage.id === "colmap" || stage.id === "3dgs";
    const hints = stage.inputs?.length ? ` <small>（需要：${stage.inputs.join("、")}）</small>` : "";
    row.innerHTML = `
      <input type="checkbox" name="stage" value="${stage.id}" ${checked ? "checked" : ""} />
      ${stage.label}${hints}
    `;
    container.appendChild(row);
  }
}

async function loadPipeline() {
  try {
    const response = await fetch(`${apiBase}/api/pipeline`);
    if (!response.ok) {
      throw new Error(`加载流水线失败: ${response.status}`);
    }
    const data = await response.json();
    pipelineStages = data.stages || [];
    renderStageCheckboxes(pipelineStages);
  } catch (error) {
    pipelineStages = [
      { id: "colmap", label: "COLMAP", order: 0, inputs: ["input/ 下有图像"] },
      { id: "3dgs", label: "3DGS", order: 1, inputs: ["colmap/sparse"] },
      { id: "langsplat", label: "LangSplatV2", order: 2, inputs: ["colmap/sparse", "output/chkpnt{N}.pth"] },
      { id: "gaussian-wrapping", label: "Mesh", order: 3, inputs: ["colmap/sparse", "output/.../point_cloud.ply"] },
    ];
    renderStageCheckboxes(pipelineStages);
    setDebug({ pipelineFallback: error.message });
  }
}

function getSelectedEnabled() {
  const boxes = document.querySelectorAll('#stageSelector input[name="stage"]:checked');
  const enabled = {};
  for (const stage of pipelineStages) {
    enabled[stage.id] = false;
  }
  for (const box of boxes) {
    if (box instanceof HTMLInputElement) {
      enabled[box.value] = true;
    }
  }
  return enabled;
}

function updateDownloadAvailability(data) {
  const stage3dgs = data.artifacts?.["3dgs"];
  const has3dgs = typeof stage3dgs?.ply === "string";
  download3dgsBtn.disabled = !has3dgs;
  download3dgsBtn.textContent = "下载 3DGS PLY";

  const wrapping = data.artifacts?.["gaussian-wrapping"];
  const hasMesh = typeof wrapping?.mesh_textured_ply === "string"
    || typeof wrapping?.mesh_ply === "string";
  downloadMeshBtn.disabled = !hasMesh;
  downloadMeshBtn.textContent = "下载 Mesh PLY";
}

async function createJob() {
  const files = [
    ...Array.from(fileInput.files || []),
    ...Array.from(dirInput.files || []),
  ];
  if (!files.length) {
    alert("请先选择图片文件");
    return;
  }

  const enabled = getSelectedEnabled();
  if (!Object.values(enabled).some(Boolean)) {
    alert("请至少勾选一个阶段");
    return;
  }

  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  formData.append("enabled", JSON.stringify(enabled));

  uploadBtn.disabled = true;
  resetDownloadButtons();

  try {
    const response = await fetch(`${apiBase}/api/jobs`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `创建任务失败: ${response.status}`);
    }
    const data = await response.json();
    currentJobId = data.job_id;
    jobIdEl.textContent = data.job_id;
    statusEl.textContent = data.status;
    messageEl.textContent = data.message;
    progressEl.textContent = "0%";
    setDebug(data);
    startPolling();
  } catch (error) {
    setDebug({ error: error.message });
    alert(error.message);
  } finally {
    uploadBtn.disabled = false;
  }
}

async function pollJob() {
  if (!currentJobId) return;
  try {
    const response = await fetch(`${apiBase}/api/jobs/${currentJobId}`);
    if (!response.ok) {
      throw new Error(`查询任务失败: ${response.status}`);
    }
    const data = await response.json();
    statusEl.textContent = data.status;
    messageEl.textContent = data.message || "-";
    progressEl.textContent = `${data.progress}%`;
    setDebug(data);
    updateDownloadAvailability(data);

    if (data.status === "done" || data.status === "error") {
      stopPolling();
    }
  } catch (error) {
    setDebug({ error: error.message });
    stopPolling();
  }
}

function startPolling() {
  stopPolling();
  pollJob();
  timer = setInterval(pollJob, 2000);
}

function stopPolling() {
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
}

function download3dgs() {
  if (!currentJobId || download3dgsBtn.disabled) return;
  window.open(`${apiBase}/api/jobs/${currentJobId}/download/3dgs`, "_blank");
}

function downloadMesh() {
  if (!currentJobId || downloadMeshBtn.disabled) return;
  window.open(`${apiBase}/api/jobs/${currentJobId}/download/mesh`, "_blank");
}

loadPipeline();
uploadBtn.addEventListener("click", createJob);
download3dgsBtn.addEventListener("click", download3dgs);
downloadMeshBtn.addEventListener("click", downloadMesh);
