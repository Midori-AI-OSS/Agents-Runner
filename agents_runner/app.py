from __future__ import annotations

import os
import sys
import time
from pathlib import Path


_FAULT_LOG_HANDLE = None


def _maybe_enable_faulthandler() -> None:
    """Enable faulthandler logging when requested via env var.

    This helps diagnose hard crashes (e.g., segfaults) where Python exceptions are not raised.
    Set `AGENTS_RUNNER_FAULTHANDLER=1` to write tracebacks to:
    `~/.midoriai/agents-runner/faulthandler.log`
    """
    enabled = str(os.environ.get("AGENTS_RUNNER_FAULTHANDLER", "")).strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return

    try:
        import faulthandler

        log_dir = Path.home() / ".midoriai" / "agents-runner"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "faulthandler.log"
        handle = open(log_path, "a", encoding="utf-8")
        faulthandler.enable(file=handle, all_threads=True)

        global _FAULT_LOG_HANDLE
        _FAULT_LOG_HANDLE = handle
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
            print(f"[cleanup] Removed {removed_count} stale temporary file(s)")
    except Exception as exc:
        # Don't fail app startup if cleanup fails
        print(f"[cleanup] Warning: failed to clean stale temp files: {exc}")


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


def _configure_qtwebengine_runtime() -> None:
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
        import logging
        logger = logging.getLogger(__name__)
        
        # Create a hidden dummy view to force Chromium initialization
        # This is garbage collected after initialization
        dummy = QWebEngineView()
        dummy.setParent(None)
        dummy.hide()
        dummy.deleteLater()
        
        logger.info("QtWebEngine initialized successfully")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"QtWebEngine not available: {e}")


def run_app(argv: list[str]) -> None:
    _maybe_enable_faulthandler()
    _configure_qtwebengine_runtime()

    from PySide6.QtWidgets import QApplication

    from agents_runner.environments import load_environments
    from agents_runner.qt_diagnostics import install_qt_message_handler
    from agents_runner.setup.orchestrator import check_setup_complete
    from agents_runner.style import app_stylesheet
    from agents_runner.ui.constants import APP_TITLE
    from agents_runner.ui.dialogs.first_run_setup import FirstRunSetupDialog
    from agents_runner.ui.dialogs.new_environment_wizard import NewEnvironmentWizard
    from agents_runner.ui.icons import _app_icon
    from agents_runner.ui.main_window import MainWindow

    # Clean up stale temporary files from previous runs
    _cleanup_stale_temp_files()

    app = QApplication(argv)
    
    # Install Qt diagnostics handler for Issue #141 (QTimer thread warnings)
    # Enable via AGENTS_RUNNER_QT_DIAGNOSTICS=1 environment variable
    install_qt_message_handler()
    app.setApplicationDisplayName(APP_TITLE)
    app.setApplicationName(APP_TITLE)
    icon = _app_icon()
    if icon is not None:
        app.setWindowIcon(icon)
    app.setStyleSheet(app_stylesheet())

    # Initialize QtWebEngine early to prevent lazy-load flash
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
