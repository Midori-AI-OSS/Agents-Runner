"""Token redaction utilities for secure logging.

This module provides functions to redact sensitive tokens from strings
before logging or displaying them to users.
"""

from __future__ import annotations

import re

# Patterns for various token types
_TOKEN_PATTERNS = [
    # GitHub Personal Access Tokens (classic and fine-grained)
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    # GitHub OAuth tokens
    re.compile(r"\bgho_[A-Za-z0-9]{20,}\b"),
    # GitHub User-to-Server tokens
    re.compile(r"\bghu_[A-Za-z0-9]{20,}\b"),
    # GitHub Refresh tokens
    re.compile(r"\bghr_[A-Za-z0-9]{20,}\b"),
    # GitHub Server-to-Server tokens  
    re.compile(r"\bghs_[A-Za-z0-9]{20,}\b"),
]

_REDACTED = "[REDACTED]"


def redact_tokens(text: str) -> str:
    """Redact sensitive tokens from a string.

    Args:
        text: The input string that may contain sensitive tokens.

    Returns:
        The string with all recognized tokens replaced with [REDACTED].
    """
    if not text:
        return text

    result = text
    for pattern in _TOKEN_PATTERNS:
        result = pattern.sub(_REDACTED, result)
    return result


def redact_exception(exc: BaseException) -> str:
    """Get a redacted string representation of an exception.

    Args:
        exc: The exception to redact.

    Returns:
        A redacted string representation of the exception.
    """
    return redact_tokens(str(exc))
