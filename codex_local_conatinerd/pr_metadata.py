import json
import os

from dataclasses import dataclass


PR_METADATA_VERSION = 1


@dataclass(frozen=True, slots=True)
class PrMetadata:
    title: str | None = None
    body: str | None = None


def pr_metadata_container_path(task_id: str) -> str:
    task_token = _safe_task_token(task_id)
    return f"/tmp/codex-pr-metadata-{task_token}.json"


def pr_metadata_host_path(data_dir: str, task_id: str) -> str:
    task_token = _safe_task_token(task_id)
    root = os.path.abspath(os.path.expanduser(str(data_dir or "").strip() or "."))
    return os.path.join(root, "pr-metadata", f"pr-metadata-{task_token}.json")


def ensure_pr_metadata_file(path: str, *, task_id: str) -> None:
    path = os.path.abspath(os.path.expanduser(str(path or "").strip()))
    if not path:
        raise ValueError("missing PR metadata path")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {"version": PR_METADATA_VERSION, "task_id": str(task_id or ""), "title": "", "body": ""}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    try:
        os.chmod(path, 0o666)
    except OSError:
        pass


def load_pr_metadata(path: str) -> PrMetadata:
    path = os.path.abspath(os.path.expanduser(str(path or "").strip()))
    if not path or not os.path.exists(path):
        return PrMetadata()
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return PrMetadata()
    if not isinstance(payload, dict):
        return PrMetadata()

    title_raw = payload.get("title")
    body_raw = payload.get("body")
    if body_raw is None:
        body_raw = payload.get("description")

    title = str(title_raw).strip() if isinstance(title_raw, str) else ""
    body = str(body_raw).strip() if isinstance(body_raw, str) else ""
    return PrMetadata(title=title or None, body=body or None)


def normalize_pr_title(title: str, *, fallback: str) -> str:
    candidate = (title or "").strip().splitlines()[0] if title else ""
    if not candidate:
        candidate = (fallback or "").strip()
    if len(candidate) > 72:
        candidate = candidate[:69].rstrip() + "..."
    return candidate


def pr_metadata_prompt_instructions(container_path: str) -> str:
    container_path = str(container_path or "").strip()
    if not container_path:
        container_path = "/tmp/codex-pr-metadata.json"
    return (
        "\n\n"
        "PR METADATA (non-interactive only)\n"
        f"- A JSON file is mounted at: {container_path}\n"
        "- If you make changes intended for a PR, update that file with valid JSON containing:\n"
        '  - "title": short PR title (<= 72 chars)\n'
        '  - "body": PR description (markdown)\n'
        "- Keep it as strict JSON (no trailing commas).\n"
    )


def _safe_task_token(task_id: str) -> str:
    raw = str(task_id or "").strip()
    safe = "".join(ch for ch in raw if ch.isalnum() or ch in {"-", "_"})
    return safe or "task"

