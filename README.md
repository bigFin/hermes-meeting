# Hermes Meeting

Intelligent meeting companion, multi-speaker diarization, and Hermes knowledge-grounded scribe.

Designed for real-time and post-meeting transcription across devices (phone, laptop, desktop), leveraging **NVIDIA Nemotron-3-Diarization** and **Parakeet TDT ASR** on Sika's RTX 3090, with dynamic on-demand GPU loading and idle VRAM termination via `llama-swap`.

## Features

- **Multi-Speaker Diarization**: Uses NVIDIA Nemotron-3-Diarization to identify and separate up to 8 speakers, including during cross-talk and overlapping speech.
- **Word-Level ASR Alignment**: Pairs with Parakeet TDT 0.6B to match words to speaker intervals with high precision.
- **Dynamic VRAM Lifecycle**: Auto-managed by `llama-swap` on Sika; holds **0 MB VRAM** when idle and releases memory after meetings.
- **Hermes Knowledge Grounding**: Real-time strategist sidebar queries QMD and Obsidian notes as topics are discussed.
- **Obsidian Scribe**: Automatically distills transcripts into Obsidian markdown with YAML frontmatter, executive summary, action items (`- [ ]`), and speaker-attributed timestamps.
- **Responsive Web Canvas**: Mobile and desktop web interface for live mic recording, waveform visualization, and voice memo drag-and-drop.

## Hardware Architecture

| Host | Role | Acceleration | Engines |
| :--- | :--- | :--- | :--- |
| **Sika** | Heavy compute backend | NVIDIA RTX 3090 (24 GB) | Nemotron-3 Diarization + Parakeet TDT |
| **Topo** | Client / WebUI / Laptop | AMD Radeon 780M / CPU | Web client + Mock/CPU dev engine |
| **Phone** | Client / Audio capture | Mobile Web / PWA | Audio recording & live strategist feed |

## Quickstart

Run development server locally with `uv`:

```bash
cd ~/projects/hermes-meeting
uv run python -m hermes_meeting.server --port 8085
```

Or run via the auto-detect launcher:

```bash
./run.sh
```

Run test suite:

```bash
uv run pytest
```

## Sika Integration with `llama-swap`

To expose this service on Sika with automatic idle VRAM termination, add this block to `dotfiles/sika/llama-swap/config.yaml`:

```yaml
models:
  "hermes-meeting":
    name: "Hermes Meeting Transcriber"
    cmd: "bash /home/fin/projects/hermes-meeting/run.sh ${PORT}"
    proxy: "http://127.0.0.1:${PORT}"
    checkEndpoint: /health
```

When Topo or your phone sends audio to `http://sika:8080/v1/...` (or direct port), `llama-swap` wakes up the RTX 3090, transcribes the audio, and drops VRAM to 0 MB 5 minutes after the meeting concludes.
