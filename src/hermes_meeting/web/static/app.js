let mediaRecorder = null;
let audioChunks = [];
let recordStartTime = null;
let timerInterval = null;
let audioContext = null;
let analyser = null;
let activeAudioStreams = [];
let currentTranscriptMarkdown = "";
let currentMeetingTitle = "Meeting " + new Date().toISOString().slice(0, 10);

const recordBtn = document.getElementById("record-btn");
const recordText = document.getElementById("record-text");
const timerEl = document.getElementById("timer");
const audioSourceSelect = document.getElementById("audio-source-select");
const emptyState = document.getElementById("empty-state");
const utteranceList = document.getElementById("utterance-list");
const hintsList = document.getElementById("hints-list");
const fileInput = document.getElementById("audio-file-input");
const exportObsidianBtn = document.getElementById("export-obsidian-btn");
const downloadMdBtn = document.getElementById("download-md-btn");
const visualizerCanvas = document.getElementById("visualizer");
const canvasCtx = visualizerCanvas.getContext("2d");
const profileSelect = document.getElementById("profile-select");
const sendGatewayBtn = document.getElementById("send-gateway-btn");
const themeBtn = document.getElementById("theme-btn");

// Theme Handling (Paper vs Blueprint)
function initTheme() {
  const saved = localStorage.getItem("hermes-theme") || "paper";
  document.documentElement.setAttribute("data-theme", saved);
  updateThemeBtn(saved);
}

function updateThemeBtn(theme) {
  if (themeBtn) {
    themeBtn.textContent = theme === "dark" ? "THEME: BLUEPRINT" : "THEME: PAPER";
  }
}

if (themeBtn) {
  themeBtn.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme") || "paper";
    const next = current === "dark" ? "paper" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("hermes-theme", next);
    updateThemeBtn(next);
    if (!mediaRecorder || mediaRecorder.state !== "recording") {
      drawIdleVisualizer();
    }
  });
}
initTheme();

// Discover installed Hermes profiles on server
async function loadProfiles() {
  try {
    const res = await fetch("/api/profiles");
    if (res.ok) {
      const data = await res.json();
      if (profileSelect && data.profiles && data.profiles.length > 0) {
        profileSelect.innerHTML = "";
        const groups = {};
        data.profiles.forEach((p) => {
          const groupName = p.is_remote ? "REMOTE: BETI GATEWAY" : "LOCAL: SIKA STATION";
          if (!groups[groupName]) {
            groups[groupName] = document.createElement("optgroup");
            groups[groupName].label = groupName;
            profileSelect.appendChild(groups[groupName]);
          }
          const opt = document.createElement("option");
          opt.value = p.id;
          opt.textContent = p.name.toUpperCase();
          if (p.profile === data.default || p.id === data.default) opt.selected = true;
          groups[groupName].appendChild(opt);
        });
      }
    }
  } catch (err) {
    console.warn("Could not load profiles:", err);
  }
}
loadProfiles();

// Setup Pointillist Sounder sizing & initial frame
function resizeCanvas() {
  visualizerCanvas.width = visualizerCanvas.offsetWidth;
  visualizerCanvas.height = visualizerCanvas.offsetHeight;
  if (!mediaRecorder || mediaRecorder.state !== "recording") {
    drawIdleVisualizer();
  }
}
window.addEventListener("resize", resizeCanvas);
resizeCanvas();

function drawIdleVisualizer() {
  if (!visualizerCanvas) return;
  const w = visualizerCanvas.width;
  const h = visualizerCanvas.height;
  const isDark = document.documentElement.getAttribute("data-theme") === "dark";

  canvasCtx.clearRect(0, 0, w, h);

  // Horizontal dotted graticules
  canvasCtx.strokeStyle = isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.08)";
  canvasCtx.lineWidth = 1;
  canvasCtx.setLineDash([2, 5]);
  [0.25, 0.5, 0.75].forEach((frac) => {
    canvasCtx.beginPath();
    canvasCtx.moveTo(0, h * frac);
    canvasCtx.lineTo(w, h * frac);
    canvasCtx.stroke();
  });
  canvasCtx.setLineDash([]);

  // Stippled baseline dots
  const numColumns = 48;
  const colSpacing = w / numColumns;
  canvasCtx.fillStyle = isDark ? "rgba(255,255,255,0.18)" : "rgba(0,0,0,0.18)";
  for (let c = 0; c < numColumns; c++) {
    const x = Math.floor(c * colSpacing + colSpacing / 2);
    canvasCtx.fillRect(x, h - 6, 2, 2);
  }
}

// Recording logic
recordBtn.addEventListener("click", async () => {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    stopRecording();
  } else {
    await startRecording();
  }
});

fileInput.addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  await uploadAudioFile(file);
});

async function startRecording() {
  activeAudioStreams = [];
  try {
    const sourceMode = audioSourceSelect ? audioSourceSelect.value : "mic";
    let recordStream = null;

    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 64;

    if (sourceMode === "digital") {
      // 1. Microphone stream
      const micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      activeAudioStreams.push(micStream);

      // 2. System / screen audio stream
      let displayStream = null;
      try {
        displayStream = await navigator.mediaDevices.getDisplayMedia({
          video: true,
          audio: true,
        });
      } catch (displayErr) {
        throw new Error("System audio capture cancelled or denied: " + displayErr.message);
      }

      const sysAudioTracks = displayStream.getAudioTracks();
      if (sysAudioTracks.length === 0) {
        displayStream.getTracks().forEach((track) => track.stop());
        throw new Error("No system audio track selected. Make sure to check 'Share audio' or 'Also share tab audio' in the sharing dialog.");
      }

      // Stop video tracks immediately so we don't capture or process video frames
      displayStream.getVideoTracks().forEach((track) => track.stop());
      activeAudioStreams.push(displayStream);

      // WebAudio Mixing
      const mixedDest = audioContext.createMediaStreamDestination();
      const mixerGain = audioContext.createGain();

      const micSource = audioContext.createMediaStreamSource(micStream);
      const sysSource = audioContext.createMediaStreamSource(displayStream);

      micSource.connect(mixerGain);
      sysSource.connect(mixerGain);

      mixerGain.connect(analyser);
      mixerGain.connect(mixedDest);

      recordStream = mixedDest.stream;
    } else {
      // Physical Room (Mic only)
      const micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      activeAudioStreams.push(micStream);

      const micSource = audioContext.createMediaStreamSource(micStream);
      micSource.connect(analyser);

      recordStream = micStream;
    }

    audioChunks = [];
    mediaRecorder = new MediaRecorder(recordStream);

    drawVisualizer();

    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.push(event.data);
      }
    };

    mediaRecorder.onstop = async () => {
      const audioBlob = new Blob(audioChunks, { type: "audio/wav" });
      await uploadAudioBlob(audioBlob);
      activeAudioStreams.forEach((stream) => {
        stream.getTracks().forEach((track) => track.stop());
      });
      activeAudioStreams = [];
      if (audioContext && audioContext.state !== "closed") {
        audioContext.close();
      }
      if (audioSourceSelect) audioSourceSelect.disabled = false;
      drawIdleVisualizer();
    };

    mediaRecorder.start();
    if (audioSourceSelect) audioSourceSelect.disabled = true;
    recordBtn.classList.add("recording");
    recordText.textContent = "STOP & TRANSCRIBE";

    recordStartTime = Date.now();
    timerInterval = setInterval(updateTimer, 1000);
  } catch (err) {
    console.error("Audio recording error:", err);
    activeAudioStreams.forEach((stream) => {
      stream.getTracks().forEach((track) => track.stop());
    });
    activeAudioStreams = [];
    if (audioContext && audioContext.state !== "closed") {
      audioContext.close();
    }
    if (audioSourceSelect) audioSourceSelect.disabled = false;
    recordBtn.classList.remove("recording");
    recordText.textContent = "START RECORDING";
    clearInterval(timerInterval);
    drawIdleVisualizer();
    alert(err.message || "Failed to start recording.");
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
    recordBtn.classList.remove("recording");
    recordText.textContent = "START RECORDING";
    clearInterval(timerInterval);
    if (audioSourceSelect) audioSourceSelect.disabled = false;
  }
}

function updateTimer() {
  const elapsed = Math.floor((Date.now() - recordStartTime) / 1000);
  const m = Math.floor(elapsed / 60).toString().padStart(2, "0");
  const s = (elapsed % 60).toString().padStart(2, "0");
  timerEl.textContent = `MET ${m}:${s}`;
}

// Pointillist sounder rendering (discrete ink stipples)
function drawVisualizer() {
  if (!analyser || (mediaRecorder && mediaRecorder.state !== "recording")) return;
  requestAnimationFrame(drawVisualizer);

  const bufferLength = analyser.frequencyBinCount;
  const dataArray = new Uint8Array(bufferLength);
  analyser.getByteFrequencyData(dataArray);

  const w = visualizerCanvas.width;
  const h = visualizerCanvas.height;
  const isDark = document.documentElement.getAttribute("data-theme") === "dark";

  canvasCtx.clearRect(0, 0, w, h);

  // Graticules
  canvasCtx.strokeStyle = isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.08)";
  canvasCtx.lineWidth = 1;
  canvasCtx.setLineDash([2, 5]);
  [0.25, 0.5, 0.75].forEach((frac) => {
    canvasCtx.beginPath();
    canvasCtx.moveTo(0, h * frac);
    canvasCtx.lineTo(w, h * frac);
    canvasCtx.stroke();
  });
  canvasCtx.setLineDash([]);

  const numColumns = 48;
  const step = Math.max(1, Math.floor(bufferLength / numColumns));
  const colSpacing = w / numColumns;
  const dotSpacing = 5;
  const maxDots = Math.floor((h - 10) / dotSpacing);

  const dotColor = isDark ? "#64b5f6" : "#183e60";
  const baselineColor = isDark ? "rgba(255,255,255,0.18)" : "rgba(0,0,0,0.18)";

  for (let c = 0; c < numColumns; c++) {
    const freqVal = dataArray[c * step] || 0;
    const energy = freqVal / 255;
    const activeDots = Math.floor(energy * maxDots);
    const x = Math.floor(c * colSpacing + colSpacing / 2);

    for (let d = 0; d <= maxDots; d++) {
      const y = h - 6 - d * dotSpacing;
      if (d === 0) {
        canvasCtx.fillStyle = d <= activeDots ? dotColor : baselineColor;
        canvasCtx.fillRect(x, y, 2, 2);
      } else if (d <= activeDots) {
        canvasCtx.fillStyle = dotColor;
        canvasCtx.fillRect(x, y, 2, 2);
      }
    }
  }
}

async function uploadAudioBlob(blob) {
  const formData = new FormData();
  formData.append("file", blob, "recording.wav");
  formData.append("title", currentMeetingTitle);
  if (profileSelect) formData.append("profile", profileSelect.value);
  await sendTranscriptionRequest(formData);
}

async function uploadAudioFile(file) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("title", file.name.replace(/\.[^/.]+$/, ""));
  if (profileSelect) formData.append("profile", profileSelect.value);
  await sendTranscriptionRequest(formData);
}

async function sendTranscriptionRequest(formData) {
  emptyState.innerHTML = "<p>[ TRANSCRIBING &amp; DIARIZING WITH SIKA GPU... ]</p>";
  emptyState.style.display = "flex";
  utteranceList.innerHTML = "";

  try {
    const res = await fetch("/api/transcribe", {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      throw new Error(`Server returned ${res.status}`);
    }

    const data = await res.json();
    renderTranscript(data);
  } catch (err) {
    console.error("Transcription error:", err);
    emptyState.innerHTML = `<p style="color: var(--stamp-rust);">[ TRANSCRIPTION FAILED: ${err.message} ]</p>`;
  }
}

function renderTranscript(data) {
  emptyState.style.display = "none";
  utteranceList.innerHTML = "";
  currentTranscriptMarkdown = data.markdown;

  if (!data.utterances || data.utterances.length === 0) {
    emptyState.innerHTML = "<p>[ NO SPEECH DETECTED IN AUDIO SAMPLE ]</p>";
    emptyState.style.display = "flex";
    return;
  }

  exportObsidianBtn.disabled = false;
  downloadMdBtn.disabled = false;
  if (sendGatewayBtn) sendGatewayBtn.disabled = false;

  data.utterances.forEach((u) => {
    const row = document.createElement("div");
    const spkNum = parseInt(u.speaker.replace(/\D/g, "") || 0);
    const spkClass = "speaker-" + (spkNum % 4);
    row.className = `log-row ${spkClass}`;

    const m = Math.floor(u.start / 60).toString().padStart(2, "0");
    const s = Math.floor(u.start % 60).toString().padStart(2, "0");
    const spkTag = `[SPK-${spkNum.toString().padStart(2, "0")}]`;

    row.innerHTML = `
      <div class="col-time">${m}:${s}</div>
      <div class="col-channel"><span class="channel-tag">${spkTag}</span></div>
      <div class="col-text">${u.text}</div>
    `;
    utteranceList.appendChild(row);
  });

  // Render Strategic Telemetry Hints
  if (data.hints && data.hints.length > 0) {
    hintsList.innerHTML = "";
    data.hints.forEach((hint, idx) => {
      const hCard = document.createElement("div");
      hCard.className = "hint-card";
      const itemNum = (idx + 1).toString().padStart(2, "0");
      hCard.innerHTML = `
        <div class="hint-header">
          <span class="hint-category">§ ${hint.category.toUpperCase()}</span>
          <span class="hint-id">#${itemNum}</span>
        </div>
        <h4>${hint.title}</h4>
        <p>${hint.content}</p>
      `;
      hintsList.appendChild(hCard);
    });
  }
}

// Export actions
downloadMdBtn.addEventListener("click", () => {
  if (!currentTranscriptMarkdown) return;
  const blob = new Blob([currentTranscriptMarkdown], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${currentMeetingTitle}.md`;
  a.click();
  URL.revokeObjectURL(url);
});

exportObsidianBtn.addEventListener("click", async () => {
  if (!currentTranscriptMarkdown) return;
  try {
    const res = await fetch("/api/export-obsidian", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: currentMeetingTitle,
        content: currentTranscriptMarkdown,
      }),
    });
    const result = await res.json();
    if (result.ok) {
      alert(`Saved to Obsidian: ${result.path}`);
    } else {
      alert(`Error saving to Obsidian: ${result.error}`);
    }
  } catch (err) {
    alert(`Failed to save to Obsidian: ${err.message}`);
  }
});

if (sendGatewayBtn) {
  sendGatewayBtn.addEventListener("click", async () => {
    if (!currentTranscriptMarkdown) return;
    const confirmSend = confirm("Send this meeting synthesis to the Hermes Discord gateway on Beti?");
    if (!confirmSend) return;

    sendGatewayBtn.textContent = "SENDING...";
    sendGatewayBtn.disabled = true;

    try {
      const res = await fetch("/api/send-gateway", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          gateway: "beti",
          message: currentTranscriptMarkdown,
          subject: currentMeetingTitle,
          target: "discord",
        }),
      });
      const result = await res.json();
      if (result.ok) {
        alert(result.message || "Delivered to Beti Discord gateway!");
      } else {
        alert("Failed to deliver to gateway: " + result.error);
      }
    } catch (err) {
      alert("Error sending to gateway: " + err.message);
    } finally {
      sendGatewayBtn.textContent = "DISCORD ↗";
      sendGatewayBtn.disabled = false;
    }
  });
}
