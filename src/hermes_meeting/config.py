from __future__ import annotations

import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Server settings
    host: str = Field(default="0.0.0.0", description="Listen address")
    port: int = Field(default=8085, description="Listen port")
    debug: bool = Field(default=False, description="Enable debug logging")

    # Audio ingestion
    sample_rate: int = Field(default=16000, description="Audio sample rate (Hz)")
    channels: int = Field(default=1, description="Audio channels (mono)")
    chunk_duration_sec: float = Field(default=2.0, description="Streaming chunk slice duration")

    # Model / Engine settings
    # 'nemotron' on NVIDIA hosts (Sika), 'mock' for CPU/testing (Topo)
    diarization_engine: str = Field(
        default="nemotron" if os.environ.get("CUDA_VISIBLE_DEVICES") != "" and Path("/dev/nvidia0").exists() else "mock",
        description="Diarization engine: 'nemotron' or 'mock'"
    )
    nemotron_model: str = Field(
        default="nvidia/Nemotron-3-Diarization-preview",
        description="HuggingFace model ID or local path for Nemotron-3"
    )

    asr_engine: str = Field(
        default="parakeet" if os.environ.get("CUDA_VISIBLE_DEVICES") != "" and Path("/dev/nvidia0").exists() else "mock",
        description="ASR engine: 'parakeet' or 'mock'"
    )
    parakeet_model: str = Field(
        default="nvidia/parakeet-tdt-0.6b-v3",
        description="NeMo Parakeet model name or path"
    )

    # VRAM Offload / Idle TTL
    vram_idle_timeout_sec: int = Field(
        default=300,
        description="Seconds of inactivity before releasing models from GPU VRAM"
    )

    # Storage & Exports
    storage_dir: Path = Field(
        default=Path.home() / ".local/share/hermes-meeting",
        description="Root directory for meeting sessions and recordings"
    )
    obsidian_vault_dir: Path | None = Field(
        default=Path.home() / "Documents/Obsidian",
        description="Path to default Obsidian vault for meeting note exports"
    )

    # Hermes Agent integration
    hermes_bin: Path = Field(
        default=Path.home() / ".local/bin/hermes",
        description="Path to Hermes executable"
    )

    model_config = SettingsConfigDict(env_prefix="HERMES_MEETING_")


settings = Settings()
