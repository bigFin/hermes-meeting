from __future__ import annotations

from typing import List
import numpy as np
from .engine import DiarizationEngine
from ..audio.aligner import SpeakerSegment


class MockDiarizationEngine(DiarizationEngine):
    """
    Mock diarization engine for testing on systems without NVIDIA GPUs (such as Topo).
    Alternates speaker labels every 4 seconds.
    """

    def __init__(self):
        self._loaded = True

    def diarize(self, audio: np.ndarray, sample_rate: int = 16000) -> List[SpeakerSegment]:
        total_duration = len(audio) / sample_rate
        if total_duration <= 0:
            return []

        segments: List[SpeakerSegment] = []
        chunk_len = 4.0
        current_time = 0.0
        speaker_idx = 0

        while current_time < total_duration:
            next_time = min(current_time + chunk_len, total_duration)
            segments.append(
                SpeakerSegment(
                    speaker=f"Speaker {speaker_idx}",
                    start=round(current_time, 2),
                    end=round(next_time, 2),
                )
            )
            current_time = next_time
            speaker_idx = (speaker_idx + 1) % 3

        return segments

    def unload(self) -> None:
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded
