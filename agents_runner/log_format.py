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


def format_log(scope: str, subscope: str, level: str, message: str) -> str:
    """Format a log message in canonical format.
    
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
    level = level.upper()
    if level not in ("DEBUG", "INFO", "WARN", "ERROR"):
        level = "INFO"
    return f"[{scope}/{subscope}][{level}] {message}"


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
    level = "INFO"  # Default level
    if stream == "stderr":
        level = "WARN"  # stderr defaults to WARN
    return f"[{cid4}/{stream}][{level}] {line}"


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
    return f"[{fallback_scope}/{fallback_subscope}][INFO] {line}"


def format_log_display(line: str, scope_width: int = 20, level_width: int = 5) -> str:
    """Format a log line for UI display with aligned columns.
    
    Args:
        line: Raw log line (canonical or legacy)
        scope_width: Width for scope/subscope column (default 20, max recommended 24)
        level_width: Width for level column (default 5)
    
    Returns:
        Formatted line with padded/truncated scope and level columns.
        For non-canonical lines, wraps them as [legacy/unknown][INFO] <original>
    
    Example output:
        [ gh/repo           ][INFO ] updated GitHub context file
        [ host/none         ][INFO ] pull complete
        [ desktop/setup     ][INFO ] cache enabled; checking for cached image
    """
    parsed = parse_canonical_log(line)
    
    if parsed is None:
        # Non-canonical line, wrap it first
        wrapped = wrap_legacy_log(line)
        parsed = parse_canonical_log(wrapped)
        if parsed is None:  # Should not happen, but handle gracefully
            return line
    
    scope, subscope, level, message = parsed
    
    # Format scope/subscope column
    scope_text = f"{scope}/{subscope}"
    
    # Truncate if too long (leave room for brackets and space: 2 chars for "[ " and 1 for "]")
    max_scope_len = scope_width - 2
    if len(scope_text) > max_scope_len:
        # Truncate with ellipsis
        scope_text = scope_text[:max_scope_len - 3] + "..."
    
    # Pad scope column (content width minus the brackets)
    scope_formatted = f"[ {scope_text:<{scope_width - 2}}]"
    
    # Format level column with padding
    level_formatted = f"[{level.upper():<{level_width}}]"
    
    return f"{scope_formatted}{level_formatted} {message}"


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
