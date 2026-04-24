from __future__ import annotations


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    seconds = max(0.0, float(seconds))
    if seconds < 60:
        return f"{int(seconds)}s"
    minutes, rem = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m {int(rem)}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"
