const apiBase = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
  ? "http://localhost:8000"
  : (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000");

const inputModeGroup = document.getElementById("inputModeGroup");
const stagePresetGroup = document.getElementById("stagePresetGroup");
const outputGroup = document.getElementById("outputGroup");
const meshFormatsBlock = document.getElementById("meshFormatsBlock");
const meshFormatGroup = document.getElementById("meshFormatGroup");
const plyOptionsBlock = document.getElementById("plyOptionsBlock");
const imagesUploadBlock = document.getElementById("imagesUploadBlock");
const plyUploadBlock = document.getElementById("plyUploadBlock");
const fileInput = document.getElementById("fileInput");
const dirInput = document.getElementById("dirInput");
const plyInput = document.getElementById("plyInput");
const iterationInput = document.getElementById("iterationInput");
const plannedStagesPreview = document.getElementById("plannedStagesPreview");
const uploadBtn = document.getElementById("uploadBtn");
const reloadCapabilitiesBtn = document.getElementById("reloadCapabilitiesBtn");
const cancelBtn = document.getElementById("cancelBtn");

const jobIdEl = document.getElementById("jobId");
const statusEl = document.getElementById("status");
const messageEl = document.getElementById("message");
const progressEl = document.getElementById("progress");
const currentStageEl = document.getElementById("currentStage");
const plannedStagesStatus = document.getElementById("plannedStagesStatus");
const stageList = document.getElementById("stageList");
const downloadList = document.getElementById("downloadList");
const debugOutput = document.getElementById("debugOutput");

let capabilities = null;
let currentJobId = null;
let timer = null;

function setDebug(payload) {
  debugOutput.textContent = JSON.stringify(payload, null, 2);
}

function getInputMode() {
  const selected = document.querySelector('input[name="inputMode"]:checked');
  return selected?.value || "images";
}

function getSelectedOutputs() {
  const boxes = document.querySelectorAll('#outputGroup input[name="output"]:checked');
  return Array.from(boxes).map((box) => box.value);
}

function getSelectedMeshFormats() {
  const boxes = document.querySelectorAll('#meshFormatGroup input[name="meshFormat"]:checked');
  return Array.from(boxes).map((box) => box.value);
}

function getInputModeDefinition(modeId) {
  return capabilities?.input_modes?.find((mode) => mode.id === modeId) || null;
}

function previewPlannedStages() {
  if (!capabilities) return [];
  const inputMode = getInputMode();
  const outputs = getSelectedOutputs();
  const stageIds = new Set();

  for (const outputId of outputs) {
    const output = capabilities.outputs.find((item) => item.id === outputId);
    if (!output) continue;
    const stages = inputMode === "native_3dgs_ply"
      ? output.ply_mode_stages
      : output.required_stages;
    for (const stageId of stages || []) {
      stageIds.add(stageId);
    }
  }

  return capabilities.stages
    .filter((stage) => stageIds.has(stage.id))
    .map((stage) => stage.id);
}

function renderPlannedStagesPreview() {
  const stages = previewPlannedStages();
  plannedStagesPreview.innerHTML = stages.length
    ? stages.map((stageId) => `<span class="chip">${stageId}</span>`).join("")
    : '<span class="hint">请选择至少一个产物</span>';
}

function updateModeUi() {
  const inputMode = getInputMode();
  const isPlyMode = inputMode === "native_3dgs_ply";
  const modeDef = getInputModeDefinition(inputMode);

  imagesUploadBlock.classList.toggle("hidden", isPlyMode);
  plyUploadBlock.classList.toggle("hidden", !isPlyMode);
  plyOptionsBlock.classList.toggle("hidden", !isPlyMode);

  const allowedOutputs = new Set(modeDef?.allowed_outputs || []);
  for (const box of document.querySelectorAll('#outputGroup input[name="output"]')) {
    const allowed = allowedOutputs.has(box.value);
    box.disabled = !allowed;
    if (!allowed) {
      box.checked = false;
    }
  }

  if (isPlyMode) {
    const meshBox = document.querySelector('#outputGroup input[name="output"][value="mesh"]');
    if (meshBox) meshBox.checked = true;
  }

  updateMeshFormatUi();
  renderPlannedStagesPreview();
}

function updateMeshFormatUi() {
  const hasMesh = getSelectedOutputs().includes("mesh");
  meshFormatsBlock.classList.toggle("hidden", !hasMesh);
}

function renderCapabilities(data) {
  capabilities = data;

  inputModeGroup.innerHTML = (data.input_modes || []).map((mode, index) => `
    <label class="block">
      <input
        type="radio"
        name="inputMode"
        value="${mode.id}"
        ${index === 0 ? "checked" : ""}
      />
      ${mode.label}
      <small class="hint">（允许产物：${mode.allowed_outputs.join("、")}）</small>
    </label>
  `).join("");

  const stagePresets = data.stage_presets || {};
  const stagePresetEntries = Object.entries(stagePresets).filter(([, presets]) => presets.length);
  stagePresetGroup.innerHTML = stagePresetEntries.map(([stageId, presets]) => `
    <div>
      <strong>${stageId}</strong>
      <p>
        <select name="stagePreset" data-stage-id="${stageId}">
          <option value="">default</option>
          ${presets.map((preset) => `<option value="${preset}">${preset}</option>`).join("")}
        </select>
      </p>
    </div>
  `).join("");
  stagePresetGroup.classList.toggle("hidden", stagePresetEntries.length === 0);

  outputGroup.innerHTML = (data.outputs || []).map((output) => `
    <label class="block">
      <input
        type="checkbox"
        name="output"
        value="${output.id}"
        ${output.id === "point_cloud" ? "checked" : ""}
      />
      ${output.label || output.id}
      <small class="hint">（images: ${output.required_stages.join(" → ")}；PLY: ${output.ply_mode_stages.join(" → ") || "-"}）</small>
    </label>
  `).join("");

  meshFormatGroup.innerHTML = (data.mesh_formats || ["ply"]).map((format) => `
    <label class="block">
      <input
        type="checkbox"
        name="meshFormat"
        value="${format}"
        ${format === "ply" ? "checked" : ""}
      />
      ${format.toUpperCase()}
    </label>
  `).join("");

  for (const input of document.querySelectorAll('input[name="inputMode"]')) {
    input.addEventListener("change", updateModeUi);
  }
  for (const input of document.querySelectorAll('#outputGroup input[name="output"]')) {
    input.addEventListener("change", () => {
      updateMeshFormatUi();
      renderPlannedStagesPreview();
    });
  }
  for (const input of document.querySelectorAll('#meshFormatGroup input[name="meshFormat"]')) {
    input.addEventListener("change", updateMeshFormatUi);
  }

  updateModeUi();
  setDebug({ capabilities: data });
}

async function loadCapabilities() {
  try {
    const response = await fetch(`${apiBase}/api/v1/capabilities`);
    if (!response.ok) {
      throw new Error(`加载 capabilities 失败: ${response.status}`);
    }
    const data = await response.json();
    renderCapabilities(data);
  } catch (error) {
    setDebug({ error: error.message });
    alert(error.message);
  }
}

function buildSpec() {
  const inputMode = getInputMode();
  const outputs = getSelectedOutputs();
  if (!outputs.length) {
    throw new Error("请至少选择一个目标产物");
  }

  const options = { input_mode: inputMode };
  if (inputMode === "native_3dgs_ply") {
    const iteration = Number(iterationInput.value);
    if (!Number.isFinite(iteration) || iteration <= 0) {
      throw new Error("iteration 必须是正整数");
    }
    options.iteration = iteration;
  }

  if (outputs.includes("mesh")) {
    const meshFormats = getSelectedMeshFormats();
    if (!meshFormats.length) {
      throw new Error("请至少选择一种 mesh 导出格式");
    }
    options.mesh_formats = meshFormats;
  }

  const stage_presets = {};
  for (const select of document.querySelectorAll('select[name="stagePreset"]')) {
    if (select.value) {
      stage_presets[select.dataset.stageId] = select.value;
    }
  }
  if (Object.keys(stage_presets).length) {
    options.stage_presets = stage_presets;
  }

  return {
    outputs,
    options,
  };
}

function collectFiles() {
  const inputMode = getInputMode();
  if (inputMode === "native_3dgs_ply") {
    const plyFile = plyInput.files?.[0];
    if (!plyFile) {
      throw new Error("请选择一个 PLY 文件");
    }
    return [plyFile];
  }

  const files = [
    ...Array.from(fileInput.files || []),
    ...Array.from(dirInput.files || []),
  ];
  if (!files.length) {
    throw new Error("请先选择图片文件或目录");
  }
  return files;
}

async function createJob() {
  let spec;
  let files;
  try {
    spec = buildSpec();
    files = collectFiles();
  } catch (error) {
    alert(error.message);
    return;
  }

  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  formData.append("spec", JSON.stringify(spec));

  uploadBtn.disabled = true;
  cancelBtn.disabled = true;
  downloadList.innerHTML = '<span class="hint">任务执行中...</span>';
  stageList.innerHTML = "";

  try {
    const response = await fetch(`${apiBase}/api/v1/jobs`, {
      method: "POST",
      body: formData,
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body.detail || `创建任务失败: ${response.status}`);
    }

    currentJobId = body.job_id;
    jobIdEl.textContent = body.job_id;
    statusEl.textContent = body.status;
    messageEl.textContent = body.message || "-";
    progressEl.textContent = "0%";
    currentStageEl.textContent = "-";
    plannedStagesStatus.innerHTML = (body.planned_stages || [])
      .map((stageId) => `<span class="chip">${stageId}</span>`)
      .join("");
    setDebug(body);
    startPolling();
  } catch (error) {
    setDebug({ error: error.message });
    alert(error.message);
  } finally {
    uploadBtn.disabled = false;
  }
}

function renderStageList(stages) {
  if (!stages?.length) {
    stageList.innerHTML = "";
    return;
  }
  stageList.innerHTML = stages.map((stage) => {
    const pct = stage.progress > 0
      ? Math.round(stage.progress <= 1 ? stage.progress * 100 : stage.progress)
      : 0;
    const progressText = stage.status === "running" || stage.status === "done"
      ? ` · ${pct}%`
      : "";
    return `
      <li>
        <span>${stage.stage_id}</span>
        <span class="status-pill ${stage.status}">${stage.status}${progressText}</span>
      </li>
    `;
  }).join("");
}

function renderDownloads(artifacts) {
  const downloadable = (artifacts || []).filter((artifact) => artifact.downloadable);
  if (!downloadable.length) {
    downloadList.innerHTML = '<span class="hint">暂无可下载产物</span>';
    return;
  }

  downloadList.innerHTML = "";
  for (const artifact of downloadable) {
    const button = document.createElement("button");
    const label = artifact.label || artifact.id;
    button.textContent = `下载 ${label} (${artifact.type})`;
    button.addEventListener("click", () => {
      window.open(
        `${apiBase}/api/v1/jobs/${currentJobId}/artifacts/${artifact.id}/download`,
        "_blank",
      );
    });
    downloadList.appendChild(button);
  }
}

function updateJobUi(data) {
  statusEl.textContent = data.status;
  messageEl.textContent = data.message || data.error || "-";
  progressEl.textContent = `${data.progress ?? 0}%`;
  currentStageEl.textContent = data.current_stage_id || "-";
  plannedStagesStatus.innerHTML = (data.planned_stages || [])
    .map((stageId) => `<span class="chip">${stageId}</span>`)
    .join("");
  renderStageList(data.stages);
  renderDownloads(data.artifacts);
  cancelBtn.disabled = !(currentJobId && ["queued", "running"].includes(data.status));
}

async function pollJob() {
  if (!currentJobId) return;
  try {
    const response = await fetch(`${apiBase}/api/v1/jobs/${currentJobId}`);
    if (!response.ok) {
      throw new Error(`查询任务失败: ${response.status}`);
    }
    const data = await response.json();
    setDebug(data);
    updateJobUi(data);

    if (data.status === "done" || data.status === "error" || data.status === "cancelled") {
      stopPolling();
    }
  } catch (error) {
    setDebug({ error: error.message });
    stopPolling();
  }
}

async function cancelJob() {
  if (!currentJobId) return;
  try {
    const response = await fetch(`${apiBase}/api/v1/jobs/${currentJobId}/cancel`, {
      method: "POST",
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body.detail || `取消任务失败: ${response.status}`);
    }
    setDebug(body);
    await pollJob();
  } catch (error) {
    setDebug({ error: error.message });
    alert(error.message);
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

uploadBtn.addEventListener("click", createJob);
reloadCapabilitiesBtn.addEventListener("click", loadCapabilities);
cancelBtn.addEventListener("click", cancelJob);

loadCapabilities();
