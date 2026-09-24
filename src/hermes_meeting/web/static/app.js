let mediaRecorder = null;
let audioChunks = [];
let recordStartTime = null;
let timerInterval = null;
let audioContext = null;
let analyser = null;
let currentTranscriptMarkdown = "";
let currentMeetingTitle = "Meeting " + new Date().toISOString().slice(0, 10);

const recordBtn = document.getElementById("record-btn");
const recordText = document.getElementById("record-text");
const timerEl = document.getElementById("timer");
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
          const groupName = p.is_remote ? "🌐 Beti Gateway (Avenue Intelligence)" : "🖥️ Local Sika";
          if (!groups[groupName]) {
            groups[groupName] = document.createElement("optgroup");
            groups[groupName].label = groupName;
            profileSelect.appendChild(groups[groupName]);
          }
          const opt = document.createElement("option");
          opt.value = p.id;
          opt.textContent = p.name;
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

// Setup Visualizer sizing
function resizeCanvas() {
  visualizerCanvas.width = visualizerCanvas.offsetWidth;
  visualizerCanvas.height = visualizerCanvas.offsetHeight;
}
window.addEventListener("resize", resizeCanvas);
resizeCanvas();

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
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];
    mediaRecorder = new MediaRecorder(stream);

    // Audio Visualizer setup
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioContext.createMediaStreamSource(stream);
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 64;
    source.connect(analyser);
    drawVisualizer();

    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.push(event.data);
      }
    };

    mediaRecorder.onstop = async () => {
      const audioBlob = new Blob(audioChunks, { type: "audio/wav" });
      await uploadAudioBlob(audioBlob);
      stream.getTracks().forEach((track) => track.stop());
    };

    mediaRecorder.start();
    recordBtn.classList.add("recording");
    recordText.textContent = "Stop & Transcribe";

    recordStartTime = Date.now();
    timerInterval = setInterval(updateTimer, 1000);
  } catch (err) {
    console.error("Microphone access error:", err);
    alert("Could not access microphone: " + err.message);
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
    recordBtn.classList.remove("recording");
    recordText.textContent = "Start Recording";
    clearInterval(timerInterval);
  }
}

function updateTimer() {
  const elapsed = Math.floor((Date.now() - recordStartTime) / 1000);
  const m = Math.floor(elapsed / 60).toString().padStart(2, "0");
  const s = (elapsed % 60).toString().padStart(2, "0");
  timerEl.textContent = `${m}:${s}`;
}

function drawVisualizer() {
  if (!analyser) return;
  requestAnimationFrame(drawVisualizer);

  const bufferLength = analyser.frequencyBinCount;
  const dataArray = new Uint8Array(bufferLength);
  analyser.getByteFrequencyData(dataArray);

  canvasCtx.fillStyle = "#272e33";
  canvasCtx.fillRect(0, 0, visualizerCanvas.width, visualizerCanvas.height);

  const barWidth = (visualizerCanvas.width / bufferLength) * 1.5;
  let x = 0;

  for (let i = 0; i < bufferLength; i++) {
    const barHeight = (dataArray[i] / 255) * visualizerCanvas.height;
    canvasCtx.fillStyle = "#a7c080";
    canvasCtx.fillRect(x, visualizerCanvas.height - barHeight, barWidth, barHeight);
    x += barWidth + 2;
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
  emptyState.innerHTML = "<p>⏳ Transcribing and diarizing speakers with Sika GPU...</p>";
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
    emptyState.innerHTML = `<p style="color: var(--accent-red);">Transcription failed: ${err.message}</p>`;
  }
}

function renderTranscript(data) {
  emptyState.style.display = "none";
  utteranceList.innerHTML = "";
  currentTranscriptMarkdown = data.markdown;

  if (!data.utterances || data.utterances.length === 0) {
    emptyState.innerHTML = "<p>No speech detected in audio.</p>";
    emptyState.style.display = "flex";
    return;
  }

  exportObsidianBtn.disabled = false;
  downloadMdBtn.disabled = false;
  if (sendGatewayBtn) sendGatewayBtn.disabled = false;

  data.utterances.forEach((u) => {
    const card = document.createElement("div");
    const spkClass = "speaker-" + (parseInt(u.speaker.replace(/\D/g, "") || 0) % 4);
    card.className = `utterance-card ${spkClass}`;

    const m = Math.floor(u.start / 60).toString().padStart(2, "0");
    const s = Math.floor(u.start % 60).toString().padStart(2, "0");

    card.innerHTML = `
      <div class="utterance-meta">
        <span class="speaker-tag">${u.speaker}</span>
        <span class="timestamp">${m}:${s}</span>
      </div>
      <div class="utterance-text">${u.text}</div>
    `;
    utteranceList.appendChild(card);
  });

  // Render Strategic Hints
  if (data.hints && data.hints.length > 0) {
    hintsList.innerHTML = "";
    data.hints.forEach((hint) => {
      const hCard = document.createElement("div");
      hCard.className = "hint-card";
      hCard.innerHTML = `
        <span class="hint-category">${hint.category}</span>
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

    sendGatewayBtn.textContent = "⏳ Sending...";
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
      sendGatewayBtn.textContent = "📤 Send to Discord";
      sendGatewayBtn.disabled = false;
    }
  });
}

