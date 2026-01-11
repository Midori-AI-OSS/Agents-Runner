"""Log file collector for diagnostics bundles."""

import os
from typing import Any

from agents_runner.persistence import default_state_path
from agents_runner.persistence import load_state


# Maximum log content per task (1MB)
MAX_LOG_SIZE_PER_TASK = 1024 * 1024

# Maximum total log content (10MB)
MAX_TOTAL_LOG_SIZE = 10 * 1024 * 1024

# Maximum number of recent tasks to include logs from
MAX_RECENT_TASKS = 10


def collect_logs() -> dict[str, str]:
    """
    Collect recent application and task logs for diagnostics.
    
    Currently collects logs from:
    - Recent task logs stored in task state
    
    Future enhancements could include:
    - Application log files if configured
    - System stdout/stderr if redirected
    
    Returns:
        Dictionary mapping log filename to log content
    """
    logs: dict[str, str] = {}
    total_size = 0
    
    # Load task state to get task logs
    try:
        state_path = default_state_path()
        state = load_state(state_path)
        tasks_data = state.get("tasks", {})
        
        if not tasks_data:
            return logs
        
        # Sort tasks by creation time (most recent first)
        tasks_list = []
        for task_id, task_data in tasks_data.items():
            if isinstance(task_data, dict):
                created_at = task_data.get("created_at_s", 0)
                tasks_list.append((created_at, task_id, task_data))
        
        tasks_list.sort(reverse=True)
        
        # Collect logs from most recent tasks
        collected_count = 0
        for created_at, task_id, task_data in tasks_list:
            if collected_count >= MAX_RECENT_TASKS:
                break
            
            task_logs = task_data.get("logs", [])
            if not task_logs:
                continue
            
            # Join log lines
            log_content = "\n".join(str(line) for line in task_logs)
            
            # Limit individual log size
            if len(log_content) > MAX_LOG_SIZE_PER_TASK:
                # Take last MAX_LOG_SIZE_PER_TASK bytes
                log_content = log_content[-MAX_LOG_SIZE_PER_TASK:]
                log_content = "... (truncated)\n" + log_content
            
            # Check total size limit
            if total_size + len(log_content) > MAX_TOTAL_LOG_SIZE:
                break
            
            # Store log with task ID in filename
            log_filename = f"task_{task_id[:8]}_logs.txt"
            logs[log_filename] = log_content
            total_size += len(log_content)
            collected_count += 1
    
    except Exception as e:
        # If we can't load logs, include error message
        logs["log_collection_error.txt"] = f"Failed to collect logs: {str(e)}"
    
    return logs


def get_last_n_lines(text: str, n: int) -> str:
    """
    Get the last N lines from text.
    
    Args:
        text: Input text
        n: Number of lines to retrieve
        
    Returns:
        Last N lines joined as a string
    """
    lines = text.splitlines()
    if len(lines) <= n:
        return text
    return "\n".join(lines[-n:])
