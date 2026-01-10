"""Progressive background loader for past tasks.

Loads past tasks in small batches with yielding to maintain UI responsiveness.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject
from PySide6.QtCore import QTimer


class PastTaskProgressiveLoader:
    """Manages progressive background loading of past tasks.
    
    Loads tasks in the background with yielding to keep UI responsive.
    Initial burst of 10 tasks for fast paint, then 1 task at a time.
    """

    INITIAL_BATCH_SIZE = 10
    PROGRESSIVE_BATCH_SIZE = 1
    YIELD_TIME_MS = 100

    def __init__(
        self,
        load_callback: Callable[[int, int], int],
        indicator_callback: Callable[[bool], None],
        parent: QObject | None = None,
    ) -> None:
        """Initialize the progressive loader.

        Args:
            load_callback: Function(offset, limit) -> count_loaded.
                Should load tasks and return number successfully loaded.
            indicator_callback: Function(is_loading) -> None.
                Called to show/hide loading indicator.
            parent: Optional parent QObject for proper Qt lifecycle.
        
        Raises:
            TypeError: If callbacks are not callable.
        """
        if not callable(load_callback):
            raise TypeError("load_callback must be callable")
        if not callable(indicator_callback):
            raise TypeError("indicator_callback must be callable")
        
        self._load_callback = load_callback
        self._indicator_callback = indicator_callback

        self._timer = QTimer(parent)  # Parent the timer
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._load_next_batch)

        self._current_offset = 0
        self._has_more = True
        self._is_active = False

    def start(self, initial_batch_size: int | None = None) -> None:
        """Start progressive loading.
        
        Args:
            initial_batch_size: Size of initial burst load. Defaults to INITIAL_BATCH_SIZE.
        """
        if self._is_active:
            return

        self._current_offset = 0
        self._has_more = True
        self._is_active = True

        # Load initial batch immediately for fast paint
        batch_size = initial_batch_size or self.INITIAL_BATCH_SIZE
        try:
            loaded = self._load_callback(self._current_offset, batch_size)
            # Validate return value
            if not isinstance(loaded, int) or loaded < 0:
                loaded = 0
        except Exception:
            # Handle callback errors gracefully
            loaded = 0
            self._has_more = False
            self._is_active = False
            self._indicator_callback(False)
            return

        if loaded > 0:
            self._current_offset += loaded

        # Check if we have more to load
        if loaded < batch_size:
            self._has_more = False
            self._is_active = False
            self._indicator_callback(False)
            return

        # Schedule progressive loading
        self._indicator_callback(True)
        self._timer.start(self.YIELD_TIME_MS)

    def _load_next_batch(self) -> None:
        """Load next small batch in background."""
        if not self._is_active or not self._has_more:
            self._is_active = False
            self._indicator_callback(False)
            return

        try:
            loaded = self._load_callback(self._current_offset, self.PROGRESSIVE_BATCH_SIZE)
            # Validate return value
            if not isinstance(loaded, int) or loaded < 0:
                loaded = 0
        except Exception:
            # Handle callback errors - stop loading on error
            self._has_more = False
            self._is_active = False
            self._indicator_callback(False)
            return

        if loaded > 0:
            self._current_offset += loaded

        # Check if we reached the end
        if loaded < self.PROGRESSIVE_BATCH_SIZE:
            self._has_more = False
            self._is_active = False
            self._indicator_callback(False)
            return

        # Schedule next batch
        self._timer.start(self.YIELD_TIME_MS)

    def cancel(self) -> None:
        """Cancel background loading and hide indicator."""
        self._timer.stop()
        self._is_active = False
        self._indicator_callback(False)

    def is_active(self) -> bool:
        """Check if loader is currently active.
        
        Returns:
            True if loader is running.
        """
        return self._is_active

    def has_more(self) -> bool:
        """Check if more tasks might be available.
        
        Returns:
            True if not all tasks have been loaded yet.
        """
        return self._has_more
