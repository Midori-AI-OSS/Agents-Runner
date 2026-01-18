"""Docker container lifecycle management for interactive tasks.

Handles:
- Detached container launch with staging directory mount
- Terminal attach via subprocess
- Container exit monitoring via docker wait
- Completion marker reading and cleanup
"""

from __future__ import annotations

import os
import shlex
import subprocess
import threading
from datetime import datetime
from datetime import timezone
from pathlib import Path

from agents_runner.log_format import format_log
from agents_runner.ui.task_model import Task
from agents_runner.ui.task_staging import read_interactive_completion_marker


def start_container_wait_monitor(
    main_window: object,
    task_id: str,
    container_name: str,
) -> None:
    """Start a background thread to monitor container exit via docker wait.
    
    When the container exits:
    1. Reads completion marker from staging directory
    2. Updates task status and exit code
    3. Triggers finalization
    
    Args:
        main_window: MainWindow instance
        task_id: Task ID
        container_name: Container name
    """
    def _worker() -> None:
        try:
            # Wait for container to exit
            result = subprocess.run(
                ["docker", "wait", container_name],
                capture_output=True,
                text=True,
                timeout=None,  # Block until container exits
            )
            
            exit_code = 0
            try:
                exit_code = int(result.stdout.strip())
            except Exception:
                exit_code = 1
            
            # Read completion marker from staging directory
            marker = read_interactive_completion_marker(task_id)
            
            if marker:
                # Prefer completion marker data
                exit_code = int(marker.get("exit_code", exit_code))
                finished_at_str = str(marker.get("finished_at", ""))
                try:
                    finished_at = datetime.fromisoformat(
                        finished_at_str.replace("Z", "+00:00")
                    )
                except Exception:
                    finished_at = datetime.now(tz=timezone.utc)
            else:
                # Fallback to docker wait exit code
                finished_at = datetime.now(tz=timezone.utc)
            
            # Update task via main thread signal
            main_window.interactive_finished.emit(task_id, exit_code)
            
        except subprocess.TimeoutExpired:
            # Should not happen since we pass timeout=None
            pass
        except Exception as exc:
            main_window.host_log.emit(
                task_id,
                format_log(
                    "docker",
                    "wait",
                    "ERROR",
                    f"container wait failed: {exc}",
                ),
            )
    
    threading.Thread(target=_worker, daemon=True, name=f"docker-wait-{task_id}").start()


def start_recovery_container_monitor(
    main_window: object,
    task: Task,
) -> None:
    """Start container monitoring for recovery (after app restart).
    
    Similar to start_container_wait_monitor but for tasks recovered on startup.
    
    Args:
        main_window: MainWindow instance
        task: Task object
    """
    container_name = str(task.container_id or "").strip()
    if not container_name:
        return
    
    start_container_wait_monitor(
        main_window=main_window,
        task_id=task.task_id,
        container_name=container_name,
    )


def launch_attach_terminal(
    terminal_opt: object,
    container_name: str,
    host_workdir: str,
) -> bool:
    """Launch terminal emulator with docker attach command.
    
    Args:
        terminal_opt: Terminal option object
        container_name: Container name to attach to
        host_workdir: Working directory for terminal
    
    Returns:
        True if terminal launched successfully
    """
    from agents_runner.terminal_apps import launch_in_terminal
    
    # Build docker attach command
    attach_script = f"docker attach {shlex.quote(container_name)}"
    
    try:
        launch_in_terminal(terminal_opt, attach_script, cwd=host_workdir)
        return True
    except Exception:
        return False
