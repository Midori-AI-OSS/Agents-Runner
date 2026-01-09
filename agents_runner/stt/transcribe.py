from __future__ import annotations

import os

from enum import StrEnum
from pathlib import Path


class SttMode(StrEnum):
    OFFLINE = "offline"
    ONLINE = "online"


class TranscribeError(RuntimeError):
    pass


def transcribe_audio_file(*, mode: str, audio_path: str) -> str:
    return _transcribe_offline(audio_path)


def _transcribe_offline(audio_path: str) -> str:
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:
        raise TranscribeError(
            "Offline speech-to-text requires the `faster-whisper` dependency."
        ) from exc

    download_root = Path(
        os.path.expanduser("~/.midoriai/agents-runner/models/faster-whisper")
    )
    download_root.mkdir(parents=True, exist_ok=True)

    model = WhisperModel(
        "base",
        device="cpu",
        compute_type="int8",
        download_root=str(download_root),
    )
    segments, _info = model.transcribe(audio_path, vad_filter=True)
    parts: list[str] = []
    for segment in segments:
        text = str(getattr(segment, "text", "") or "").strip()
        if text:
            parts.append(text)
    return " ".join(parts).strip()
