import numpy as np
from hermes_meeting.audio.chunker import AudioChunker


def test_chunker_roundtrip():
    chunker = AudioChunker(target_sample_rate=16000)
    # Generate 1 second sine wave
    t = np.linspace(0, 1.0, 16000, endpoint=False, dtype=np.float32)
    sine = 0.5 * np.sin(2 * np.pi * 440 * t)

    wav_bytes = chunker.to_wav_bytes(sine)
    assert len(wav_bytes) > 0

    reloaded = chunker.load_from_bytes(wav_bytes)
    assert len(reloaded) == 16000
    assert np.allclose(reloaded, sine, atol=1e-3)
