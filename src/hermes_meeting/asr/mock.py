from __future__ import annotations

from typing import List
import numpy as np
from .engine import ASREngine
from ..audio.aligner import WordTimestamp


class MockASREngine(ASREngine):
    """Mock ASR engine for local testing on CPU/Topo."""

    def __init__(self):
        self._loaded = True

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> List[WordTimestamp]:
        total_duration = len(audio) / sample_rate
        if total_duration <= 0.2:
            return []

        sample_words = [
            "Welcome", "everyone", "to", "our", "architecture", "sync",
            "today", "we", "are", "reviewing", "the", "meeting", "pipeline",
            "and", "deciding", "how", "Hermes", "can", "ground", "our", "notes",
            "in", "the", "Obsidian", "knowledge", "base", "smoothly"
        ]

        words: List[WordTimestamp] = []
        word_duration = 0.35
        curr = 0.1
        idx = 0

        while curr + word_duration <= total_duration and idx < len(sample_words):
            words.append(
                WordTimestamp(
                    word=sample_words[idx],
                    start=round(curr, 2),
                    end=round(curr + word_duration, 2),
                    confidence=0.98,
                )
            )
            curr += word_duration + 0.05
            idx += 1

        return words

    def unload(self) -> None:
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded
