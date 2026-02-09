from __future__ import annotations

"""Helpers for agent-system interactive command construction."""


def move_positional_to_end(parts: list[str], value: str) -> None:
    """Move a positional argument to the end of the command parts.

    Modifies `parts` in place.
    """
    value = str(value or "")
    if not value:
        return

    for idx in range(len(parts) - 1, 0, -1):
        if parts[idx] != value:
            continue
        prev = parts[idx - 1]
        if prev != "--" and prev.startswith("-"):
            continue
        parts.pop(idx)
        break

    parts.append(value)


def move_flag_value_to_end(parts: list[str], flags: set[str]) -> None:
    """Move a flag and its value to the end of the command parts.

    Modifies `parts` in place.
    """
    for idx in range(len(parts) - 2, -1, -1):
        if parts[idx] not in flags:
            continue
        flag = parts.pop(idx)
        value = parts.pop(idx)
        parts.extend([flag, value])
        return
