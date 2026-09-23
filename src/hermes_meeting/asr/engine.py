from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List
import numpy as np
from ..audio.aligner import WordTimestamp


class ASREngine(ABC):
    """Abstract interface for Speech-to-Text with word-level timestamps."""

    @abstractmethod
    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> List[WordTimestamp]:
        """Transcribe 16kHz mono audio and return words with exact start and end timestamps."""
        pass

    @abstractmethod
    def unload(self) -> None:
        """Release ASR model weights from VRAM/memory."""
        pass

    @property
    @abstractmethod
    def is_loaded(self) -> bool:
        """Return True if model is currently resident in VRAM."""
        pass
