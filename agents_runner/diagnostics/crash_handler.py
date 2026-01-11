"""Crash report handler for capturing unhandled exceptions."""

import json
import os
import sys
import traceback
from datetime import datetime
from types import TracebackType
from typing import Any

from agents_runner.diagnostics.breadcrumbs import get_breadcrumbs
from agents_runner.diagnostics.paths import crash_reports_dir
from agents_runner.diagnostics.redaction import redact_secrets


def get_app_version() -> str:
    """
    Get the application version.
    
    Returns:
        Version string
    """
    try:
        import tomllib
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        pyproject_path = os.path.join(project_root, "pyproject.toml")
        
        if os.path.exists(pyproject_path):
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
                return data.get("project", {}).get("version", "unknown")
    except Exception:
        pass
    
    return "unknown"


def write_crash_report(
    exc_type: type[BaseException] | None,
    exc_value: BaseException | None,
    exc_traceback: TracebackType | None
) -> str:
    """
    Write a crash report to disk.
    
    Args:
        exc_type: Exception type
        exc_value: Exception instance
        exc_traceback: Traceback object
        
    Returns:
        Path to the created crash report file
    """
    try:
        # Create timestamp for filename
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        crash_filename = f"crash-{timestamp}.json"
        crash_path = os.path.join(crash_reports_dir(), crash_filename)
        
        # Format stack trace
        if exc_traceback:
            tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            stack_trace = "".join(tb_lines)
        else:
            stack_trace = "No traceback available"
        
        # Get exception details
        exc_type_name = exc_type.__name__ if exc_type else "UnknownException"
        exc_message = str(exc_value) if exc_value else "No message"
        
        # Collect breadcrumbs
        breadcrumbs = get_breadcrumbs()
        
        # Build crash report data
        crash_data: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "app_version": get_app_version(),
            "exception": {
                "type": exc_type_name,
                "message": exc_message,
                "traceback": stack_trace,
            },
            "breadcrumbs": breadcrumbs,
        }
        
        # Apply redaction to entire crash report
        crash_json = json.dumps(crash_data, indent=2)
        crash_json = redact_secrets(crash_json)
        
        # Write to file
        with open(crash_path, "w", encoding="utf-8") as f:
            f.write(crash_json)
        
        return crash_path
    
    except Exception as e:
        # If crash handler fails, try to write a minimal report
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
            fallback_path = os.path.join(
                crash_reports_dir(),
                f"crash-{timestamp}-fallback.txt"
            )
            with open(fallback_path, "w", encoding="utf-8") as f:
                f.write(f"Crash handler failed: {str(e)}\n")
                f.write(f"Original exception: {exc_type} - {exc_value}\n")
            return fallback_path
        except Exception:
            # If even that fails, just return empty string
            return ""


def crash_handler(
    exc_type: type[BaseException] | None,
    exc_value: BaseException | None,
    exc_traceback: TracebackType | None
) -> None:
    """
    Global exception handler for unhandled exceptions.
    
    This should be installed with sys.excepthook.
    
    Args:
        exc_type: Exception type
        exc_value: Exception instance
        exc_traceback: Traceback object
    """
    # Write crash report
    crash_path = write_crash_report(exc_type, exc_value, exc_traceback)
    
    # Print to stderr for debugging
    if crash_path:
        print(f"\nCrash report written to: {crash_path}", file=sys.stderr)
    
    # Call original exception handler to ensure normal crash behavior
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def install_crash_handler() -> None:
    """
    Install the global crash handler.
    
    This replaces sys.excepthook with our crash handler that writes
    crash reports to disk before propagating the exception.
    """
    sys.excepthook = crash_handler
