const API_BASE = window.location.protocol === "file:" ? "http://127.0.0.1:8080/api" : "/api";
const AI_BASE = "http://127.0.0.1:8001";
const POLL_MS = 1200;
const RESPONSE_TIMEOUT_MS = 15000;
const CAMERA_INFER_MS = 900;

const CareState = {
  NORMAL: "NORMAL",
  SUSPECTED_FALL: "SUSPECTED_FALL",
  VOICE_CHECKING: "VOICE_CHECKING",
  WAITING_RESPONSE: "WAITING_RESPONSE",
  CONFIRMED_SAFE: "CONFIRMED_SAFE",
  CONFIRMED_FALL: "CONFIRMED_FALL",
  EMERGENCY: "EMERGENCY",
};

const dom = {
  apiStatus: document.querySelector("#apiStatus"),
  stateChip: document.querySelector("#stateChip"),
  clock: document.querySelector("#clock"),
  cameraModeBtn: document.querySelector("#cameraModeBtn"),
  demoModeBtn: document.querySelector("#demoModeBtn"),
  cameraVideo: document.querySelector("#cameraVideo"),
  demoVideo: document.querySelector("#demoVideo"),
  videoFallback: document.querySelector("#videoFallback"),
  canvas: document.querySelector("#detectionCanvas"),
  videoModeLabel: document.querySelector("#videoModeLabel"),
  fallLabel: document.querySelector("#fallLabel"),
  fpsValue: document.querySelector("#fpsValue"),
  fallBanner: document.querySelector("#fallBanner"),
  videoUploadPanel: document.querySelector("#videoUploadPanel"),
  videoDropZone: document.querySelector("#videoDropZone"),
  videoFileInput: document.querySelector("#videoFileInput"),
  videoFileName: document.querySelector("#videoFileName"),
  videoUploadStatus: document.querySelector("#videoUploadStatus"),
  riskBadge: document.querySelector("#riskBadge"),
  riskArc: document.querySelector("#riskArc"),
  riskScore: document.querySelector("#riskScore"),
  riskText: document.querySelector("#riskText"),
  needsRescueText: document.querySelector("#needsRescueText"),
  userResponseText: document.querySelector("#userResponseText"),
  gemmaActionText: document.querySelector("#gemmaActionText"),
  aiReasonText: document.querySelector("#aiReasonText"),
  interventionDot: document.querySelector("#interventionDot"),
  voiceCheckBtn: document.querySelector("#voiceCheckBtn"),
  voiceStatusText: document.querySelector("#voiceStatusText"),
  replyText: document.querySelector("#replyText"),
  voiceFeedbackText: document.querySelector("#voiceFeedbackText"),
  rescueText: document.querySelector("#rescueText"),
  emergencyCard: document.querySelector("#emergencyCard"),
  emergencyTitle: document.querySelector("#emergencyTitle"),
  emergencyMessage: document.querySelector("#emergencyMessage"),
  countdownValue: document.querySelector("#countdownValue"),
  contactStatusText: document.querySelector("#contactStatusText"),
  manualEmergencyBtn: document.querySelector("#manualEmergencyBtn"),
  refreshLogsBtn: document.querySelector("#refreshLogsBtn"),
  logList: document.querySelector("#logList"),
  emergencyModal: document.querySelector("#emergencyModal"),
  modalReason: document.querySelector("#modalReason"),
  modalCountdown: document.querySelector("#modalCountdown"),
  modalContact: document.querySelector("#modalContact"),
  modalReply: document.querySelector("#modalReply"),
  modalState: document.querySelector("#modalState"),
};

const ctx = dom.canvas.getContext("2d");

const machine = {
  state: CareState.NORMAL,
  enteredAt: Date.now(),
  lastState: null,
  transition(nextState) {
    if (this.state === nextState) return;
    this.lastState = this.state;
    this.state = nextState;
    this.enteredAt = Date.now();
    renderStateMachine();
  },
  syncFromJson(state) {
    const vision = state.vision || {};
    const speech = state.speech || {};
    const decision = state.decision || {};
    const intervention = state.intervention || {};
    const emergency = state.emergency || {};
    const fall = vision.fall_detected === true;
    const hasReply = Boolean((speech.transcript || "").trim());
    const alerting = decision.emergency_alert === true || emergency.triggered === true;

    if (alerting) return this.transition(CareState.EMERGENCY);
    if (fall && decision.risk_level === "high") return this.transition(CareState.CONFIRMED_FALL);
    if (fall && hasReply) return this.transition(CareState.CONFIRMED_SAFE);
    if (fall && intervention.active) return this.transition(CareState.WAITING_RESPONSE);
    if (fall) return this.transition(CareState.SUSPECTED_FALL);
    return this.transition(CareState.NORMAL);
  },
  autoTick() {
    const elapsed = Date.now() - this.enteredAt;
    if (this.state === CareState.SUSPECTED_FALL && elapsed > 2500) {
      this.transition(CareState.VOICE_CHECKING);
    }
    if (this.state === CareState.VOICE_CHECKING && elapsed > 2500) {
      this.transition(CareState.WAITING_RESPONSE);
    }
    if (this.state === CareState.WAITING_RESPONSE && elapsed > RESPONSE_TIMEOUT_MS) {
      this.transition(CareState.CONFIRMED_FALL);
    }
  },
};

let currentMode = "camera";
let lastDetection = null;
let modeDetections = {
  camera: null,
  demo: null,
};
let latestState = null;
let lastFrameTime = performance.now();
let cameraInferTimer = null;
let cameraInferBusy = false;
let cameraCanvas = document.createElement("canvas");
let cameraCtx = cameraCanvas.getContext("2d");
let mediaRecorder = null;
let recordedAudioChunks = [];
let uploadedVideoResult = null;
let lastRealtimeUpdateAt = 0;

async function requestJson(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!payload.success) throw new Error(payload.message || "Request failed");
  return payload.data;
}

async function requestAiJson(path, options = {}) {
  const response = await fetch(`${AI_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || payload.message || `AI request failed (${response.status})`);
  if (!payload.success && !payload.payload && !payload.data) {
    throw new Error(payload.error || payload.message || "AI request failed");
  }
  return payload;
}

function setApiOnline(isOnline) {
  dom.apiStatus.textContent = isOnline ? "API Online" : "API Offline";
  dom.apiStatus.className = `status-chip ${isOnline ? "status-online" : "status-offline"}`;
}

function setMode(mode) {
  currentMode = mode;
  modeDetections[mode] = null;
  lastDetection = null;
  lastRealtimeUpdateAt = Date.now();
  dom.cameraModeBtn.classList.toggle("active", mode === "camera");
  dom.demoModeBtn.classList.toggle("active", mode === "demo");
  dom.cameraVideo.classList.toggle("hidden", mode !== "camera");
  dom.demoVideo.classList.toggle("hidden", mode !== "demo");
  dom.videoUploadPanel.classList.toggle("hidden", mode !== "demo");
  dom.videoModeLabel.textContent = mode === "camera" ? "CAMERA" : "VIDEO";

  if (mode === "demo") {
    stopCameraInference();
    showFallback(false);
    dom.fallLabel.textContent = "NO FALL";
    dom.fpsValue.textContent = "--";
    if (dom.demoVideo.src) dom.demoVideo.play().catch(() => {});
  } else {
    startCamera();
  }
}

function showFallback(show) {
  dom.videoFallback.classList.toggle("hidden", !show);
}

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    showFallback(true);
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    dom.cameraVideo.srcObject = stream;
    showFallback(false);
    startCameraInference();
  } catch {
    showFallback(true);
  }
}

function startCameraInference() {
  if (cameraInferTimer) return;
  cameraInferTimer = setInterval(sendCameraFrameForInference, CAMERA_INFER_MS);
}

function stopCameraInference() {
  if (!cameraInferTimer) return;
  clearInterval(cameraInferTimer);
  cameraInferTimer = null;
  cameraInferBusy = false;
}

function cameraFrameReady() {
  return (
    currentMode === "camera" &&
    dom.cameraVideo.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA &&
    dom.cameraVideo.videoWidth > 0 &&
    dom.cameraVideo.videoHeight > 0
  );
}

async function sendCameraFrameForInference() {
  if (cameraInferBusy || !cameraFrameReady()) return;
  cameraInferBusy = true;

  const width = Math.min(640, dom.cameraVideo.videoWidth);
  const height = Math.round((dom.cameraVideo.videoHeight / dom.cameraVideo.videoWidth) * width);
  cameraCanvas.width = width;
  cameraCanvas.height = height;
  cameraCtx.drawImage(dom.cameraVideo, 0, 0, width, height);
  const image = cameraCanvas.toDataURL("image/jpeg", 0.72);

  try {
    const data = await requestAiJson("/vision/frame", {
      method: "POST",
      body: JSON.stringify({
        image,
        push_to_php: true,
        no_response_seconds: latestState?.context?.no_response_seconds || 0,
      }),
    });
    const payload = data.payload || {};
    if (payload.vision) {
      modeDetections.camera = payload.vision;
      if (currentMode === "camera") {
        lastDetection = payload.vision;
      }
    }
    lastRealtimeUpdateAt = Date.now();
    renderState({
      ...(latestState || {}),
      ...payload,
    });
    setApiOnline(true);
    if (data.php_error) {
      dom.aiReasonText.textContent = `YOLO updated locally. PHP sync pending: ${data.php_error}`;
    }
  } catch (error) {
    setApiOnline(false);
    dom.aiReasonText.textContent = `AI backend unavailable: ${error.message}`;
  } finally {
    cameraInferBusy = false;
  }
}

function resizeCanvas() {
  const rect = dom.canvas.getBoundingClientRect();
  const width = Math.max(1, Math.floor(rect.width));
  const height = Math.max(1, Math.floor(rect.height));
  if (dom.canvas.width !== width || dom.canvas.height !== height) {
    dom.canvas.width = width;
    dom.canvas.height = height;
  }
}

function drawDetections() {
  resizeCanvas();
  ctx.clearRect(0, 0, dom.canvas.width, dom.canvas.height);
  const activeDetection = modeDetections[currentMode];
  const detections = activeDetection?.detections || [];
  const drawArea = getVideoDrawArea();

  detections.forEach((box) => {
    const x = drawArea.x + box.x * drawArea.width;
    const y = drawArea.y + box.y * drawArea.height;
    const w = box.width * drawArea.width;
    const h = box.height * drawArea.height;
    const danger = box.fall_detected === true;
    const color = danger ? "#ff3158" : "#2ff6a0";
    const label = `${box.label || "person"} ${Math.round((box.confidence || 0) * 100)}%`;

    ctx.lineWidth = 3;
    ctx.strokeStyle = color;
    ctx.fillStyle = danger ? "rgba(255,49,88,.18)" : "rgba(47,246,160,.12)";
    ctx.fillRect(x, y, w, h);
    ctx.strokeRect(x, y, w, h);

    ctx.font = "700 14px Arial";
    const labelWidth = ctx.measureText(label).width + 16;
    ctx.fillStyle = color;
    ctx.fillRect(x, Math.max(0, y - 28), labelWidth, 24);
    ctx.fillStyle = "#06101f";
    ctx.fillText(label, x + 8, Math.max(17, y - 11));
  });

  requestAnimationFrame(drawDetections);
}

function getVideoDrawArea() {
  const video = currentMode === "camera" ? dom.cameraVideo : dom.demoVideo;
  const canvasWidth = dom.canvas.width;
  const canvasHeight = dom.canvas.height;
  const videoWidth = video.videoWidth || canvasWidth;
  const videoHeight = video.videoHeight || canvasHeight;
  const scale = Math.min(canvasWidth / videoWidth, canvasHeight / videoHeight);
  const width = videoWidth * scale;
  const height = videoHeight * scale;

  return {
    x: (canvasWidth - width) / 2,
    y: (canvasHeight - height) / 2,
    width,
    height,
  };
}

function updateFps() {
  const now = performance.now();
  const fps = Math.round(1000 / Math.max(1, now - lastFrameTime));
  lastFrameTime = now;
  const activeDetection = modeDetections[currentMode];
  dom.fpsValue.textContent = String(activeDetection?.fps || fps);
  requestAnimationFrame(updateFps);
}

function riskScoreFromState(state) {
  const decision = state.decision || {};
  const vision = state.vision || {};
  if (Number.isFinite(Number(decision.risk_score))) return Math.max(0, Math.min(100, Number(decision.risk_score)));
  if (decision.emergency_alert) return 100;
  if (decision.risk_level === "high") return 86;
  if (decision.risk_level === "medium") return Math.max(55, Math.round((vision.confidence || 0.6) * 80));
  return vision.fall_detected ? 42 : 12;
}

function riskColor(score) {
  if (score >= 80) return "#ff3158";
  if (score >= 45) return "#ffd166";
  return "#2ff6a0";
}

function renderRisk(score) {
  const radius = 58;
  const circumference = 2 * Math.PI * radius;
  dom.riskArc.style.strokeDasharray = `${circumference}`;
  dom.riskArc.style.strokeDashoffset = `${circumference - (score / 100) * circumference}`;
  dom.riskArc.style.stroke = riskColor(score);
  dom.riskScore.textContent = String(score);
}

function renderStateMachine() {
  dom.stateChip.textContent = machine.state.replace("_", " ");
  dom.stateChip.className = `state-chip state-${machine.state.toLowerCase()}`;
  document.querySelectorAll("[data-flow-state]").forEach((node) => {
    node.classList.toggle("active", node.dataset.flowState === machine.state);
  });
}

function renderState(state) {
  latestState = state;
  machine.syncFromJson(state);

  const vision = state.vision || {};
  const speech = state.speech || {};
  const decision = state.decision || {};
  const intervention = state.intervention || {};
  const emergency = state.emergency || {};
  const fallDetected = vision.fall_detected === true;
  const alerting = decision.emergency_alert === true || emergency.triggered === true;
  const score = riskScoreFromState(state);
  const risk = decision.risk_level || "low";

  renderRisk(score);
  dom.fallLabel.textContent = fallDetected ? "FALL" : "NO FALL";
  dom.fallBanner.classList.toggle("hidden", !fallDetected);
  dom.riskBadge.textContent = risk.toUpperCase();
  dom.riskBadge.className = `risk-badge ${risk}`;
  dom.riskText.textContent = risk.toUpperCase();
  dom.needsRescueText.textContent = alerting ? "Yes" : "No";
  dom.userResponseText.textContent = speech.transcript ? "Responded" : (intervention.active ? "Waiting" : "No check active");
  dom.gemmaActionText.textContent = decision.action || "Monitor";
  dom.aiReasonText.textContent = decision.reason || "Waiting for AI reasoning.";

  dom.interventionDot.classList.toggle("active", intervention.active === true);
  dom.voiceStatusText.textContent = intervention.active ? (intervention.voice_prompt || "Voice check active") : "Standby";
  dom.replyText.textContent = speech.transcript || "No reply";
  dom.voiceFeedbackText.textContent = voiceFeedbackFromState(state);
  dom.rescueText.textContent = alerting ? "Yes" : "No";

  dom.emergencyCard.classList.toggle("alerting", alerting);
  dom.emergencyModal.classList.toggle("hidden", !alerting);
  dom.emergencyTitle.textContent = alerting ? "Emergency alarm active" : "No active alarm";
  dom.emergencyMessage.textContent = alerting ? "Gemma4 requires rescue. Family notification is in progress." : "Gemma4 will trigger emergency mode when rescue is required.";
  dom.countdownValue.textContent = String(emergency.countdown_seconds ?? (alerting ? 0 : "--"));
  dom.contactStatusText.textContent = emergency.contact_status || "Standby";
  dom.modalReason.textContent = decision.reason || "Gemma4 has classified this event as high risk.";
  dom.modalCountdown.textContent = String(emergency.countdown_seconds ?? 0);
  dom.modalContact.textContent = emergency.contact_status || "Notifying family";
  dom.modalReply.textContent = speech.transcript || "No reply";
  dom.modalState.textContent = machine.state;
}

function voiceFeedbackFromState(state) {
  const speech = state.speech || {};
  const decision = state.decision || {};
  const transcript = (speech.transcript || "").trim();

  if (!transcript) return "Waiting for voice reply";
  if (speech.intent === "safe") return "AI: User says they are safe. Keep monitoring.";
  if (speech.intent === "help") return "AI: User asks for help. Increase rescue priority.";
  if (decision.action) return `AI: ${decision.action}`;
  return "AI: Reply recorded. Continue monitoring.";
}

function renderLogs(logs) {
  dom.logList.innerHTML = "";
  logs.slice().reverse().forEach((entry) => {
    const item = document.createElement("li");
    const time = document.createElement("time");
    const text = document.createElement("span");
    time.textContent = entry.created_at;
    text.textContent = `[${entry.level}] ${entry.message}`;
    item.append(time, text);
    dom.logList.appendChild(item);
  });
}

async function refreshStatus() {
  if (Date.now() - lastRealtimeUpdateAt < 2500) return;
  try {
    const data = await requestJson("/status");
    renderState(data.state);
    setApiOnline(true);
  } catch {
    setApiOnline(false);
  }
}

async function refreshDetection() {
  return;
}

async function refreshDecision() {
  try {
    const data = await requestJson("/gemma-decision");
    if (data.state) renderState(data.state);
  } catch {
    setApiOnline(false);
  }
}

async function refreshLogs() {
  try {
    const data = await requestJson("/logs");
    renderLogs(data.logs);
  } catch {
    setApiOnline(false);
  }
}

async function triggerEmergency() {
  const data = await requestJson("/emergency", {
    method: "POST",
    body: JSON.stringify({ source: "manual_dashboard", reason: "Manual dashboard emergency trigger" }),
  });
  renderState(data.state);
  await refreshLogs();
}

async function toggleVoiceCheck() {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    recordedAudioChunks = [];
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.addEventListener("dataavailable", (event) => {
      if (event.data.size > 0) recordedAudioChunks.push(event.data);
    });
    mediaRecorder.addEventListener("stop", async () => {
      stream.getTracks().forEach((track) => track.stop());
      dom.voiceCheckBtn.textContent = "Uploading Voice";
      dom.voiceCheckBtn.disabled = true;
      await uploadRecordedVoice();
      dom.voiceCheckBtn.disabled = false;
      dom.voiceCheckBtn.textContent = "Ask and Record Reply";
    });
    mediaRecorder.start();
    dom.voiceCheckBtn.textContent = "Stop and Analyze";
    dom.voiceStatusText.textContent = "Listening for elder reply...";
  } catch (error) {
    dom.voiceStatusText.textContent = `Microphone unavailable: ${error.message}`;
  }
}

async function uploadRecordedVoice() {
  const blob = new Blob(recordedAudioChunks, { type: "audio/webm" });
  const form = new FormData();
  form.append("audio", blob, "voice-check.webm");
  form.append("push_to_php", "true");

  try {
    const response = await fetch(`${AI_BASE}/speech/upload`, {
      method: "POST",
      body: form,
    });
    const data = await response.json();
    if (!data.success) throw new Error(data.error || "Voice upload failed");
    const payload = data.payload || {};
    const speech = payload.speech || {};
    if (speech.error) {
      dom.voiceStatusText.textContent = speech.error;
    }
    dom.replyText.textContent = speech.transcript || (speech.error ? "Recognition error" : "No speech detected");
    dom.voiceFeedbackText.textContent = voiceFeedbackFromState({
      ...(latestState || {}),
      ...payload,
      vision: payload.vision || latestState?.vision || {},
    });
    renderState({
      ...(latestState || {}),
      ...payload,
      vision: payload.vision || latestState?.vision || {},
    });
    await refreshStatus();
  } catch (error) {
    dom.voiceStatusText.textContent = `Voice check failed: ${error.message}`;
  }
}

async function uploadVideo(file) {
  if (!file) return;
  uploadedVideoResult = null;
  modeDetections.demo = null;
  lastDetection = null;
  dom.videoFileName.textContent = file.name;
  dom.videoUploadStatus.textContent = "Processing video...";
  dom.videoUploadStatus.className = "processing";
  dom.fallLabel.textContent = "ANALYZING";
  dom.fpsValue.textContent = "--";

  const objectUrl = URL.createObjectURL(file);
  dom.demoVideo.src = objectUrl;
  dom.demoVideo.classList.remove("hidden");
  dom.demoVideo.addEventListener("loadedmetadata", resizeCanvas, { once: true });
  dom.demoVideo.play().catch(() => {});

  const form = new FormData();
  form.append("file", file);

  try {
    const response = await fetch(`${AI_BASE}/upload_video`, {
      method: "POST",
      body: form,
    });
    const data = await response.json();
    if (!data.success) throw new Error(data.error || "Video analysis failed");

    const payload = data.data || data.payload || {};
    const vision = payload.vision || {};
    const decision = payload.decision || {};
    uploadedVideoResult = payload;
    modeDetections.demo = vision;
    if (currentMode === "demo") {
      lastDetection = vision;
    }
    lastRealtimeUpdateAt = Date.now();
    dom.videoUploadStatus.textContent = vision.fall_detected ? "Fall detected" : "Normal";
    dom.videoUploadStatus.className = vision.fall_detected ? "danger" : "ok";
    dom.fpsValue.textContent = String(payload.video?.frames_processed || vision.fps || 0);

    renderState({
      ...(latestState || {}),
      vision,
      speech: { transcript: "" },
      intervention: {
        active: vision.fall_detected === true,
        voice_prompt: vision.fall_detected ? "Are you okay? Please answer if you can hear me." : "System is monitoring.",
      },
      decision: {
        risk_level: decision.risk_level || decision.risk || (vision.fall_detected ? "medium" : "low"),
        risk_score: decision.risk_score ?? vision.risk_score ?? (vision.fall_detected ? 62 : 12),
        emergency_alert: decision.emergency_alert === true || decision.emergency === true,
        action: decision.action || (vision.fall_detected ? "Start voice check" : "Monitor"),
        reason: decision.reason || "Video upload analyzed by YOLO.",
      },
      emergency: {
        triggered: decision.emergency_alert === true || decision.emergency === true,
        countdown_seconds: decision.emergency_alert || decision.emergency ? 0 : 10,
        contact_status: decision.emergency_alert || decision.emergency ? "Notifying family" : "Standby",
      },
    });
    setApiOnline(true);
  } catch (error) {
    dom.videoUploadStatus.textContent = error.message;
    dom.videoUploadStatus.className = "danger";
    setApiOnline(false);
  }
}

function tickClock() {
  dom.clock.textContent = new Date().toLocaleTimeString("en-US", { hour12: false });
  machine.autoTick();
  renderStateMachine();
}

dom.cameraModeBtn.addEventListener("click", () => setMode("camera"));
dom.demoModeBtn.addEventListener("click", () => setMode("demo"));
dom.videoFileInput.addEventListener("change", (event) => uploadVideo(event.target.files[0]));
dom.videoDropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dom.videoDropZone.classList.add("dragging");
});
dom.videoDropZone.addEventListener("dragleave", () => dom.videoDropZone.classList.remove("dragging"));
dom.videoDropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  dom.videoDropZone.classList.remove("dragging");
  const file = event.dataTransfer.files[0];
  if (file) uploadVideo(file);
});
dom.refreshLogsBtn.addEventListener("click", refreshLogs);
dom.manualEmergencyBtn.addEventListener("click", triggerEmergency);
dom.voiceCheckBtn.addEventListener("click", toggleVoiceCheck);
window.addEventListener("resize", resizeCanvas);

setMode("camera");
renderStateMachine();
drawDetections();
updateFps();
tickClock();
refreshStatus();
refreshDetection();
refreshDecision();
refreshLogs();

setInterval(tickClock, 1000);
setInterval(refreshStatus, POLL_MS);
setInterval(refreshDetection, POLL_MS);
setInterval(refreshDecision, 5000);
setInterval(refreshLogs, 3500);
