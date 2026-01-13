import json
import os

from dataclasses import dataclass

from agents_runner.prompts import load_prompt


GITHUB_CONTEXT_VERSION = 2


@dataclass(frozen=True, slots=True)
class PrMetadata:
    title: str | None = None
    body: str | None = None


@dataclass
class GitHubContext:
    """GitHub repository context for v2 schema.
    
    Contains repository metadata to help agents understand the codebase context.
    """
    repo_url: str
    repo_owner: str | None
    repo_name: str | None
    base_branch: str
    task_branch: str | None
    head_commit: str


@dataclass
class GitHubMetadataV2:
    """Version 2 metadata with GitHub context.
    
    Extends v1 (title/body only) with repository context.
    """
    version: int = GITHUB_CONTEXT_VERSION
    task_id: str = ""
    github: GitHubContext | None = None
    title: str = ""
    body: str = ""


def github_context_container_path(task_id: str) -> str:
    """V2 container path with new naming."""
    task_token = _safe_task_token(task_id)
    return f"/tmp/github-context-{task_token}.json"


def github_context_host_path(data_dir: str, task_id: str) -> str:
    """V2 host path with new naming."""
    task_token = _safe_task_token(task_id)
    root = os.path.abspath(os.path.expanduser(str(data_dir or "").strip() or "."))
    return os.path.join(root, "github-context", f"github-context-{task_token}.json")


def ensure_github_context_file(
    path: str,
    *,
    task_id: str,
    github_context: GitHubContext | None = None,
) -> None:
    """Create v2 metadata file with optional GitHub context.
    
    Args:
        path: Host file path where metadata will be created
        task_id: Unique task identifier
        github_context: Optional GitHub context to include. If None, creates
            file with empty github object that can be populated later.
    """
    path = os.path.abspath(os.path.expanduser(str(path or "").strip()))
    if not path:
        raise ValueError("missing GitHub context path")
    
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    # Build payload
    payload: dict = {
        "version": GITHUB_CONTEXT_VERSION,
        "task_id": str(task_id or ""),
        "title": "",
        "body": "",
    }
    
    # Add github object if provided
    if github_context:
        payload["github"] = {
            "repo_url": github_context.repo_url,
            "repo_owner": github_context.repo_owner,
            "repo_name": github_context.repo_name,
            "base_branch": github_context.base_branch,
            "task_branch": github_context.task_branch,
            "head_commit": github_context.head_commit,
        }
    else:
        payload["github"] = None
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    
    # Fix 1.3: Use container-compatible permissions
    # 0o666 allows container user (different UID) to write during Phase 2 update
    # Safe: file contains only non-sensitive repo metadata (URLs, branches, commit SHAs)
    try:
        os.chmod(path, 0o666)
    except OSError:
        pass


def update_github_context_after_clone(
    path: str,
    *,
    github_context: GitHubContext,
) -> None:
    """Update existing v2 metadata file with GitHub context after clone.
    
    Used for cloned repo environments where the file is created before clone
    but needs to be populated with repo context after clone completes.
    
    Args:
        path: Host file path of existing metadata file
        github_context: GitHub context to add to file
    """
    path = os.path.abspath(os.path.expanduser(str(path or "").strip()))
    if not path or not os.path.exists(path):
        raise ValueError(f"GitHub context file does not exist: {path}")
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as exc:
        raise ValueError(f"Failed to read GitHub context file: {exc}") from exc
    
    if not isinstance(payload, dict):
        raise ValueError("Invalid GitHub context file format")
    
    # Update github object
    payload["github"] = {
        "repo_url": github_context.repo_url,
        "repo_owner": github_context.repo_owner,
        "repo_name": github_context.repo_name,
        "base_branch": github_context.base_branch,
        "task_branch": github_context.task_branch,
        "head_commit": github_context.head_commit,
    }
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def load_pr_metadata(path: str) -> PrMetadata:
    """Load PR metadata from v1 or v2 file.
    
    Supports both old (v1) and new (v2) formats. Only extracts title/body.
    """
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


def load_github_metadata(path: str) -> GitHubMetadataV2 | None:
    """Load v2 metadata file with GitHub context.
    
    Returns None if file doesn't exist or is invalid.
    """
    path = os.path.abspath(os.path.expanduser(str(path or "").strip()))
    if not path or not os.path.exists(path):
        return None
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return None
    
    if not isinstance(payload, dict):
        return None
    
    version = payload.get("version", 1)
    if version != GITHUB_CONTEXT_VERSION:
        return None
    
    task_id = str(payload.get("task_id", ""))
    title = str(payload.get("title", ""))
    body = str(payload.get("body", ""))
    
    # Parse github object
    github_data = payload.get("github")
    github_context = None
    if isinstance(github_data, dict):
        github_context = GitHubContext(
            repo_url=str(github_data.get("repo_url", "")),
            repo_owner=github_data.get("repo_owner"),
            repo_name=github_data.get("repo_name"),
            base_branch=str(github_data.get("base_branch", "")),
            task_branch=github_data.get("task_branch"),
            head_commit=str(github_data.get("head_commit", "")),
        )
    
    return GitHubMetadataV2(
        version=version,
        task_id=task_id,
        github=github_context,
        title=title,
        body=body,
    )


def normalize_pr_title(title: str, *, fallback: str) -> str:
    candidate = (title or "").strip().splitlines()[0] if title else ""
    if not candidate:
        candidate = (fallback or "").strip()
    if len(candidate) > 72:
        candidate = candidate[:69].rstrip() + "..."
    return candidate


def github_context_prompt_instructions(container_path: str) -> str:
    """Generate v2 prompt instructions with GitHub context."""
    container_path = str(container_path or "").strip()
    if not container_path:
        container_path = "/tmp/github-context.json"
    return load_prompt(
        "github_context",
        GITHUB_CONTEXT_FILE=container_path,
    )


def _safe_task_token(task_id: str) -> str:
    raw = str(task_id or "").strip()
    safe = "".join(ch for ch in raw if ch.isalnum() or ch in {"-", "_"})
    return safe or "task"
