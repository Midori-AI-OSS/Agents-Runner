"""Task state collector for diagnostics bundles."""

import json
from typing import Any

from agents_runner.persistence import default_state_path
from agents_runner.persistence import load_state


def collect_task_state() -> dict[str, Any]:
    """
    Collect information about tasks for diagnostics.
    
    Gathers:
    - List of all known tasks with basic information
    - Detailed information about the most recent task
    
    Returns:
        Dictionary containing task state information
    """
    result: dict[str, Any] = {
        "tasks": [],
        "most_recent": None,
    }
    
    try:
        state_path = default_state_path()
        state = load_state(state_path)
        tasks_data = state.get("tasks", {})
        
        if not tasks_data:
            return result
        
        # Sort tasks by creation time
        tasks_list = []
        for task_id, task_data in tasks_data.items():
            if isinstance(task_data, dict):
                created_at = task_data.get("created_at_s", 0)
                tasks_list.append((created_at, task_id, task_data))
        
        tasks_list.sort(reverse=True)
        
        # Collect basic info for all tasks
        for created_at, task_id, task_data in tasks_list:
            task_info = {
                "task_id": task_id,
                "status": task_data.get("status", "unknown"),
                "agent": task_data.get("agent_cli", ""),
                "created_at_s": created_at,
                "exit_code": task_data.get("exit_code"),
                "has_error": bool(task_data.get("error")),
            }
            
            # Add timestamps if available
            if task_data.get("started_at"):
                task_info["started_at"] = task_data["started_at"]
            if task_data.get("finished_at"):
                task_info["finished_at"] = task_data["finished_at"]
            
            result["tasks"].append(task_info)
        
        # Add detailed info for most recent task
        if tasks_list:
            _, most_recent_id, most_recent_data = tasks_list[0]
            
            result["most_recent"] = {
                "task_id": most_recent_id,
                "status": most_recent_data.get("status", "unknown"),
                "agent": most_recent_data.get("agent_cli", ""),
                "agent_instance_id": most_recent_data.get("agent_instance_id", ""),
                "exit_code": most_recent_data.get("exit_code"),
                "error": most_recent_data.get("error"),
                "container_id": most_recent_data.get("container_id", ""),
                "created_at_s": most_recent_data.get("created_at_s", 0),
                "started_at": most_recent_data.get("started_at"),
                "finished_at": most_recent_data.get("finished_at"),
                "environment_id": most_recent_data.get("environment_id", ""),
                "attempt_count": len(most_recent_data.get("attempt_history", [])),
            }
            
            # Include attempt history summary
            attempt_history = most_recent_data.get("attempt_history", [])
            if attempt_history:
                result["most_recent"]["attempts"] = [
                    {
                        "exit_code": attempt.get("exit_code"),
                        "error": attempt.get("error"),
                        "agent": attempt.get("agent_cli", ""),
                    }
                    for attempt in attempt_history
                ]
    
    except Exception as e:
        result["error"] = f"Failed to collect task state: {str(e)}"
    
    return result


def format_task_state(task_state: dict[str, Any]) -> str:
    """
    Format task state as a readable string.
    
    Args:
        task_state: Task state dictionary from collect_task_state()
        
    Returns:
        Formatted string representation
    """
    return json.dumps(task_state, indent=2, default=str)
