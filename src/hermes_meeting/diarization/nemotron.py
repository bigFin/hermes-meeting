from __future__ import annotations

import gc
import logging
import tempfile
from pathlib import Path
from typing import List
import numpy as np
import soundfile as sf

from .engine import DiarizationEngine
from ..audio.aligner import SpeakerSegment
from ..config import settings

logger = logging.getLogger(__name__)


class NemotronDiarizationEngine(DiarizationEngine):
    """
    Production NVIDIA Nemotron-3-Diarization engine.
    Supports on-demand GPU loading and immediate VRAM release on idle.
    """

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.nemotron_model
        self._model = None
        self._torch = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return

        try:
            import torch
            from nemo.collections.asr.models import SortformerEncLabelModel
        except ImportError as e:
            raise RuntimeError(
                "NVIDIA NeMo or PyTorch is not installed. "
                "Ensure torch and nemo_toolkit are available in your CUDA environment."
            ) from e

        self._torch = torch
        logger.info("Loading Nemotron-3-Diarization model: %s into CUDA...", self.model_name)
        self._model = SortformerEncLabelModel.from_pretrained(model_name=self.model_name)
        if torch.cuda.is_available():
            self._model = self._model.cuda()
        self._model.eval()
        logger.info("Nemotron-3-Diarization successfully loaded in VRAM.")

    def diarize(self, audio: np.ndarray, sample_rate: int = 16000) -> List[SpeakerSegment]:
        self._ensure_loaded()

        # Write to temporary wav for NeMo batch ingestion
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            sf.write(tmp_path, audio, sample_rate)

        try:
            # Run Sortformer / Nemotron inference
            # NeMo returns time boundaries with predicted speaker IDs
            predicted_segments = self._model.diarize(paths2audio_files=[str(tmp_path)])
            segments: List[SpeakerSegment] = []

            # Parse NeMo diarization output format
            if predicted_segments and len(predicted_segments) > 0:
                for line in predicted_segments[0]:
                    # Standard NeMo diarization tuple/entry format: (start_time, end_time, speaker_label)
                    start, end, spk = line
                    segments.append(
                        SpeakerSegment(
                            speaker=f"Speaker {spk}",
                            start=round(float(start), 2),
                            end=round(float(end), 2),
                        )
                    )
            return segments
        finally:
            tmp_path.unlink(missing_ok=True)

    def unload(self) -> None:
        if self._model is not None:
            logger.info("Unloading Nemotron-3-Diarization from VRAM...")
            del self._model
            self._model = None
            if self._torch and self._torch.cuda.is_available():
                self._torch.cuda.empty_cache()
            gc.collect()
            logger.info("Nemotron-3-Diarization unloaded. VRAM freed.")

    @property
    def is_loaded(self) -> bool:
        return self._model is not None
