from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

from midori_ai_logger import MidoriAiLogger

_fault_log_handle = None
logger = MidoriAiLogger(channel=None, name=__name__)


def _is_truthy_env(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _maybe_enable_faulthandler() -> None:
    """Enable faulthandler logging when requested via env var.

    This helps diagnose hard crashes (e.g., segfaults) where Python exceptions are not raised.
    Set `AGENTS_RUNNER_FAULTHANDLER=1` to write tracebacks to:
    `~/.midoriai/agents-runner/faulthandler.log`
    """
    if not _is_truthy_env("AGENTS_RUNNER_FAULTHANDLER"):
        return

    try:
        import faulthandler

        log_dir = Path.home() / ".midoriai" / "agents-runner"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "faulthandler.log"
        handle = open(log_path, "a", encoding="utf-8")
        faulthandler.enable(file=handle, all_threads=True)

        global _fault_log_handle
        _fault_log_handle = handle
    except Exception:
        # Best-effort: never block startup on diagnostics.
        pass


def _cleanup_stale_temp_files() -> None:
    """Clean up stale temporary files from previous runs.

    Removes files older than 24 hours from ~/.midoriai/agents-runner/:
    - interactive-finish-*.txt
    - stt-*.wav (audio recordings)
    - Other stale temporary files

    This handles edge cases where cleanup didn't run due to crashes or early exits.
    """
    try:
        base_dir = Path.home() / ".midoriai" / "agents-runner"
        if not base_dir.exists():
            return

        # Current time for age check (24 hours = 86400 seconds)
        current_time = time.time()
        max_age_seconds = 24 * 60 * 60

        # Patterns to clean up
        patterns = [
            "interactive-finish-*.txt",
            "stt-*.wav",
        ]

        removed_count = 0
        for pattern in patterns:
            for file_path in base_dir.glob(pattern):
                if not file_path.is_file():
                    continue
                try:
                    # Check file age
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > max_age_seconds:
                        file_path.unlink()
                        removed_count += 1
                except Exception:
                    # Ignore errors for individual files
                    pass

        # Also clean tmp subdirectory
        tmp_dir = base_dir / "tmp"
        if tmp_dir.exists():
            for file_path in tmp_dir.glob("stt-*.wav"):
                if not file_path.is_file():
                    continue
                try:
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > max_age_seconds:
                        file_path.unlink()
                        removed_count += 1
                except Exception:
                    pass

        if removed_count > 0:
            logger.rprint(f"Removed {removed_count} stale temporary file(s)", mode="info")
    except Exception as exc:
        # Don't fail app startup if cleanup fails
        logger.rprint(f"Failed to clean stale temp files: {exc}", mode="warn")


def _append_chromium_flags(existing: str, extra_flags: list[str]) -> str:
    tokens: list[str] = []
    existing = (existing or "").strip()
    if existing:
        tokens.extend(existing.split())
    existing_set = set(tokens)
    for flag in extra_flags:
        if flag not in existing_set:
            tokens.append(flag)
            existing_set.add(flag)
    return " ".join(tokens).strip()


def _upsert_qt_logging_rules(existing: str, required_rules: list[str]) -> str:
    tokens: list[str] = []
    existing_rules = (existing or "").replace("\n", ";").strip()
    if existing_rules:
        tokens.extend(rule.strip() for rule in existing_rules.split(";") if rule.strip())

    # Keep the last seen index for each key so we can replace effective rules.
    key_to_index: dict[str, int] = {}
    for idx, rule in enumerate(tokens):
        if "=" not in rule:
            continue
        key = str(rule.split("=", 1)[0]).strip().lower()
        if key:
            key_to_index[key] = idx

    for rule in required_rules:
        key = str(rule.split("=", 1)[0]).strip().lower()
        if not key:
            continue
        existing_idx = key_to_index.get(key)
        if existing_idx is None:
            key_to_index[key] = len(tokens)
            tokens.append(rule)
            continue
        tokens[existing_idx] = rule
    return ";".join(tokens)


def _configure_qt_logging_runtime() -> None:
    # Keep full Qt output in explicit diagnostics mode.
    if _is_truthy_env("AGENTS_RUNNER_QT_DIAGNOSTICS"):
        return

    os.environ.pop("QT_FFMPEG_DEBUG", None)
    existing_rules = os.environ.get("QT_LOGGING_RULES", "")
    os.environ["QT_LOGGING_RULES"] = _upsert_qt_logging_rules(
        existing_rules,
        [
            "default.warning=false",
            "qt.core.qfuture.continuations.warning=false",
            "qt.multimedia.ffmpeg=false",
            "qt.multimedia.ffmpeg.*=false",
        ],
    )


def _suppress_ffmpeg_native_logging() -> None:
    if _is_truthy_env("AGENTS_RUNNER_QT_DIAGNOSTICS"):
        return
    try:
        import ctypes
        import ctypes.util
        import PySide6
    except Exception:
        return

    mode = int(getattr(os, "RTLD_GLOBAL", 0) | getattr(os, "RTLD_NOW", 0))
    qt_lib_dir = Path(PySide6.__file__).resolve().parent / "Qt" / "lib"

    for stub_name in ("libQt6FFmpegStub-crypto.so.3", "libQt6FFmpegStub-ssl.so.3"):
        stub_path = qt_lib_dir / stub_name
        if not stub_path.is_file():
            continue
        try:
            ctypes.CDLL(str(stub_path), mode=mode)
        except Exception:
            continue

    avutil: Any | None = None
    for candidate in (
        qt_lib_dir / "libavutil.so.59",
        qt_lib_dir / "libavutil.so.60",
        qt_lib_dir / "libavutil.so",
    ):
        if not candidate.is_file():
            continue
        try:
            avutil = ctypes.CDLL(str(candidate), mode=mode)
            break
        except Exception:
            continue

    if avutil is None:
        candidate_name = str(ctypes.util.find_library("avutil") or "").strip()
        if candidate_name:
            try:
                avutil = ctypes.CDLL(candidate_name, mode=mode)
            except Exception:
                avutil = None
    if avutil is None:
        return

    try:
        av_log_set_level = avutil.av_log_set_level
        av_log_set_level.argtypes = [ctypes.c_int]
        av_log_set_level.restype = None
        av_log_set_level(16)  # AV_LOG_WARNING
    except Exception:
        return


def configure_qtwebengine_runtime() -> None:
    fontconfig_file = os.environ.get("FONTCONFIG_FILE")
    if not fontconfig_file:
        candidate = Path("/etc/fonts/fonts.conf")
        if candidate.is_file():
            os.environ["FONTCONFIG_FILE"] = str(candidate)

    if not Path("/dev/dri").exists():
        flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = _append_chromium_flags(
            flags,
            [
                "--disable-gpu",
                "--disable-gpu-compositing",
                "--disable-features=Vulkan",
            ],
        )


def _initialize_qtwebengine() -> None:
    """Initialize QtWebEngine at startup to prevent lazy-load flash."""
    try:
        from PySide6.QtWebEngineWidgets import QWebEngineView

        # Create a hidden dummy view to force Chromium initialization
        # This is garbage collected after initialization
        dummy = QWebEngineView()
        dummy.setParent(None)
        dummy.hide()
        dummy.deleteLater()

        logger.rprint("QtWebEngine initialized successfully", mode="info")
    except Exception as e:
        logger.rprint(f"QtWebEngine not available: {e}", mode="debug")


def run_app(argv: list[str]) -> None:
    _maybe_enable_faulthandler()
    _configure_qt_logging_runtime()
    _suppress_ffmpeg_native_logging()
    configure_qtwebengine_runtime()

    from agents_runner.diagnostics.crash_reporting import install_exception_hooks

    install_exception_hooks(argv=list(argv))

    from PySide6.QtWidgets import QApplication

    from agents_runner.environments import load_environments
    from agents_runner.ui.qt_diagnostics import install_qt_message_handler
    from agents_runner.setup.orchestrator import check_setup_complete
    from agents_runner.ui.style import app_stylesheet
    from agents_runner.ui.constants import APP_TITLE
    from agents_runner.ui.dialogs.first_run_setup import FirstRunSetupDialog
    from agents_runner.ui.dialogs.new_environment_wizard import NewEnvironmentWizard
    from agents_runner.ui.icons import app_icon
    from agents_runner.ui.main_window import MainWindow

    # Clean up stale temporary files from previous runs
    _cleanup_stale_temp_files()

    app = QApplication(argv)

    # Install Qt diagnostics handler for Issue #141 (QTimer thread warnings)
    # Enable via AGENTS_RUNNER_QT_DIAGNOSTICS=1 environment variable
    install_qt_message_handler()
    app.setApplicationDisplayName(APP_TITLE)
    app.setApplicationName(APP_TITLE)
    icon = app_icon()
    if icon is not None:
        app.setWindowIcon(icon)
    app.setStyleSheet(app_stylesheet())

    if _is_truthy_env("AGENTS_RUNNER_EAGER_QTWEBENGINE_INIT"):
        _initialize_qtwebengine()

    # Check if first-run setup is needed
    if not check_setup_complete():
        dialog = FirstRunSetupDialog(parent=None)
        dialog.exec()

    # Check if user has no environments and show wizard
    if not load_environments():
        wizard = NewEnvironmentWizard(parent=None)
        wizard.exec()

    window = MainWindow()
    if icon is not None:
        window.setWindowIcon(icon)
    window.show()
    sys.exit(app.exec())
