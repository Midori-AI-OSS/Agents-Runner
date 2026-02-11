from __future__ import annotations

from agents_runner.log_format import format_log


def prep_diag_line(prep_id: str, level: str, message: str) -> str:
    level_text = str(level or "INFO").strip().upper() or "INFO"
    return format_log("ui", "prepdiag", level_text, f"[prep:{prep_id}] {message}")


def log_interactive_prep_diag(
    *, main_window: object, task_id: str, prep_id: str, level: str, message: str
) -> None:
    level_text = str(level or "INFO").strip().upper() or "INFO"
    if level_text not in {"WARN", "ERROR"}:
        return
    main_window._on_task_log(task_id, prep_diag_line(prep_id, level_text, message))
