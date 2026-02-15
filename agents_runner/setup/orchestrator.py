"""Sequential setup orchestration for agent authentication.

This module handles the first-run setup flow, including:
- Sequential terminal launch with delays
- Progress tracking
- Cancellation handling
- Setup state persistence
"""

import asyncio
import json
import os
import subprocess
import tempfile

from datetime import datetime
from typing import Any, Callable

from agents_runner.setup.commands import get_setup_command
from agents_runner.terminal_apps import (
    detect_terminal_options,
    TerminalOption,
    linux_terminal_args,
)


SETUP_STATE_PATH = os.path.expanduser("~/.midoriai/agents-runner/setup_state.json")


def setup_state_path() -> str:
    """Get the path to the setup state file.

    Returns:
        Full path to setup_state.json
    """
    return SETUP_STATE_PATH


def check_setup_complete() -> bool:
    """Check if first-run setup has been completed.

    Returns:
        True if first-run setup is complete, False otherwise
    """
    path = setup_state_path()
    if not os.path.exists(path):
        return False

    try:
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
        return state.get("first_run_complete", False)
    except (json.JSONDecodeError, OSError):
        return False


def load_setup_state() -> dict[str, Any]:
    """Load setup state from file.

    Returns:
        Setup state dictionary
    """
    path = setup_state_path()
    if not os.path.exists(path):
        return {
            "version": 1,
            "first_run_complete": False,
            "setup_date": None,
            "setup_cancelled": False,
            "agents_setup": {},
            "agents_enabled": {},
            "last_status_check": None,
            "setup_delay_seconds": 2.0,
        }

    try:
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
        # Ensure all required keys exist
        state.setdefault("version", 1)
        state.setdefault("first_run_complete", False)
        state.setdefault("setup_date", None)
        state.setdefault("setup_cancelled", False)
        state.setdefault("agents_setup", {})
        state.setdefault("agents_enabled", {})
        state.setdefault("last_status_check", None)
        state.setdefault("setup_delay_seconds", 2.0)
        return state
    except (json.JSONDecodeError, OSError):
        return {
            "version": 1,
            "first_run_complete": False,
            "setup_date": None,
            "setup_cancelled": False,
            "agents_setup": {},
            "agents_enabled": {},
            "last_status_check": None,
            "setup_delay_seconds": 2.0,
        }


def save_setup_state(state: dict[str, Any]) -> None:
    """Save setup state to file atomically.

    Args:
        state: Setup state dictionary to save
    """
    path = setup_state_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)

    # Write to temporary file first
    fd, tmp_path = tempfile.mkstemp(
        prefix="setup-state-", suffix=".json", dir=os.path.dirname(path)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        # Atomic replace
        os.replace(tmp_path, path)
    except Exception:
        # Clean up temp file on error
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def mark_setup_complete(
    agents_setup: dict[str, bool],
    agents_enabled: dict[str, bool],
    cancelled: bool = False,
) -> None:
    """Mark first-run setup as complete and save setup state.

    Args:
        agents_setup: Dict mapping agent name to setup success status
        agents_enabled: Dict mapping agent name to whether user enabled it
        cancelled: Whether setup was cancelled mid-flow
    """
    state = load_setup_state()
    state["first_run_complete"] = True
    state["setup_date"] = datetime.now().isoformat()
    state["setup_cancelled"] = cancelled
    state["agents_setup"] = agents_setup
    state["agents_enabled"] = agents_enabled
    state["last_status_check"] = datetime.now().isoformat()
    save_setup_state(state)


def mark_setup_skipped() -> None:
    """Mark first-run setup as skipped (user clicked Skip button).

    This prevents the first-run dialog from appearing again.
    """
    state = load_setup_state()
    state["first_run_complete"] = True
    state["setup_date"] = datetime.now().isoformat()
    state["setup_cancelled"] = False
    save_setup_state(state)


def launch_terminal_and_wait(
    option: TerminalOption, bash_script: str, cwd: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Launch terminal and WAIT for it to close (blocking).

    This is used for sequential setup where we need to wait
    for one terminal to close before opening the next.

    Args:
        option: Terminal option to use
        bash_script: Shell command to run in terminal
        cwd: Working directory for the command

    Returns:
        CompletedProcess with returncode
    """
    cwd = os.path.abspath(os.path.expanduser(cwd)) if cwd else None

    if option.kind == "linux-exe":
        args = linux_terminal_args(
            option.terminal_id, option.exe or option.terminal_id, bash_script, cwd=cwd
        )
        return subprocess.run(args, start_new_session=True)

    if option.kind in {"mac-terminal", "mac-iterm"}:
        # For macOS, we need to use osascript which returns immediately
        # This is a limitation - we can't easily wait for Terminal.app to close
        # For now, just launch it and return
        # TODO: Research better macOS terminal waiting mechanism
        raise NotImplementedError("Blocking terminal launch not yet supported on macOS")

    raise RuntimeError(f"Unsupported terminal kind: {option.kind}")


def launch_agent_setup_terminal(agent: str, terminal: TerminalOption) -> bool:
    """Launch terminal for agent setup and wait for completion.

    Args:
        agent: Agent name to set up
        terminal: Terminal option to use

    Returns:
        True if terminal exited successfully (exit code 0), False otherwise
    """
    command = get_setup_command(agent)
    if not command:
        return False

    try:
        result = launch_terminal_and_wait(terminal, command, cwd=None)
        return result.returncode == 0
    except Exception:
        return False


class SetupOrchestrator:
    """Orchestrates sequential agent setup with delays."""

    def __init__(self, delay_seconds: float = 2.0):
        """Initialize orchestrator.

        Args:
            delay_seconds: Delay between agent setups (default 2 seconds)
        """
        self.delay_seconds = delay_seconds
        self._cancelled = False

    def cancel(self) -> None:
        """Cancel the setup process."""
        self._cancelled = True

    async def run_sequential_setup(
        self,
        agents: list[str],
        progress_callback: Callable[[str, int, int, str], None] | None = None,
    ) -> dict[str, bool]:
        """Run setup for multiple agents sequentially.

        Args:
            agents: List of agent names to set up
            progress_callback: Called with (agent, current, total, status_message)

        Returns:
            Dict mapping agent name to success status
        """
        results: dict[str, bool] = {}
        total = len(agents)

        # Detect terminal
        terminal_options = detect_terminal_options()
        if not terminal_options:
            # No terminal available
            return {agent: False for agent in agents}

        terminal = terminal_options[0]

        for idx, agent in enumerate(agents):
            if self._cancelled:
                # Mark remaining agents as not set up
                for remaining_agent in agents[idx:]:
                    results[remaining_agent] = False
                break

            current = idx + 1

            # Update progress: launching
            if progress_callback:
                progress_callback(agent, current, total, f"Launching {agent} setup...")

            # Launch terminal and wait (blocking)
            # We need to run this in a thread to keep UI responsive
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None, launch_agent_setup_terminal, agent, terminal
            )
            results[agent] = success

            # Update progress: complete
            if progress_callback:
                status = "Setup complete" if success else "Setup failed"
                progress_callback(agent, current, total, status)

            # Delay before next agent (except after last one)
            if current < total and not self._cancelled:
                next_agent = agents[idx + 1]
                # Countdown delay
                for remaining in range(int(self.delay_seconds), 0, -1):
                    if self._cancelled:
                        break
                    if progress_callback:
                        progress_callback(
                            next_agent,
                            current,
                            total,
                            f"Starting in {remaining} seconds...",
                        )
                    await asyncio.sleep(1.0)

        return results
