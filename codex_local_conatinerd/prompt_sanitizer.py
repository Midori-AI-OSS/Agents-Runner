_PROMPT_REPLACEMENTS = {
    '"': "`",
    "“": "`",
    "”": "`",
    "„": "`",
    "‟": "`",
}


def sanitize_prompt(prompt: str) -> str:
    return "".join(_PROMPT_REPLACEMENTS.get(ch, ch) for ch in (prompt or ""))
