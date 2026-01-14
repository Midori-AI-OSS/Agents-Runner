import re

from datetime import datetime


_ANSI_ESCAPE_RE = re.compile(
    r"""
    \x1B  # ESC
    (?:
        \[ [0-?]* [ -/]* [@-~]   # CSI ... cmd
      | \] .*? (?:\x07|\x1B\\)   # OSC ... BEL or ST
      | .                       # single-char escape
    )
    """,
    re.VERBOSE,
)

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")

_DOCKER_LOG_PREFIX_RE = re.compile(
    r"^(?P<ts>\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)?)\s+(?P<msg>.*)$"
)


def parse_docker_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    tz_index = max(text.rfind("+"), text.rfind("-"))
    if tz_index > 10:
        main, tz = text[:tz_index], text[tz_index:]
    else:
        main, tz = text, ""

    if "." in main:
        prefix, frac = main.split(".", 1)
        frac_digits = "".join(ch for ch in frac if ch.isdigit())
        frac_digits = (frac_digits[:6]).ljust(6, "0") if frac_digits else "000000"
        main = f"{prefix}.{frac_digits}"

    try:
        return datetime.fromisoformat(main + tz)
    except ValueError:
        return None


_CANONICAL_LOG_RE = re.compile(r"^\[[^/\]]+/[^\]]+\]\[[A-Z]+\]\s")
_NESTED_HEADER_RE = re.compile(r"^\[[^\]]+\]\[[A-Z]+\]\s?")


def format_log_line(
    scope: str,
    subscope: str = "none",
    level: str = "INFO",
    message: str = "",
    *,
    padded: bool = False,
    scope_width: int = 20,
    level_width: int = 5,
) -> str:
    """Central log line formatter - single source of truth.
    
    This function provides a unified interface for creating log lines in both
    raw canonical format and padded display format. It removes all padding/spaces
    inside brackets, ensures exactly one space between header and message, strips
    nested/duplicated headers, and skips empty messages after stripping.
    
    Args:
        scope: Host logs use ids like host, ui, gh, docker, desktop, artifacts, env, supervisor, cleanup, mcp.
               Container-origin logs use first 4 chars of container id (cid4), e.g. 6e9f.
        subscope: Short module/phase name, or "none" if none applies (default: "none").
        level: One of DEBUG, INFO, WARN, ERROR (default: "INFO").
        message: The log message content.
        padded: If True, return aligned format for UI display (default: False).
        scope_width: Max length for scope (truncates if longer, no padding) (default: 20).
        level_width: Unused, kept for compatibility (default: 5).
    
    Returns:
        Formatted log line with no internal padding:
        - Raw (padded=False): [{scope}/{subscope}][{LEVEL}] {message}
        - Padded (padded=True): [{scope}/{subscope}][{LEVEL}] {message}
        
        Returns empty string if message is empty after nested header stripping.
    
    Examples:
        >>> format_log_line("host", "test", "INFO", "hello")
        '[host/test][INFO] hello'
        
        >>> format_log_line("host", "test", "INFO", "hello", padded=True)
        '[host/test][INFO] hello'
        
        >>> format_log_line("host", "test", "INFO", "[nested/header][INFO] real message")
        '[host/test][INFO] real message'
        
        >>> format_log_line("host", "test", "INFO", "  leading spaces preserved")
        '[host/test][INFO]   leading spaces preserved'
    """
    # Normalize level to uppercase without trailing spaces
    level = level.upper().strip()
    if level not in ("DEBUG", "INFO", "WARN", "ERROR"):
        level = "INFO"
    
    # Strip nested/duplicated headers matching /^\[[^\]]+\]\[[A-Z]+\]\s*/
    # Keep stripping until no more nested headers are found
    while True:
        match = _NESTED_HEADER_RE.match(message)
        if not match:
            break
        message = message[match.end():]
    
    # Skip empty messages after stripping (but allow whitespace-only messages)
    if not message:
        return ""
    
    if not padded:
        # Raw canonical format - no padding/spaces inside brackets
        # Ensures exactly ONE space between header and message
        return f"[{scope}/{subscope}][{level}] {message}"
    
    # Padded display format for UI
    scope_text = f"{scope}/{subscope}"
    
    # Truncate if too long (no padding, but still enforce max length)
    if len(scope_text) > scope_width:
        # Truncate with ellipsis
        scope_text = scope_text[:scope_width - 3] + "..."
    
    # No padding - use compact format
    scope_formatted = f"[{scope_text}]"
    
    # No padding - use compact format
    level_formatted = f"[{level}]"
    
    return f"{scope_formatted}{level_formatted} {message}"


def format_log(scope: str, subscope: str, level: str, message: str) -> str:
    """Format a log message in canonical format.
    
    This is a compatibility wrapper around format_log_line(). Use format_log_line()
    directly for new code.
    
    Canonical format: [{scope}/{subscope}][{LEVEL}] {message}
    
    Args:
        scope: Host logs use ids like host, ui, gh, docker, desktop, artifacts, env, supervisor, cleanup, mcp.
               Container-origin logs use first 4 chars of container id (cid4), e.g. 6e9f.
        subscope: Short module/phase name, or "none" if none applies.
        level: One of DEBUG, INFO, WARN, ERROR (default INFO).
        message: The log message content.
    
    Returns:
        Formatted log string in canonical format.
    """
    return format_log_line(scope, subscope, level, message, padded=False)


def wrap_container_log(cid: str, stream: str, line: str) -> str:
    """Wrap container output in canonical format.
    
    Args:
        cid: Container ID (will use first 4 chars as scope).
        stream: Output stream identifier (e.g., 'stdout' or 'stderr').
        line: The log line to wrap.
    
    Returns:
        Line unchanged if it already has canonical format, otherwise wrapped.
    """
    # If already in canonical format, return unchanged
    if _CANONICAL_LOG_RE.match(line):
        return line
    
    cid4 = cid[:4] if len(cid) >= 4 else cid
    level = "WARN" if stream == "stderr" else "INFO"
    return format_log_line(cid4, stream, level, line, padded=False)


def parse_canonical_log(line: str) -> tuple[str, str, str, str] | None:
    """Parse a canonical log line and return (scope, subscope, level, message).
    
    Returns None if the line doesn't match canonical format.
    """
    # Match pattern: [scope/subscope][LEVEL] message
    pattern = r"^\[([^/\]]+)/([^\]]+)\]\[([A-Z]+)\]\s(.*)$"
    match = re.match(pattern, line)
    if not match:
        return None
    
    scope, subscope, level, message = match.groups()
    return (scope, subscope, level, message)


def wrap_legacy_log(line: str, fallback_scope: str = "legacy", fallback_subscope: str = "unknown") -> str:
    """Wrap a non-canonical log line in canonical format.
    
    Returns:
        Wrapped line: [fallback_scope/fallback_subscope][INFO] <original>
    """
    return format_log_line(fallback_scope, fallback_subscope, "INFO", line, padded=False)


def format_log_display(line: str, scope_width: int = 20, level_width: int = 5) -> str:
    """Format a log line for UI display with compact format.
    
    Args:
        line: Raw log line (canonical or legacy)
        scope_width: Max length for scope/subscope (truncates if longer, no padding) (default 20)
        level_width: Unused, kept for compatibility (default 5)
    
    Returns:
        Formatted line with compact brackets and no internal padding.
        For non-canonical lines, wraps them as [legacy/unknown][INFO] <original>
    
    Example output:
        [gh/repo][INFO] updated GitHub context file
        [host/none][INFO] pull complete
        [desktop/setup][INFO] cache enabled; checking for cached image
    """
    parsed = parse_canonical_log(line)
    
    if parsed is None:
        # Non-canonical line, wrap it first
        wrapped = wrap_legacy_log(line)
        parsed = parse_canonical_log(wrapped)
        if parsed is None:  # Should not happen, but handle gracefully
            return line
    
    scope, subscope, level, message = parsed
    
    # Use format_log_line with padded=True
    return format_log_line(scope, subscope, level, message, padded=True, 
                          scope_width=scope_width, level_width=level_width)


def prettify_log_line(line: str) -> str:
    text = (line or "").replace("\r", "")
    text = _ANSI_ESCAPE_RE.sub("", text)
    text = _CONTROL_CHARS_RE.sub("", text)

    match = _DOCKER_LOG_PREFIX_RE.match(text)
    if match:
        msg = match.group("msg")
        text = msg

    text = re.sub(r"^\[\d{2}:\d{2}:\d{2}\]\s+", "", text)
    return text.rstrip()
