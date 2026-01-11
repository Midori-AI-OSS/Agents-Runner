"""Path utilities for diagnostics system."""

import os
from pathlib import Path


def diagnostics_root_dir() -> str:
    """
    Get the root diagnostics directory path.
    
    Returns:
        Path to ~/.midoriai/agents-runner/diagnostics/
    """
    base = os.path.expanduser("~/.midoriai/agents-runner")
    diagnostics_dir = os.path.join(base, "diagnostics")
    os.makedirs(diagnostics_dir, exist_ok=True)
    return diagnostics_dir


def bundles_dir() -> str:
    """
    Get the diagnostics bundles directory path.
    
    Returns:
        Path to ~/.midoriai/agents-runner/diagnostics/bundles/
    """
    root = diagnostics_root_dir()
    bundles_path = os.path.join(root, "bundles")
    os.makedirs(bundles_path, exist_ok=True)
    return bundles_path


def crash_reports_dir() -> str:
    """
    Get the crash reports directory path.
    
    Returns:
        Path to ~/.midoriai/agents-runner/diagnostics/crash_reports/
    """
    root = diagnostics_root_dir()
    crash_path = os.path.join(root, "crash_reports")
    os.makedirs(crash_path, exist_ok=True)
    return crash_path
