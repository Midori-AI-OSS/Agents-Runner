"""Retry logic for network operations during PR creation.

This module provides retry wrappers with exponential backoff for
operations that may fail due to transient network issues.
"""

from __future__ import annotations

import time
from typing import Callable
from typing import TypeVar

T = TypeVar("T")


def with_retry(
    operation: Callable[[], T],
    *,
    max_attempts: int = 3,
    retry_delay_s: float = 2.0,
    retry_on: tuple[type[Exception], ...] = (OSError, TimeoutError),
    operation_name: str = "operation",
) -> T:
    """Retry operation on transient failures.
    
    Args:
        operation: Function to retry (must be callable with no args)
        max_attempts: Maximum number of attempts (default: 3)
        retry_delay_s: Base delay between retries in seconds (default: 2.0)
        retry_on: Tuple of exception types to retry on
        operation_name: Name of operation for logging
        
    Returns:
        Result of successful operation
        
    Raises:
        Last exception if all retries exhausted
    """
    last_exc: Exception | None = None
    
    for attempt in range(1, max_attempts + 1):
        try:
            return operation()
        except retry_on as exc:
            last_exc = exc
            if attempt >= max_attempts:
                # All retries exhausted
                raise
            
            # Exponential backoff: 2s, 4s, 8s, ...
            delay = retry_delay_s * (2 ** (attempt - 1))
            time.sleep(delay)
            continue
        except Exception:
            # Non-retryable exception
            raise
    
    # This should never be reached, but satisfy type checker
    if last_exc:
        raise last_exc
    raise RuntimeError(f"{operation_name} failed without exception")
