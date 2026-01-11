"""Breadcrumb logging system for tracking application events."""

from collections import deque
from datetime import datetime
from typing import Deque


class BreadcrumbLogger:
    """
    A lightweight logging system that tracks recent application events.
    
    Uses a circular buffer to store recent events with timestamps,
    useful for debugging and crash reports.
    """
    
    def __init__(self, max_size: int = 100):
        """
        Initialize the breadcrumb logger.
        
        Args:
            max_size: Maximum number of breadcrumbs to keep in memory
        """
        self._crumbs: Deque[str] = deque(maxlen=max_size)
    
    def add(self, message: str) -> None:
        """
        Add a breadcrumb entry with timestamp.
        
        Args:
            message: Event description to log
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] {message}"
        self._crumbs.append(entry)
    
    def get_recent(self, count: int | None = None) -> list[str]:
        """
        Retrieve recent breadcrumb entries.
        
        Args:
            count: Maximum number of entries to return (None for all)
            
        Returns:
            List of formatted breadcrumb entries
        """
        if count is None:
            return list(self._crumbs)
        return list(self._crumbs)[-count:] if count > 0 else []
    
    def clear(self) -> None:
        """Clear all breadcrumb entries."""
        self._crumbs.clear()


# Global breadcrumb logger instance
_breadcrumb_logger = BreadcrumbLogger(max_size=100)


def add_breadcrumb(message: str) -> None:
    """
    Add a breadcrumb entry to the global logger.
    
    This is the primary API for adding breadcrumbs throughout the application.
    
    Args:
        message: Event description to log
    """
    _breadcrumb_logger.add(message)


def get_breadcrumbs(count: int | None = None) -> list[str]:
    """
    Get recent breadcrumb entries from the global logger.
    
    Args:
        count: Maximum number of entries to return (None for all)
        
    Returns:
        List of formatted breadcrumb entries
    """
    return _breadcrumb_logger.get_recent(count)


def clear_breadcrumbs() -> None:
    """Clear all breadcrumb entries from the global logger."""
    _breadcrumb_logger.clear()
