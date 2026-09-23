#!/usr/bin/env bash
set -euo pipefail

export PATH="/etc/profiles/per-user/fin/bin:$HOME/.local/bin:$PATH"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-${1:-8085}}"
HOST="${HOST:-0.0.0.0}"

# Auto-detect if CUDA device is present (e.g. Sika RTX 3090)
if [ -e /dev/nvidia0 ] && command -v nvidia-smi >/dev/null 2>&1; then
    export HERMES_MEETING_DIARIZATION_ENGINE="nemotron"
    export HERMES_MEETING_ASR_ENGINE="parakeet"
    echo "[hermes-meeting] Detected NVIDIA GPU. Using Nemotron-3 Diarization + Parakeet ASR."
else
    export HERMES_MEETING_DIARIZATION_ENGINE="mock"
    export HERMES_MEETING_ASR_ENGINE="mock"
    echo "[hermes-meeting] No NVIDIA GPU detected. Using Mock/CPU development engine."
fi

export HERMES_MEETING_PORT="$PORT"
export HERMES_MEETING_HOST="$HOST"

# Run with uv
exec uv run --directory "$DIR" python -m hermes_meeting.server --host "$HOST" --port "$PORT"
