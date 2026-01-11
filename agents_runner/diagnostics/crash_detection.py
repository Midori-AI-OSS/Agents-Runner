"""Crash detection utilities for startup notification."""

import os
from datetime import datetime

from agents_runner.diagnostics.paths import crash_reports_dir
from agents_runner.diagnostics.paths import diagnostics_root_dir


def get_last_notification_time() -> float:
    """
    Get the timestamp of the last crash notification shown.
    
    Returns:
        Timestamp in seconds since epoch, or 0 if never shown
    """
    marker_path = os.path.join(diagnostics_root_dir(), ".last_crash_notification")
    try:
        if os.path.exists(marker_path):
            with open(marker_path, "r", encoding="utf-8") as f:
                return float(f.read().strip())
    except Exception:
        pass
    return 0.0


def set_last_notification_time(timestamp: float) -> None:
    """
    Record the timestamp when crash notification was shown.
    
    Args:
        timestamp: Timestamp in seconds since epoch
    """
    marker_path = os.path.join(diagnostics_root_dir(), ".last_crash_notification")
    try:
        with open(marker_path, "w", encoding="utf-8") as f:
            f.write(str(timestamp))
    except Exception:
        pass


def get_recent_crash_reports() -> list[tuple[str, float]]:
    """
    Get list of recent crash reports that haven't been notified.
    
    Returns:
        List of (crash_file_path, timestamp) tuples
    """
    crash_dir = crash_reports_dir()
    last_notified = get_last_notification_time()
    
    crash_files: list[tuple[str, float]] = []
    
    try:
        if not os.path.exists(crash_dir):
            return crash_files
        
        for filename in os.listdir(crash_dir):
            if not filename.startswith("crash-"):
                continue
            
            filepath = os.path.join(crash_dir, filename)
            if not os.path.isfile(filepath):
                continue
            
            try:
                mtime = os.path.getmtime(filepath)
                if mtime > last_notified:
                    crash_files.append((filepath, mtime))
            except Exception:
                continue
        
        # Sort by timestamp (most recent first)
        crash_files.sort(key=lambda x: x[1], reverse=True)
    
    except Exception:
        pass
    
    return crash_files


def should_notify_crash() -> bool:
    """
    Check if there are new crash reports to notify about.
    
    Returns:
        True if there are unnotified crash reports
    """
    return len(get_recent_crash_reports()) > 0


def mark_crashes_notified() -> None:
    """Mark current crash reports as notified."""
    set_last_notification_time(datetime.now().timestamp())
