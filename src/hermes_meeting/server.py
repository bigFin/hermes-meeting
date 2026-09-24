from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request

from .agent.scribe import MeetingScribe
from .agent.strategist import MeetingStrategist
from .audio.aligner import align_words_to_speakers
from .audio.chunker import AudioChunker
from .config import settings
from .diarization.mock import MockDiarizationEngine
from .diarization.nemotron import NemotronDiarizationEngine
from .asr.mock import MockASREngine
from .asr.parakeet import ParakeetASREngine

logging.basicConfig(level=logging.INFO if not settings.debug else logging.DEBUG)
logger = logging.getLogger("hermes-meeting")

# Engine State & Idle Manager
last_active_time = time.monotonic()
diarization_engine = None
asr_engine = None
chunker = AudioChunker(target_sample_rate=settings.sample_rate)
scribe = MeetingScribe()
strategist = MeetingStrategist()


def get_diarization_engine():
    global diarization_engine, last_active_time
    last_active_time = time.monotonic()
    if diarization_engine is None:
        if settings.diarization_engine == "nemotron":
            diarization_engine = NemotronDiarizationEngine(settings.nemotron_model)
        else:
            diarization_engine = MockDiarizationEngine()
    return diarization_engine


def get_asr_engine():
    global asr_engine, last_active_time
    last_active_time = time.monotonic()
    if asr_engine is None:
        if settings.asr_engine == "parakeet":
            asr_engine = ParakeetASREngine(settings.parakeet_model)
        else:
            asr_engine = MockASREngine()
    return asr_engine


async def idle_checker_loop():
    """Background task that unloads models from VRAM when idle exceeding TTL."""
    global diarization_engine, asr_engine
    while True:
        await asyncio.sleep(15)
        idle_duration = time.monotonic() - last_active_time
        if idle_duration > settings.vram_idle_timeout_sec:
            if diarization_engine and diarization_engine.is_loaded:
                logger.info("Idle TTL reached (%ds). Unloading diarization engine...", idle_duration)
                diarization_engine.unload()
            if asr_engine and asr_engine.is_loaded:
                logger.info("Idle TTL reached (%ds). Unloading ASR engine...", idle_duration)
                asr_engine.unload()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Hermes Meeting server on %s:%d", settings.host, settings.port)
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    task = asyncio.create_task(idle_checker_loop())
    yield
    # Shutdown
    task.cancel()
    if diarization_engine:
        diarization_engine.unload()
    if asr_engine:
        asr_engine.unload()


app = FastAPI(title="Hermes Meeting Companion", lifespan=lifespan)

# Setup Templates & Static
web_dir = Path(__file__).parent / "web"
static_dir = web_dir / "static"
templates_dir = web_dir / "templates"

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"settings": settings},
    )


@app.get("/health")
async def health():
    """Health check endpoint compatible with llama-swap."""
    return {
        "status": "ok",
        "diarization_loaded": diarization_engine.is_loaded if diarization_engine else False,
        "asr_loaded": asr_engine.is_loaded if asr_engine else False,
        "engine_mode": {
            "diarization": settings.diarization_engine,
            "asr": settings.asr_engine,
        },
    }


@app.get("/api/profiles")
async def list_profiles():
    """Discover available Hermes profiles on the host."""
    profiles = []
    if settings.hermes_profiles_dir.exists():
        for d in settings.hermes_profiles_dir.iterdir():
            if d.is_dir() and ((d / "config.yaml").exists() or (d / "SOUL.md").exists()):
                profiles.append(d.name)
    if not profiles:
        profiles = ["main", "analyst", "briefer", "voice-chat"]
    profiles.sort()
    return {"profiles": profiles, "default": settings.default_profile}


class ObsidianExportRequest(BaseModel):
    title: str
    content: str
    folder: Optional[str] = "Meetings"


@app.post("/api/export-obsidian")
async def export_obsidian(req: ObsidianExportRequest):
    path = scribe.save_to_vault(req.title, req.content, folder=req.folder)
    if path:
        return {"ok": True, "path": str(path)}
    return {"ok": False, "error": "Obsidian vault directory not configured or does not exist."}


@app.post("/api/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    title: Optional[str] = Form("Meeting Notes"),
    profile: Optional[str] = Form(None),
):
    global last_active_time
    last_active_time = time.monotonic()
    selected_profile = profile or settings.default_profile

    try:
        content = await file.read()
        audio_data = chunker.load_from_bytes(content)
    except Exception as e:
        logger.error("Failed to read audio file: %s", e)
        raise HTTPException(status_code=400, detail=f"Invalid audio format: {e}")

    logger.info("Transcribing audio (%d samples, %.1fs, profile=%s)...", len(audio_data), len(audio_data) / settings.sample_rate, selected_profile)

    # 1. Run ASR for word timestamps
    asr = get_asr_engine()
    words = asr.transcribe(audio_data, settings.sample_rate)

    # 2. Run Diarization for speaker segments
    diarizer = get_diarization_engine()
    speaker_segments = diarizer.diarize(audio_data, settings.sample_rate)

    # 3. Align words to speakers
    utterances = align_words_to_speakers(words, speaker_segments)

    # 4. Generate Scribe markdown
    markdown = scribe.format_markdown(title or "Meeting", utterances, profile=selected_profile)

    # 5. Extract strategic hints
    hints = [
        {"category": h.category, "title": h.title, "content": h.content, "source": h.source}
        for h in strategist.analyze_recent(utterances, profile=selected_profile)
    ]

    return {
        "ok": True,
        "title": title,
        "profile": selected_profile,
        "utterances": [u.to_dict() for u in utterances],
        "markdown": markdown,
        "hints": hints,
    }


def main():
    parser = argparse.ArgumentParser(description="Hermes Meeting Server")
    parser.add_argument("--host", default=settings.host, help="Listen host")
    parser.add_argument("--port", type=int, default=settings.port, help="Listen port")
    parser.add_argument("--engine", choices=["nemotron", "mock"], default=settings.diarization_engine, help="Diarization engine")
    args = parser.parse_args()

    settings.host = args.host
    settings.port = args.port
    settings.diarization_engine = args.engine

    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
