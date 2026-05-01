from __future__ import annotations

from collections.abc import Iterable

from agents_runner.log_format import format_log
from agents_runner.log_format import parse_canonical_log


MAX_LOG_MESSAGE_CHARS = 1800


def normalize_log_stream_chunk(
    chunk: str,
    *,
    max_message_chars: int = MAX_LOG_MESSAGE_CHARS,
) -> list[str]:
    """Normalize a raw log chunk into safe, ordered line events.

    Rules:
    - Treat carriage-return progress updates as line boundaries.
    - Preserve canonical headers while splitting CR-heavy lines.
    - Hard-wrap oversized lines to keep UI rendering responsive.
    """
    text = str(chunk or "")
    if not text:
        return []

    max_chars = max(120, int(max_message_chars))
    normalized: list[str] = []
    active_header: tuple[str, str, str] | None = None

    for fragment, delimiter in _iter_log_fragments(text):
        if fragment:
            parsed = parse_canonical_log(fragment)
            if parsed is not None:
                scope, subscope, level, message = parsed
                active_header = (scope, subscope, level)
                normalized.extend(
                    _format_canonical_chunks(
                        scope=scope,
                        subscope=subscope,
                        level=level,
                        message=message,
                        max_chars=max_chars,
                    )
                )
            elif active_header is not None:
                scope, subscope, level = active_header
                normalized.extend(
                    _format_canonical_chunks(
                        scope=scope,
                        subscope=subscope,
                        level=level,
                        message=fragment,
                        max_chars=max_chars,
                    )
                )
            else:
                normalized.extend(_split_chunks(fragment, max_chars=max_chars))

        # Preserve header context across '\r' progress updates, but not across new lines.
        if "\n" in delimiter:
            active_header = None

    return normalized


def _format_canonical_chunks(
    *,
    scope: str,
    subscope: str,
    level: str,
    message: str,
    max_chars: int,
) -> Iterable[str]:
    for part in _split_chunks(message, max_chars=max_chars):
        wrapped = format_log(scope, subscope, level, part)
        if wrapped:
            yield wrapped


def _split_chunks(text: str, *, max_chars: int) -> Iterable[str]:
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]


def _iter_log_fragments(text: str) -> Iterable[tuple[str, str]]:
    buffer: list[str] = []
    index = 0
    size = len(text)
    while index < size:
        char = text[index]
        if char == "\r":
            delimiter = "\r"
            if index + 1 < size and text[index + 1] == "\n":
                delimiter = "\r\n"
                index += 1
            yield ("".join(buffer), delimiter)
            buffer = []
        elif char == "\n":
            yield ("".join(buffer), "\n")
            buffer = []
        else:
            buffer.append(char)
        index += 1
    yield ("".join(buffer), "")
