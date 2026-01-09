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
