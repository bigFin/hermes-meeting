from __future__ import annotations

import io
import wave
import numpy as np
import soundfile as sf


class AudioChunker:
    """Handles audio normalization, resampling, and buffer chunking for 16kHz mono audio."""

    def __init__(self, target_sample_rate: int = 16000):
        self.target_sample_rate = target_sample_rate

    def load_from_bytes(self, audio_bytes: bytes) -> np.ndarray:
        """Loads arbitrary audio bytes (WAV, MP3, OGG, WebM) into normalized 16kHz float32 mono."""
        with io.BytesIO(audio_bytes) as bio:
            data, sr = sf.read(bio, dtype="float32")

        # Convert stereo/multichannel to mono
        if data.ndim > 1:
            data = np.mean(data, axis=1)

        # Simple linear resampling if sample rate doesn't match
        if sr != self.target_sample_rate:
            duration = len(data) / sr
            target_length = int(duration * self.target_sample_rate)
            data = np.interp(
                np.linspace(0, len(data), target_length, endpoint=False),
                np.arange(len(data)),
                data
            ).astype(np.float32)

        return data

    def to_wav_bytes(self, audio_data: np.ndarray) -> bytes:
        """Converts float32 numpy array back to 16kHz 16-bit PCM WAV bytes."""
        bio = io.BytesIO()
        # Scale to 16-bit PCM
        scaled = np.clip(audio_data, -1.0, 1.0)
        sf.write(bio, scaled, self.target_sample_rate, format="WAV", subtype="PCM_16")
        return bio.getvalue()
