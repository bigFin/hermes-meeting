from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List
import numpy as np
from ..audio.aligner import SpeakerSegment


class DiarizationEngine(ABC):
    """Abstract interface for multi-speaker diarization."""

    @abstractmethod
    def diarize(self, audio: np.ndarray, sample_rate: int = 16000) -> List[SpeakerSegment]:
        """Perform speaker diarization on 16kHz mono audio."""
        pass

    @abstractmethod
    def unload(self) -> None:
        """Release model weights from VRAM/memory."""
        pass

    @property
    @abstractmethod
    def is_loaded(self) -> bool:
        """Return True if model is currently resident in VRAM."""
        pass
