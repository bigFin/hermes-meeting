from __future__ import annotations

import gc
import logging
import tempfile
from pathlib import Path
from typing import List
import numpy as np
import soundfile as sf

from .engine import ASREngine
from ..audio.aligner import WordTimestamp
from ..config import settings

logger = logging.getLogger(__name__)


class ParakeetASREngine(ASREngine):
    """
    NVIDIA Parakeet-TDT ASR engine producing word-level timestamps.
    Supports on-demand VRAM loading and automatic release.
    """

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.parakeet_model
        self._model = None
        self._torch = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return

        try:
            import torch
            import nemo.collections.asr as nemo_asr
        except ImportError as e:
            raise RuntimeError(
                "NVIDIA NeMo or PyTorch is not installed. "
                "Ensure torch and nemo_toolkit are available in your CUDA environment."
            ) from e

        self._torch = torch
        logger.info("Loading Parakeet ASR model: %s into CUDA...", self.model_name)
        self._model = nemo_asr.models.ASRModel.from_pretrained(model_name=self.model_name)
        if torch.cuda.is_available():
            self._model = self._model.cuda()
        self._model.eval()
        logger.info("Parakeet ASR successfully loaded in VRAM.")

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> List[WordTimestamp]:
        self._ensure_loaded()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            sf.write(tmp_path, audio, sample_rate)

        try:
            # Transcribe with return_hypotheses=True to extract word timestamps
            hypotheses = self._model.transcribe([str(tmp_path)], return_hypotheses=True)
            words: List[WordTimestamp] = []

            if hypotheses and len(hypotheses) > 0:
                hyp = hypotheses[0]
                # Extract word offsets if available in NeMo hypothesis
                if hasattr(hyp, "words") and hasattr(hyp, "word_offsets"):
                    for word_str, offset in zip(hyp.words, hyp.word_offsets):
                        start = offset.get("start_offset", 0.0)
                        end = offset.get("end_offset", start + 0.3)
                        words.append(WordTimestamp(word=word_str, start=round(start, 2), end=round(end, 2)))
                else:
                    # Fallback: estimate equidistant timestamps if offsets aren't emitted
                    text = hyp.text if hasattr(hyp, "text") else str(hyp)
                    raw_words = text.split()
                    duration = len(audio) / sample_rate
                    if raw_words:
                        step = duration / len(raw_words)
                        for i, w in enumerate(raw_words):
                            words.append(
                                WordTimestamp(
                                    word=w,
                                    start=round(i * step, 2),
                                    end=round((i + 1) * step, 2),
                                )
                            )

            return words
        finally:
            tmp_path.unlink(missing_ok=True)

    def unload(self) -> None:
        if self._model is not None:
            logger.info("Unloading Parakeet ASR from VRAM...")
            del self._model
            self._model = None
            if self._torch and self._torch.cuda.is_available():
                self._torch.cuda.empty_cache()
            gc.collect()
            logger.info("Parakeet ASR unloaded. VRAM freed.")

    @property
    def is_loaded(self) -> bool:
        return self._model is not None
