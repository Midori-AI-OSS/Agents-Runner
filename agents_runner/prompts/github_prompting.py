from __future__ import annotations

import re


_AGENTS_NOVA_MENTION_RE = re.compile(r"(?i)@agentsnova\b")


def has_agentsnova_mention(text: str) -> bool:
    return bool(_AGENTS_NOVA_MENTION_RE.search(str(text or "")))


def strip_agentsnova_mention(text: str) -> str:
    cleaned = _AGENTS_NOVA_MENTION_RE.sub("", str(text or ""))
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def escape_prompt_braces(text: str) -> str:
    return str(text or "").replace("{", "{{").replace("}", "}}")


def build_default_request_line(
    *,
    item_type: str,
    repo_owner: str,
    repo_name: str,
    number: int,
) -> str:
    normalized = str(item_type or "").strip().lower()
    if normalized == "pr":
        return (
            "Review GitHub pull request "
            f"#{int(number)} for repository {repo_owner}/{repo_name}."
        )
    return (
        "Fix GitHub issue "
        f"#{int(number)} for repository {repo_owner}/{repo_name}."
    )


def build_primary_request(*, mention_text: str, fallback: str) -> str:
    cleaned = strip_agentsnova_mention(mention_text)
    if cleaned:
        return f"User request (from GitHub):\n{escape_prompt_braces(cleaned)}"
    return escape_prompt_braces(fallback)
