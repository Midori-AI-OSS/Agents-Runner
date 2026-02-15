from __future__ import annotations

import json
import os
import platform
import sys
import threading
import traceback
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_hooks_installed = False


def crash_reports_dir() -> Path:
    root = Path.home() / ".midoriai" / "agents-runner" / "crash-reports"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _format_exception(exc: BaseException) -> str:
    return "".join(
        traceback.format_exception(type(exc), exc, exc.__traceback__)
    ).strip()


def _build_report_payload(
    exc: BaseException,
    *,
    context: str,
    argv: list[str] | None,
) -> dict[str, Any]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "context": str(context),
        "pid": os.getpid(),
        "argv": list(argv) if argv is not None else None,
        "python": {
            "version": sys.version,
            "executable": sys.executable,
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
        },
        "exception": {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": _format_exception(exc),
        },
        "diagnostics_hints": {
            "faulthandler_env": "AGENTS_RUNNER_FAULTHANDLER=1",
            "qt_diagnostics_env": "AGENTS_RUNNER_QT_DIAGNOSTICS=1",
        },
    }


def report_fatal_exception(
    exc: BaseException,
    *,
    context: str,
    argv: list[str] | None = None,
) -> Path | None:
    """Write a crash report and return its path (best-effort).

    This should never raise; failures return None.
    """
    try:
        reports_dir = crash_reports_dir()
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        path = reports_dir / f"crash-{stamp}-{os.getpid()}.json"
        payload = _build_report_payload(exc, context=context, argv=argv)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return path
    except Exception:
        return None


def install_exception_hooks(*, argv: list[str] | None = None) -> None:
    """Install global exception hooks that write crash reports.

    This is intentionally best-effort and will not raise.
    """
    global _hooks_installed
    if _hooks_installed:
        return
    _hooks_installed = True

    try:
        original_sys_hook = sys.excepthook

        def _sys_hook(
            exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            exc_tb: types.TracebackType | None,
        ) -> None:
            try:
                exc = (
                    exc_value
                    if isinstance(exc_value, BaseException)
                    else RuntimeError(str(exc_value))
                )
                path = report_fatal_exception(
                    exc, context="sys.excepthook", argv=argv or list(sys.argv)
                )
                if path is not None:
                    print(
                        f"Agents Runner crashed. Crash report: {path}",
                        file=sys.stderr,
                        flush=True,
                    )
            except Exception:
                pass
            try:
                original_sys_hook(exc_type, exc_value, exc_tb)
            except Exception:
                pass

        sys.excepthook = _sys_hook

        original_threading_hook = getattr(threading, "excepthook", None)

        def _thread_hook(args: threading.ExceptHookArgs) -> None:
            try:
                thread_name = getattr(getattr(args, "thread", None), "name", "unknown")
                exc_value = getattr(args, "exc_value", None)
                if isinstance(exc_value, BaseException):
                    report_fatal_exception(
                        exc_value,
                        context=f"threading.excepthook:{thread_name}",
                        argv=argv or list(sys.argv),
                    )
            except Exception:
                pass
            if callable(original_threading_hook):
                try:
                    original_threading_hook(args)
                except Exception:
                    pass

        if hasattr(threading, "excepthook"):
            threading.excepthook = _thread_hook  # type: ignore[assignment]
    except Exception:
        # Never block startup on diagnostics.
        return
