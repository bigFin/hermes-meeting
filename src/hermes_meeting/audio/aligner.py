from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List


@dataclass
class WordTimestamp:
    word: str
    start: float
    end: float
    confidence: float = 1.0


@dataclass
class SpeakerSegment:
    speaker: str
    start: float
    end: float


@dataclass
class Utterance:
    speaker: str
    start: float
    end: float
    text: str

    def to_dict(self) -> dict:
        return asdict(self)


def align_words_to_speakers(
    words: List[WordTimestamp],
    speaker_segments: List[SpeakerSegment],
    default_speaker: str = "Speaker 0"
) -> List[Utterance]:
    """
    Assigns each word to the speaker segment with the maximum temporal overlap.
    Merges adjacent words attributed to the same speaker into coherent Utterances.
    """
    if not words:
        return []

    if not speaker_segments:
        # Fallback if no speaker segments exist
        full_text = " ".join(w.word for w in words)
        return [Utterance(speaker=default_speaker, start=words[0].start, end=words[-1].end, text=full_text)]

    attributed_words: List[tuple[str, WordTimestamp]] = []

    for w in words:
        word_mid = (w.start + w.end) / 2.0
        best_speaker = default_speaker
        max_overlap = -1.0

        for seg in speaker_segments:
            # Check overlap between word and segment
            overlap_start = max(w.start, seg.start)
            overlap_end = min(w.end, seg.end)
            overlap = overlap_end - overlap_start

            if overlap > max_overlap:
                max_overlap = overlap
                best_speaker = seg.speaker
            elif max_overlap <= 0 and (seg.start <= word_mid <= seg.end):
                best_speaker = seg.speaker

        attributed_words.append((best_speaker, w))

    # Merge consecutive words from the same speaker into utterances
    utterances: List[Utterance] = []
    current_speaker: str | None = None
    current_words: List[str] = []
    start_time: float = 0.0
    end_time: float = 0.0

    for spk, w in attributed_words:
        if spk != current_speaker:
            if current_speaker is not None and current_words:
                utterances.append(
                    Utterance(
                        speaker=current_speaker,
                        start=round(start_time, 2),
                        end=round(end_time, 2),
                        text=" ".join(current_words),
                    )
                )
            current_speaker = spk
            current_words = [w.word]
            start_time = w.start
            end_time = w.end
        else:
            current_words.append(w.word)
            end_time = w.end

    if current_speaker is not None and current_words:
        utterances.append(
            Utterance(
                speaker=current_speaker,
                start=round(start_time, 2),
                end=round(end_time, 2),
                text=" ".join(current_words),
            )
        )

    return utterances
