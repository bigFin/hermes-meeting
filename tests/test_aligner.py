from hermes_meeting.audio.aligner import (
    WordTimestamp,
    SpeakerSegment,
    align_words_to_speakers,
)


def test_align_words_to_speakers():
    words = [
        WordTimestamp(word="Hello", start=0.0, end=0.4),
        WordTimestamp(word="world", start=0.5, end=0.9),
        WordTimestamp(word="How", start=1.5, end=1.8),
        WordTimestamp(word="are", start=1.9, end=2.1),
        WordTimestamp(word="you?", start=2.2, end=2.6),
    ]

    segments = [
        SpeakerSegment(speaker="Speaker 0", start=0.0, end=1.0),
        SpeakerSegment(speaker="Speaker 1", start=1.4, end=3.0),
    ]

    utterances = align_words_to_speakers(words, segments)

    assert len(utterances) == 2
    assert utterances[0].speaker == "Speaker 0"
    assert utterances[0].text == "Hello world"
    assert utterances[1].speaker == "Speaker 1"
    assert utterances[1].text == "How are you?"
