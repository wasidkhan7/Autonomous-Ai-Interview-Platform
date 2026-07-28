import tempfile
from pathlib import Path
from faster_whisper import WhisperModel
from app.config import get_settings

settings = get_settings()

_model = None


def get_whisper_model():
    """
    Lazily loaded once per process — loading model weights from disk is
    expensive, so we don't want to reload it on every single transcription
    call. Same pattern as embeddings.py's get_embedding_model().
    """
    global _model
    if _model is None:
        _model = WhisperModel(settings.WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    return _model


def _transcribe_bytes(audio_bytes: bytes, beam_size: int = 2) -> str:
    """
    Shared internal helper: writes raw audio bytes to a temporary file
    (faster-whisper needs a real file path, not in-memory bytes directly),
    transcribes it, then cleans up the temp file automatically.
    """
    model = get_whisper_model()

    with tempfile.NamedTemporaryFile(suffix=".webm", delete=True) as tmp_file:
        tmp_file.write(audio_bytes)
        tmp_file.flush()

        segments, _info = model.transcribe(tmp_file.name, beam_size=beam_size)
        full_text = " ".join(segment.text.strip() for segment in segments)

    return full_text.strip()


def transcribe_partial(audio_buffer: bytes) -> str:
    """
    Called repeatedly (every 2-3 seconds) on the growing audio buffer for
    an in-progress turn. Powers the 'live captions' the candidate sees
    while still speaking. beam_size=1 (greedy decoding) trades some
    accuracy for speed - acceptable here since this is never scored,
    just a rough live preview.
    """
    if not audio_buffer:
        return ""
    return _transcribe_bytes(audio_buffer, beam_size=1)


def transcribe_final(audio_buffer: bytes) -> str:
    """
    Called ONCE, when the candidate's turn is finalized. This result
    becomes the actual answer_text stored and scored - beam_size=2 keeps
    a small accuracy safety net here since this is the permanent record,
    while still being meaningfully faster than the original beam_size=5.
    """
    if not audio_buffer:
        return ""
    return _transcribe_bytes(audio_buffer, beam_size=2)