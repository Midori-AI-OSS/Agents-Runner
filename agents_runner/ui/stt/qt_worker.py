from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtCore import Signal

from agents_runner.stt.transcribe import transcribe_audio_file


class SttWorker(QObject):
    done = Signal(str, str)
    error = Signal(str, str)

    def __init__(self, *, mode: str, audio_path: str) -> None:
        super().__init__()
        self._mode = str(mode or "")
        self._audio_path = str(audio_path or "")

    def run(self) -> None:
        try:
            text = transcribe_audio_file(mode=self._mode, audio_path=self._audio_path)
        except Exception as exc:
            self.error.emit(str(exc) or "Speech-to-text failed.", self._audio_path)
            return
        self.done.emit(text, self._audio_path)
