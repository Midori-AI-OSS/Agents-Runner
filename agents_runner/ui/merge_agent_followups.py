from __future__ import annotations

from typing import Any


MERGE_AGENT_FOLLOWUPS_SETTINGS_KEY = "merge_agent_followups"
MERGE_AGENT_FOLLOWUP_VERSION = 1


def followup_key_for_pr(
    *,
    pull_request_url: str,
    repo_url: str,
    pull_request_number: int,
) -> str:
    pr_url = str(pull_request_url or "").strip()
    if pr_url:
        return pr_url
    repo = str(repo_url or "").strip()
    if repo:
        return f"{repo.rstrip('/')}/pull/{int(pull_request_number)}"
    return f"pull_request:{int(pull_request_number)}"


def ensure_followups_list(settings_data: dict[str, object]) -> list[dict[str, Any]]:
    raw = settings_data.get(MERGE_AGENT_FOLLOWUPS_SETTINGS_KEY)
    if isinstance(raw, list):
        cleaned: list[dict[str, Any]] = []
        for item in raw:
            if isinstance(item, dict):
                cleaned.append(dict(item))
        settings_data[MERGE_AGENT_FOLLOWUPS_SETTINGS_KEY] = cleaned
        return cleaned
    settings_data[MERGE_AGENT_FOLLOWUPS_SETTINGS_KEY] = []
    return []

