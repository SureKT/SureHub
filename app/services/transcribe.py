from functools import lru_cache
from pathlib import Path

from app.config import settings


@lru_cache(maxsize=1)
def _model():
    from faster_whisper import WhisperModel

    return WhisperModel(
        settings.WHISPER_MODEL,
        device=settings.WHISPER_DEVICE,
        compute_type=settings.WHISPER_COMPUTE_TYPE,
    )


def transcribe(audio_path: str | Path) -> str:
    segments, _ = _model().transcribe(
        str(audio_path),
        language=settings.WHISPER_LANGUAGE,
        vad_filter=True,
    )
    return " ".join(s.text.strip() for s in segments).strip()
