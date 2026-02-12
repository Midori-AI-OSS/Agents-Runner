"""Tests for mic_recorder graceful degradation."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agents_runner.stt.mic_recorder import (
    FfmpegPulseRecorder,
    MicRecorderError,
)


class TestFfmpegPulseRecorder:
    """Test graceful degradation when PulseAudio/PipeWire is unavailable."""

    def test_start_raises_error_when_ffmpeg_not_found(self) -> None:
        """Test that MicRecorderError is raised when ffmpeg is not in PATH."""
        with patch("shutil.which", return_value=None):
            recorder = FfmpegPulseRecorder()
            with pytest.raises(
                MicRecorderError, match="Could not find `ffmpeg` in PATH"
            ):
                recorder.start()

    def test_start_handles_file_not_found_error(self) -> None:
        """Test that FileNotFoundError is converted to MicRecorderError."""
        with (
            patch("shutil.which", return_value="/usr/bin/ffmpeg"),
            patch(
                "subprocess.Popen",
                side_effect=FileNotFoundError("ffmpeg not found"),
            ),
        ):
            recorder = FfmpegPulseRecorder()
            with pytest.raises(
                MicRecorderError,
                match="Could not start ffmpeg \\(executable not found\\)",
            ):
                recorder.start()

    def test_start_handles_permission_error(self) -> None:
        """Test that PermissionError is converted to MicRecorderError."""
        with (
            patch("shutil.which", return_value="/usr/bin/ffmpeg"),
            patch(
                "subprocess.Popen",
                side_effect=PermissionError("Permission denied"),
            ),
        ):
            recorder = FfmpegPulseRecorder()
            with pytest.raises(
                MicRecorderError, match="Could not start ffmpeg \\(permission denied\\)"
            ):
                recorder.start()

    def test_start_handles_os_error(self) -> None:
        """Test that OSError is converted to MicRecorderError."""
        with (
            patch("shutil.which", return_value="/usr/bin/ffmpeg"),
            patch(
                "subprocess.Popen",
                side_effect=OSError("System error"),
            ),
        ):
            recorder = FfmpegPulseRecorder()
            with pytest.raises(
                MicRecorderError, match="Could not start ffmpeg: System error"
            ):
                recorder.start()

    def test_start_detects_immediate_process_failure(self) -> None:
        """Test that immediate process failure (e.g., PulseAudio unavailable) is detected."""
        mock_process = MagicMock()
        mock_process.poll.return_value = 1  # Process exited with error
        mock_process.stderr.read.return_value = (
            b"Server connection failed: Connection refused"
        )

        with (
            patch("shutil.which", return_value="/usr/bin/ffmpeg"),
            patch("subprocess.Popen", return_value=mock_process),
        ):
            recorder = FfmpegPulseRecorder()
            with pytest.raises(
                MicRecorderError, match="Server connection failed: Connection refused"
            ):
                recorder.start()

    def test_start_provides_default_error_when_no_stderr(self) -> None:
        """Test that a default error message is provided when process fails with no stderr."""
        mock_process = MagicMock()
        mock_process.poll.return_value = 1  # Process exited with error
        mock_process.stderr = None

        with (
            patch("shutil.which", return_value="/usr/bin/ffmpeg"),
            patch("subprocess.Popen", return_value=mock_process),
        ):
            recorder = FfmpegPulseRecorder()
            with pytest.raises(
                MicRecorderError,
                match="Could not connect to audio server \\(PulseAudio/PipeWire may be unavailable\\)",
            ):
                recorder.start()

    def test_is_available_returns_true_when_ffmpeg_exists(self) -> None:
        """Test that is_available returns True when ffmpeg is in PATH."""
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            assert FfmpegPulseRecorder.is_available() is True

    def test_is_available_returns_false_when_ffmpeg_missing(self) -> None:
        """Test that is_available returns False when ffmpeg is not in PATH."""
        with patch("shutil.which", return_value=None):
            assert FfmpegPulseRecorder.is_available() is False

    def test_successful_start_returns_mic_recording(self) -> None:
        """Test that a successful start returns a MicRecording object."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process still running
        mock_process.pid = 12345

        with (
            patch("shutil.which", return_value="/usr/bin/ffmpeg"),
            patch("subprocess.Popen", return_value=mock_process),
            tempfile.TemporaryDirectory() as tmpdir,
        ):
            recorder = FfmpegPulseRecorder(output_dir=Path(tmpdir))
            recording = recorder.start()

            assert recording.process == mock_process
            assert recording.output_path.parent == Path(tmpdir)
            assert recording.started_at_s > 0
