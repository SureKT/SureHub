import os
from functools import lru_cache
from pathlib import Path

from app.config import settings


def _ensure_cache_dir() -> Path:
    cache = Path(settings.WHISPER_CACHE_DIR)
    cache.mkdir(parents=True, exist_ok=True)
    # faster-whisper / huggingface_hub respect HF_HOME
    os.environ.setdefault("HF_HOME", str(cache))
    return cache


@lru_cache(maxsize=1)
def _model():
    from faster_whisper import WhisperModel

    cache = _ensure_cache_dir()
    return WhisperModel(
        settings.WHISPER_MODEL,
        device=settings.WHISPER_DEVICE,
        compute_type=settings.WHISPER_COMPUTE_TYPE,
        download_root=str(cache),
    )


def transcribe(audio_path: str | Path) -> str:
    segments, _ = _model().transcribe(
        str(audio_path),
        language=settings.WHISPER_LANGUAGE,
        vad_filter=True,
    )
    return " ".join(s.text.strip() for s in segments).strip()
