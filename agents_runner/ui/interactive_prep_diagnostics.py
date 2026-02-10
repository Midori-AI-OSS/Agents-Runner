from __future__ import annotations

import threading
import time

from agents_runner.log_format import format_log


def prep_diag_line(prep_id: str, level: str, message: str) -> str:
    level_text = str(level or "INFO").strip().upper() or "INFO"
    return format_log("ui", "prepdiag", level_text, f"[prep:{prep_id}] {message}")


def init_interactive_prep_diag(
    *,
    main_window: object,
    task_id: str,
    task_created_at_s: float,
    prep_id: str,
) -> None:
    lock = threading.Lock()
    stop_event = threading.Event()
    main_window._interactive_prep_diag[task_id] = {
        "prep_id": str(prep_id or "").strip(),
        "created_at_s": float(task_created_at_s or time.time()),
        "last_callback_at_s": 0.0,
        "callback_count": 0,
        "stage_callback_count": 0,
        "log_callback_count": 0,
        "success_callback_count": 0,
        "failed_callback_count": 0,
        "last_stage": "starting",
        "last_callback_kind": "",
        "warned_no_progress": False,
        "lock": lock,
        "stop_event": stop_event,
    }


def log_interactive_prep_diag(
    *, main_window: object, task_id: str, prep_id: str, level: str, message: str
) -> None:
    main_window._on_task_log(task_id, prep_diag_line(prep_id, level, message))


def touch_interactive_prep_callback(
    *, main_window: object, task_id: str, kind: str, stage: str = ""
) -> None:
    diag = main_window._interactive_prep_diag.get(task_id)
    if not isinstance(diag, dict):
        return
    lock = diag.get("lock")
    if lock is None:
        return
    acquired = False
    try:
        lock.acquire()
        acquired = True
        now_s = time.time()
        diag["last_callback_at_s"] = now_s
        diag["callback_count"] = int(diag.get("callback_count", 0)) + 1
        diag["last_callback_kind"] = str(kind or "")
        if stage:
            diag["last_stage"] = str(stage or "")
        key = f"{kind}_callback_count"
        diag[key] = int(diag.get(key, 0)) + 1
    except Exception:
        pass
    finally:
        if acquired:
            try:
                lock.release()
            except Exception:
                pass


def stop_interactive_prep_diag(*, main_window: object, task_id: str) -> None:
    diag = main_window._interactive_prep_diag.pop(str(task_id or "").strip(), None)
    if not isinstance(diag, dict):
        return
    stop_event = diag.get("stop_event")
    if isinstance(stop_event, threading.Event):
        stop_event.set()


def start_interactive_prep_heartbeat(
    *,
    main_window: object,
    task_id: str,
    prep_id: str,
    task_created_at_s: float,
    interval_s: float = 10.0,
    warn_no_progress_after_s: float = 30.0,
) -> None:
    diag = main_window._interactive_prep_diag.get(task_id)
    if not isinstance(diag, dict):
        return
    stop_event = diag.get("stop_event")
    if not isinstance(stop_event, threading.Event):
        return

    def _worker() -> None:
        main_window.host_log.emit(
            task_id,
            prep_diag_line(
                prep_id, "INFO", f"heartbeat started interval_s={interval_s:.0f}"
            ),
        )
        while not stop_event.wait(interval_s):
            active_task = main_window._tasks.get(task_id)
            if active_task is None:
                break

            elapsed_s = time.time() - float(task_created_at_s or time.time())
            callback_count = 0
            stage_callbacks = 0
            log_callbacks = 0
            last_callback_age_s = -1.0
            last_stage = str(active_task.status or "").strip()
            last_callback_kind = ""
            warn_no_progress = False

            current_diag = main_window._interactive_prep_diag.get(task_id)
            if isinstance(current_diag, dict):
                lock = current_diag.get("lock")
                if lock is not None:
                    acquired = False
                    try:
                        lock.acquire()
                        acquired = True
                        callback_count = int(current_diag.get("callback_count", 0))
                        stage_callbacks = int(
                            current_diag.get("stage_callback_count", 0)
                        )
                        log_callbacks = int(current_diag.get("log_callback_count", 0))
                        last_callback_s = float(
                            current_diag.get("last_callback_at_s", 0.0) or 0.0
                        )
                        last_stage = (
                            str(current_diag.get("last_stage") or "").strip()
                            or last_stage
                        )
                        last_callback_kind = str(
                            current_diag.get("last_callback_kind") or ""
                        ).strip()
                        warned = bool(current_diag.get("warned_no_progress"))
                        if (
                            callback_count == 0
                            and elapsed_s >= warn_no_progress_after_s
                            and not warned
                        ):
                            current_diag["warned_no_progress"] = True
                            warn_no_progress = True
                        if last_callback_s > 0.0:
                            last_callback_age_s = time.time() - last_callback_s
                    except Exception:
                        pass
                    finally:
                        if acquired:
                            try:
                                lock.release()
                            except Exception:
                                pass

            callback_age_text = (
                f"{last_callback_age_s:.1f}" if last_callback_age_s >= 0.0 else "none"
            )
            main_window.host_log.emit(
                task_id,
                prep_diag_line(
                    prep_id,
                    "INFO",
                    "heartbeat "
                    f"status={str(active_task.status or '').strip() or 'unknown'} "
                    f"phase={last_stage or 'unknown'} "
                    f"elapsed_s={elapsed_s:.1f} "
                    f"callbacks={callback_count} "
                    f"stage_callbacks={stage_callbacks} "
                    f"log_callbacks={log_callbacks} "
                    f"last_callback_kind={last_callback_kind or 'none'} "
                    f"last_callback_age_s={callback_age_text}",
                ),
            )
            if warn_no_progress:
                main_window.host_log.emit(
                    task_id,
                    prep_diag_line(
                        prep_id,
                        "WARN",
                        f"no callback progress observed for {warn_no_progress_after_s:.0f}s while task is active",
                    ),
                )
        main_window.host_log.emit(
            task_id, prep_diag_line(prep_id, "INFO", "heartbeat stopped")
        )

    threading.Thread(target=_worker, daemon=True).start()
