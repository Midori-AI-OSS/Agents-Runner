from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time

from dataclasses import dataclass
from pathlib import Path

# Timeout for detecting immediate process failures (e.g., PulseAudio unavailable)
PROCESS_START_TIMEOUT_SECONDS = 0.1


@dataclass(frozen=True, slots=True)
class MicRecording:
    output_path: Path
    started_at_s: float
    process: subprocess.Popen[bytes]


class MicRecorderError(RuntimeError):
    pass


class FfmpegPulseRecorder:
    def __init__(self, *, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir or Path(
            os.path.expanduser("~/.midoriai/agents-runner/tmp")
        )

    @staticmethod
    def is_available() -> bool:
        return shutil.which("ffmpeg") is not None

    def start(self) -> MicRecording:
        if not self.is_available():
            raise MicRecorderError("Could not find `ffmpeg` in PATH.")

        self._output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self._output_dir / f"stt-{int(time.time() * 1000)}.wav"

        args = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "pulse",
            "-i",
            "default",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ]

        try:
            process = subprocess.Popen(
                args,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise MicRecorderError(
                "Could not start ffmpeg (executable not found)."
            ) from exc
        except PermissionError as exc:
            raise MicRecorderError(
                "Could not start ffmpeg (permission denied)."
            ) from exc
        except OSError as exc:
            raise MicRecorderError(f"Could not start ffmpeg: {exc}") from exc

        # Check if process failed immediately (e.g., PulseAudio/PipeWire unavailable)
        # Use wait() with a short timeout to avoid unnecessary delay on success
        try:
            poll_result = process.wait(timeout=PROCESS_START_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            # Process is still running - success case
            poll_result = None

        if poll_result is not None:
            # Process already exited - read error message
            stderr_text = ""
            if process.stderr:
                try:
                    stderr_bytes = process.stderr.read()
                    stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()
                except (IOError, OSError, UnicodeDecodeError):
                    # Failed to read stderr, use default message
                    pass

            error_msg = (
                stderr_text
                or "Could not connect to audio server (PulseAudio/PipeWire may be unavailable)."
            )
            raise MicRecorderError(error_msg)

        return MicRecording(
            output_path=output_path, started_at_s=time.time(), process=process
        )

    def stop(self, recording: MicRecording, *, timeout_s: float = 2.0) -> Path:
        if recording.process.poll() is None:
            try:
                recording.process.send_signal(signal.SIGINT)
            except Exception:
                recording.process.terminate()

        try:
            _stdout, stderr = recording.process.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            recording.process.kill()
            try:
                _stdout, stderr = recording.process.communicate(timeout=timeout_s)
            except subprocess.TimeoutExpired as exc:
                raise MicRecorderError(
                    "Timed out while stopping the microphone recording."
                ) from exc

        if (
            recording.process.returncode not in (0, 255)
            and recording.process.stderr is not None
        ):
            stderr_text = ""
            try:
                if isinstance(stderr, (bytes, bytearray)):
                    stderr_text = stderr.decode("utf-8", errors="replace")
            except Exception:
                stderr_text = ""
            stderr_text = (stderr_text or "").strip()
            if stderr_text:
                raise MicRecorderError(stderr_text)
            raise MicRecorderError("ffmpeg failed while stopping the recording.")

        if not recording.output_path.is_file():
            raise MicRecorderError("Recording did not produce an output file.")

        try:
            file_size = recording.output_path.stat().st_size
            if file_size < 512:
                raise MicRecorderError("Recording file is empty.")
        except OSError as exc:
            raise MicRecorderError("Could not stat recording output file.") from exc

        return recording.output_path
