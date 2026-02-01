"""
Qt diagnostic message handler for Issue #141.

Captures Qt warnings (especially QTimer cross-thread warnings) with full
stack traces to identify the exact source of threading issues.
"""

from __future__ import annotations

import logging
import os
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QtMsgType, qInstallMessageHandler

logger = logging.getLogger(__name__)

# Track whether the handler has been installed
_handler_installed = False

# Log file path
_QT_DIAGNOSTICS_LOG: Path | None = None


def _get_log_path() -> Path:
    """Get the path to the Qt diagnostics log file."""
    global _QT_DIAGNOSTICS_LOG
    if _QT_DIAGNOSTICS_LOG is None:
        log_dir = Path.home() / ".midoriai" / "agents-runner"
        log_dir.mkdir(parents=True, exist_ok=True)
        _QT_DIAGNOSTICS_LOG = log_dir / "qt-diagnostics.log"
    return _QT_DIAGNOSTICS_LOG


def _qt_message_handler(msg_type: QtMsgType, context, message: str) -> None:
    """
    Custom Qt message handler that captures warnings with stack traces.

    Specifically designed to diagnose Issue #141 (QTimer cross-thread warnings).
    """
    # Check if this is a QTimer-related warning
    is_timer_warning = any(
        keyword in message.lower()
        for keyword in ["qtimer", "timer", "thread", "qobject"]
    )

    # Always log to stderr for visibility
    msg_type_str = {
        QtMsgType.QtDebugMsg: "DEBUG",
        QtMsgType.QtInfoMsg: "INFO",
        QtMsgType.QtWarningMsg: "WARNING",
        QtMsgType.QtCriticalMsg: "CRITICAL",
        QtMsgType.QtFatalMsg: "FATAL",
    }.get(msg_type, "UNKNOWN")

    # Format basic message
    output_lines = [f"[Qt {msg_type_str}] {message}"]

    # Add context info if available
    if context.file:
        output_lines.append(f"  File: {context.file}:{context.line}")
    if context.function:
        output_lines.append(f"  Function: {context.function}")

    # For timer warnings, capture full stack trace
    if is_timer_warning and msg_type in (
        QtMsgType.QtWarningMsg,
        QtMsgType.QtCriticalMsg,
    ):
        output_lines.append("\n=== STACK TRACE ===")
        # Get the current stack, excluding this handler frame
        stack_frames = traceback.extract_stack()[:-1]
        for frame in stack_frames:
            output_lines.append(
                f'  File "{frame.filename}", line {frame.lineno}, in {frame.name}'
            )
            if frame.line:
                output_lines.append(f"    {frame.line}")
        output_lines.append("=== END STACK TRACE ===\n")

    full_output = "\n".join(output_lines)

    # Write to stderr
    print(full_output, file=sys.stderr, flush=True)

    # Write to log file
    try:
        log_path = _get_log_path()
        with open(log_path, "a", encoding="utf-8") as f:
            import datetime

            timestamp = datetime.datetime.now().isoformat()
            f.write(f"\n[{timestamp}]\n")
            f.write(full_output)
            f.write("\n")
    except Exception as e:
        # Don't let logging errors crash the app
        print(f"Failed to write to Qt diagnostics log: {e}", file=sys.stderr)


def install_qt_message_handler() -> None:
    """
    Install the Qt diagnostic message handler.

    This handler captures Qt warnings (especially QTimer thread warnings)
    with full stack traces to help diagnose Issue #141.

    Enable by setting the environment variable:
        AGENTS_RUNNER_QT_DIAGNOSTICS=1
    """
    global _handler_installed

    if _handler_installed:
        return

    # Check if diagnostics are enabled via environment variable
    enabled = str(os.environ.get("AGENTS_RUNNER_QT_DIAGNOSTICS", "")).strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return

    try:
        # Install the custom message handler
        qInstallMessageHandler(_qt_message_handler)
        _handler_installed = True

        log_path = _get_log_path()
        logger.info(f"Qt diagnostics enabled. Logging to: {log_path}")
        print(f"[Qt Diagnostics] Enabled. Logging to: {log_path}", file=sys.stderr)

        # Write header to log file
        with open(log_path, "a", encoding="utf-8") as f:
            import datetime

            f.write("\n" + "=" * 80 + "\n")
            f.write(
                f"Qt Diagnostics Log Started: {datetime.datetime.now().isoformat()}\n"
            )
            f.write("=" * 80 + "\n\n")

    except Exception as e:
        logger.error(f"Failed to install Qt message handler: {e}")


def get_diagnostics_log_path() -> Path | None:
    """Return the path to the Qt diagnostics log file if enabled."""
    if not _handler_installed:
        return None
    return _get_log_path()
