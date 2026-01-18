"""Task artifacts staging directory management."""

from __future__ import annotations

import os
import json
from pathlib import Path
from datetime import datetime
from datetime import timezone


def get_artifacts_staging_dir(task_id: str) -> Path:
    """Get the artifacts staging directory path for a task.
    
    Args:
        task_id: Task ID
    
    Returns:
        Path to staging directory
    """
    return (
        Path.home() / ".midoriai" / "agents-runner" / "artifacts" 
        / task_id / "staging"
    )


def ensure_artifacts_staging_dir(task_id: str) -> Path:
    """Ensure artifacts staging directory exists.
    
    Args:
        task_id: Task ID
    
    Returns:
        Path to staging directory
    """
    staging_dir = get_artifacts_staging_dir(task_id)
    staging_dir.mkdir(parents=True, exist_ok=True)
    return staging_dir


def read_interactive_completion_marker(task_id: str) -> dict[str, object] | None:
    """Read interactive task completion marker from staging directory.
    
    Args:
        task_id: Task ID
    
    Returns:
        Completion marker dict or None if not found or malformed
    """
    staging_dir = get_artifacts_staging_dir(task_id)
    marker_path = staging_dir / "interactive-exit.json"
    
    if not marker_path.exists():
        return None
    
    try:
        with open(marker_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception:
        # Malformed marker
        return None


def write_container_entrypoint_script(
    staging_dir: Path,
    task_id: str,
    agent_cli_cmd: str,
) -> Path:
    """Write container entrypoint script to staging directory.
    
    The entrypoint script:
    - Records start time
    - Launches the agent CLI
    - Writes completion marker on exit (via trap)
    
    Args:
        staging_dir: Staging directory path
        task_id: Task ID
        agent_cli_cmd: Full agent CLI command to execute
    
    Returns:
        Path to entrypoint script
    """
    script_path = staging_dir / ".container-entrypoint.sh"
    
    script_content = f'''#!/bin/bash
set -euo pipefail

# Trap EXIT to write completion marker
write_completion_marker() {{
    local exit_code=$?
    cat > /tmp/agents-artifacts/interactive-exit.json <<EOF
{{
  "task_id": "{task_id}",
  "container_name": "$(hostname)",
  "exit_code": ${{exit_code}},
  "started_at": "${{STARTED_AT}}",
  "finished_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "reason": "process_exit"
}}
EOF
    exit ${{exit_code}}
}}

trap write_completion_marker EXIT

# Record start time
STARTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Launch the agent CLI
exec {agent_cli_cmd}
'''
    
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_content)
    
    # Make executable
    os.chmod(script_path, 0o755)
    
    return script_path
