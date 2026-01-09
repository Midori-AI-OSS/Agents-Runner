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
    mode_value = str(mode or "").strip().lower()
    if mode_value == SttMode.ONLINE:
        return _transcribe_online(audio_path)
    return _transcribe_offline(audio_path)


def _transcribe_online(audio_path: str) -> str:
    try:
        import speech_recognition as sr
    except Exception as exc:
        raise TranscribeError(
            "Online speech-to-text requires the `SpeechRecognition` dependency."
        ) from exc

    recognizer = sr.Recognizer()
    with sr.AudioFile(audio_path) as source:
        audio = recognizer.record(source)
    try:
        return str(recognizer.recognize_google(audio) or "").strip()
    except Exception as exc:  # SpeechRecognition has many ad-hoc error types.
        raise TranscribeError(str(exc) or "Online transcription failed.") from exc


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

