import re
import secrets
import hashlib
import subprocess
import time

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime

from agents_runner.agent_display import format_agent_markdown_link
from agents_runner.agent_display import get_agent_github_url
from agents_runner.environments.model import GH_BRANCH_WORK_MODE_DIRECT_BASE
from agents_runner.environments.model import GH_BRANCH_WORK_MODE_TASK_BRANCH
from agents_runner.environments.model import GH_TASK_BRANCH_CUSTOM_TEMPLATE_DEFAULT
from agents_runner.environments.model import GH_TASK_BRANCH_NAMING_STYLE_ANIMALS
from agents_runner.environments.model import GH_TASK_BRANCH_NAMING_STYLE_COLORS
from agents_runner.environments.model import GH_TASK_BRANCH_NAMING_STYLE_CUSTOM
from agents_runner.environments.model import GH_TASK_BRANCH_NAMING_STYLE_FOODS
from agents_runner.environments.model import GH_TASK_BRANCH_NAMING_STYLE_SONGS
from agents_runner.environments.model import GH_TASK_BRANCH_NAMING_STYLE_SPACE
from agents_runner.environments.model import GH_TASK_BRANCH_NAMING_STYLE_STANDARD
from agents_runner.environments.model import normalize_gh_branch_work_mode
from agents_runner.environments.model import normalize_gh_task_branch_custom_template
from agents_runner.environments.model import normalize_gh_task_branch_naming_style
from agents_runner.gh.auth import is_gh_authenticated
from agents_runner.gh.errors import GhManagementError
from agents_runner.gh.gh_cli import is_gh_available
from agents_runner.gh.git_ops import (
    git_current_branch,
    git_default_base_branch,
    git_is_clean,
    git_list_branches,
    git_repo_root,
)
from agents_runner.gh.pr_retry import with_retry
from agents_runner.gh.process import expand_dir, require_ok, run_gh
from agents_runner.gh.rate_limiter import Priority
from agents_runner.gh.rate_limiter import _parse_rate_limit_seconds
from agents_runner.gh.rate_limiter import logger
from agents_runner.gh.rate_limiter import push_priority
from agents_runner.prompts.loader import load_prompt

_TASK_BRANCH_PREFIXES: tuple[str, ...] = ("midoriaiagents/",)
_COMMON_BASE_BRANCHES: tuple[str, ...] = ("main", "master", "trunk", "develop")

_MIDORI_AI_AGENTS_RUNNER_URL = "https://github.com/Midori-AI-OSS/Agents-Runner"
_MIDORIAI_URL = "https://github.com/Midori-AI-OSS/Midori-AI"
_PR_ATTRIBUTION_MARKER = "<!-- midori-ai-agents-runner-pr-footer -->"
_BRANCH_THEME_TOKENS: dict[str, tuple[str, ...]] = {
    GH_TASK_BRANCH_NAMING_STYLE_SONGS: (
        "anthem",
        "ballad",
        "chorus",
        "crescendo",
        "duet",
        "encore",
        "groove",
        "harmony",
    ),
    GH_TASK_BRANCH_NAMING_STYLE_FOODS: (
        "basil",
        "biscuit",
        "citrus",
        "dumpling",
        "ginger",
        "noodle",
        "olive",
        "taco",
    ),
    GH_TASK_BRANCH_NAMING_STYLE_ANIMALS: (
        "badger",
        "falcon",
        "lynx",
        "otter",
        "panther",
        "quail",
        "raven",
        "stoat",
    ),
    GH_TASK_BRANCH_NAMING_STYLE_COLORS: (
        "amber",
        "cerulean",
        "crimson",
        "jade",
        "ochre",
        "saffron",
        "teal",
        "umber",
    ),
    GH_TASK_BRANCH_NAMING_STYLE_SPACE: (
        "aurora",
        "comet",
        "cosmos",
        "meteor",
        "nebula",
        "nova",
        "orbit",
        "solstice",
    ),
}


def _append_pr_attribution_footer(
    body: str,
    agent_cli: str = "",
    agent_display_name: str | None = None,
) -> str:
    body = (body or "").rstrip()
    if _PR_ATTRIBUTION_MARKER in body:
        return body + "\n"

    agent_cli_name = agent_cli.strip()

    if agent_cli_name:
        if agent_display_name:
            github_url = get_agent_github_url(agent_cli_name)
            if github_url:
                agent_link = f"[{agent_display_name}]({github_url})"
            else:
                agent_link = agent_display_name
        else:
            agent_link = format_agent_markdown_link(agent_cli_name)
        agent_used = agent_link
    else:
        agent_used = "(unknown)"

    footer_content = load_prompt(
        "pr_attribution_footer",
        agent_used=agent_used,
        agents_runner_url=_MIDORI_AI_AGENTS_RUNNER_URL,
        midoriai_url=_MIDORIAI_URL,
        marker=_PR_ATTRIBUTION_MARKER,
    )

    footer = f"\n\n{footer_content}\n"
    return (body + footer) if body else footer.lstrip("\n")


@dataclass(frozen=True, slots=True)
class RepoPlan:
    workdir: str
    repo_root: str
    base_branch: str
    branch: str


def _is_task_branch(branch: str) -> bool:
    branch = (branch or "").strip()
    if not branch:
        return False
    return any(branch.startswith(prefix) for prefix in _TASK_BRANCH_PREFIXES)


def _pick_auto_base_branch(repo_root: str) -> str:
    repo_root = expand_dir(repo_root)
    default = git_default_base_branch(repo_root)
    if default:
        return default
    branches = git_list_branches(repo_root)
    if branches:
        for name in _COMMON_BASE_BRANCHES:
            if name in branches:
                return name
        return branches[0]
    current = git_current_branch(repo_root)
    if current and not _is_task_branch(current):
        return current
    return "main"


def _has_origin_branch(repo_root: str, branch: str) -> bool:
    repo_root = expand_dir(repo_root)
    branch = (branch or "").strip()
    if not branch:
        return False
    proc = run_gh(
        [
            "git",
            "-C",
            repo_root,
            "show-ref",
            "--verify",
            "--quiet",
            f"refs/remotes/origin/{branch}",
        ],
        timeout_s=8.0,
    )
    return proc.returncode == 0


def _update_base_branch_from_origin(repo_root: str, base_branch: str) -> None:
    repo_root = expand_dir(repo_root)
    base_branch = (base_branch or "").strip()
    if not base_branch:
        return
    if not _has_origin_branch(repo_root, base_branch):
        return
    require_ok(
        run_gh(
            ["git", "-C", repo_root, "merge", "--ff-only", f"origin/{base_branch}"],
            timeout_s=120.0,
        ),
        args=["git", "merge", "--ff-only"],
    )


def prepare_branch_for_task(
    repo_root: str,
    *,
    branch: str,
    base_branch: str | None = None,
) -> tuple[str, str]:
    repo_root = expand_dir(repo_root)

    # Fetch with retry for transient network issues
    def _fetch_with_retry() -> None:
        proc = run_gh(["git", "-C", repo_root, "fetch", "--prune"], timeout_s=120.0)
        require_ok(proc, args=["git", "fetch"])

    with_retry(
        _fetch_with_retry,
        operation_name="git fetch",
        retry_on=(OSError, TimeoutError, GhManagementError),
    )
    desired_base = str(base_branch or "").strip()
    base_branch = desired_base or _pick_auto_base_branch(repo_root)
    checkout_proc = run_gh(["git", "-C", repo_root, "checkout", "-f", base_branch], timeout_s=20.0)
    if checkout_proc.returncode != 0:
        require_ok(
            run_gh(
                [
                    "git",
                    "-C",
                    repo_root,
                    "checkout",
                    "-B",
                    base_branch,
                    f"origin/{base_branch}",
                ],
                timeout_s=20.0,
            ),
            args=["git", "checkout", "-B", base_branch],
        )
    _update_base_branch_from_origin(repo_root, base_branch)

    if not git_is_clean(repo_root):
        raise GhManagementError("repo has uncommitted changes; commit/stash before running")

    require_ok(
        run_gh(["git", "-C", repo_root, "checkout", "-B", branch], timeout_s=20.0),
        args=["git", "checkout", "-B"],
    )
    return base_branch, branch


def _sanitize_branch(value: str) -> str:
    value = _sanitize_branch_suffix(value)
    value = re.sub(r"/{2,}", "/", value)
    value = re.sub(r"/{2,}", "/", value)
    return value or "midoriaiagents/task"


def _sanitize_branch_suffix(value: str) -> str:
    value = str(value or "").strip().lower()
    value = re.sub(r"[^a-z0-9/_-]+", "-", value)
    value = re.sub(r"/{2,}", "/", value)
    value = re.sub(r"[-_]{2,}", "-", value)
    return value.strip("/_-")


def _stable_theme_token(task_id: str, naming_style: str) -> str:
    tokens = _BRANCH_THEME_TOKENS.get(naming_style, ())
    if not tokens:
        return ""
    seed = f"{naming_style}:{task_id}".encode("utf-8", errors="ignore")
    index = int(hashlib.sha256(seed).hexdigest(), 16) % len(tokens)
    return tokens[index]


def _render_custom_branch_suffix(task_id: str, template: str) -> str:
    safe_task_id = _sanitize_branch_suffix(task_id) or "task"
    safe_slug = safe_task_id
    rendered = normalize_gh_task_branch_custom_template(template)
    for token, value in (
        ("{task_id}", safe_task_id),
        ("{slug}", safe_slug),
        ("{date}", datetime.now(tz=UTC).strftime("%Y%m%d")),
        ("{rand}", secrets.token_hex(2)),
    ):
        rendered = rendered.replace(token, value)
    return _sanitize_branch_suffix(rendered)


def _build_task_branch_name(
    *,
    task_id: str,
    naming_style: str,
    custom_template: str,
) -> str:
    safe_task_id = _sanitize_branch_suffix(task_id) or "task"
    normalized_style = normalize_gh_task_branch_naming_style(naming_style)
    suffix = safe_task_id

    if normalized_style == GH_TASK_BRANCH_NAMING_STYLE_CUSTOM:
        suffix = _render_custom_branch_suffix(safe_task_id, custom_template)
    elif normalized_style != GH_TASK_BRANCH_NAMING_STYLE_STANDARD:
        theme_token = _stable_theme_token(safe_task_id, normalized_style)
        suffix = _sanitize_branch_suffix(f"{theme_token}-{safe_task_id}")

    suffix = suffix or safe_task_id
    for prefix in _TASK_BRANCH_PREFIXES:
        if suffix.startswith(prefix):
            suffix = suffix[len(prefix) :]
            break
    suffix = _sanitize_branch_suffix(suffix) or safe_task_id
    return _sanitize_branch(f"midoriaiagents/{suffix}")


def _find_next_available_branch(repo_root: str, base_branch_name: str, *, max_attempts: int = 100) -> str:
    """Find next available branch name by incrementing number suffix.

    Checks if branch exists and has an associated PR. If so, increments
    the number suffix until finding an unused branch name.

    Args:
        repo_root: Repository root path
        base_branch_name: Base branch name (e.g., 'midoriaiagents/task-123')
        max_attempts: Maximum number of attempts before giving up

    Returns:
        Available branch name (e.g., 'midoriaiagents/task-123-2')
    """
    from .pr_validation import check_existing_pr

    existing_branches = git_list_branches(repo_root)

    # Try base name first (without number suffix)
    if base_branch_name not in existing_branches:
        return base_branch_name

    # Check if base branch has a PR - if not, we can reuse it
    try:
        existing_pr = check_existing_pr(repo_root, base_branch_name)
        if existing_pr is None:
            # Branch exists but no PR, safe to reuse
            return base_branch_name
    except Exception:
        # If we can't check for PR, assume branch is available
        return base_branch_name

    # Branch exists with PR, need to find next available number
    for attempt in range(2, max_attempts + 2):
        candidate = f"{base_branch_name}-{attempt}"
        if candidate not in existing_branches:
            return candidate

        # Check if this numbered branch has a PR
        try:
            existing_pr = check_existing_pr(repo_root, candidate)
            if existing_pr is None:
                # Branch exists but no PR, safe to reuse
                return candidate
        except Exception:
            # If we can't check for PR, use this candidate
            return candidate

    # Fallback: return a high-numbered branch if we exceed max attempts
    return f"{base_branch_name}-{max_attempts + 2}"


def plan_repo_task(
    workdir: str,
    *,
    task_id: str,
    base_branch: str | None = None,
    branch_work_mode: str = GH_BRANCH_WORK_MODE_TASK_BRANCH,
    task_branch_naming_style: str = GH_TASK_BRANCH_NAMING_STYLE_STANDARD,
    task_branch_custom_template: str = GH_TASK_BRANCH_CUSTOM_TEMPLATE_DEFAULT,
) -> RepoPlan | None:
    workdir = expand_dir(workdir)
    repo_root = git_repo_root(workdir)
    if repo_root is None:
        return None
    desired_base = str(base_branch or "").strip()
    base_branch = desired_base or _pick_auto_base_branch(repo_root)
    work_mode = normalize_gh_branch_work_mode(branch_work_mode)
    if work_mode == GH_BRANCH_WORK_MODE_DIRECT_BASE:
        branch = base_branch
    else:
        base_branch_name = _build_task_branch_name(
            task_id=task_id,
            naming_style=task_branch_naming_style,
            custom_template=task_branch_custom_template,
        )
        branch = _find_next_available_branch(repo_root, base_branch_name)
    return RepoPlan(workdir=workdir, repo_root=repo_root, base_branch=base_branch, branch=branch)


def commit_push_and_pr(
    repo_root: str,
    *,
    branch: str,
    base_branch: str,
    title: str,
    body: str,
    use_gh: bool = True,
    agent_cli: str = "",
    agent_display_name: str | None = None,
    pr_retry_interval_minutes: int = 5,
    pr_retry_max_minutes: int = 60,
    on_log: Callable[[str], None] | None = None,
) -> str | None:
    repo_root = expand_dir(repo_root)
    branch = str(branch or "").strip()
    base_branch = str(base_branch or "").strip() or _pick_auto_base_branch(repo_root)
    if not branch:
        raise GhManagementError("cannot create a pull request without a branch")
    if branch == base_branch:
        raise GhManagementError(
            "current branch matches the base branch; PR creation is unavailable for direct-base tasks"
        )
    body = _append_pr_attribution_footer(
        body,
        agent_cli=agent_cli,
        agent_display_name=agent_display_name,
    )

    def _porcelain_status() -> str:
        proc = run_gh(["git", "-C", repo_root, "status", "--porcelain"], timeout_s=15.0)
        require_ok(proc, args=["git", "status"])
        return str(proc.stdout or "")

    def _ensure_local_branch() -> None:
        branch_ref = f"refs/heads/{branch}"
        exists_proc = run_gh(
            ["git", "-C", repo_root, "show-ref", "--verify", "--quiet", branch_ref],
            timeout_s=8.0,
        )
        if exists_proc.returncode == 0:
            return
        create_proc = run_gh(["git", "-C", repo_root, "branch", branch, base_branch], timeout_s=20.0)
        if create_proc.returncode != 0:
            create_proc = run_gh(
                ["git", "-C", repo_root, "branch", branch, f"origin/{base_branch}"],
                timeout_s=20.0,
            )
        require_ok(create_proc, args=["git", "branch"])

    def _checkout_branch_for_commit() -> None:
        current = git_current_branch(repo_root)
        if current == branch:
            return

        _ensure_local_branch()
        if not _porcelain_status().strip():
            require_ok(
                run_gh(["git", "-C", repo_root, "checkout", branch], timeout_s=20.0),
                args=["git", "checkout"],
            )
            return

        # Common case: the repo is dirty on the base branch. If the task branch
        # has no unique commits yet, reset it to the current HEAD so we can
        # switch branches without overwriting local changes.
        if current == base_branch:
            ahead_proc = run_gh(
                [
                    "git",
                    "-C",
                    repo_root,
                    "rev-list",
                    "--count",
                    f"{base_branch}..{branch}",
                ],
                timeout_s=10.0,
            )
            ahead = None
            if ahead_proc.returncode == 0:
                try:
                    ahead = int((ahead_proc.stdout or "").strip() or "0")
                except ValueError:
                    ahead = None
            if ahead == 0:
                require_ok(
                    run_gh(
                        ["git", "-C", repo_root, "checkout", "-B", branch, "HEAD"],
                        timeout_s=20.0,
                    ),
                    args=["git", "checkout", "-B"],
                )
                return

        merge_proc = run_gh(["git", "-C", repo_root, "checkout", "--merge", branch], timeout_s=20.0)
        if merge_proc.returncode != 0:
            combined = ((merge_proc.stdout or "") + "\n" + (merge_proc.stderr or "")).strip()
            raise GhManagementError(
                "failed to switch to PR branch while preserving local changes; "
                "commit/stash your work (or switch back to the base branch) and rerun PR creation.\n"
                f"{combined}".rstrip()
            )
        unmerged_proc = run_gh(["git", "-C", repo_root, "ls-files", "-u"], timeout_s=8.0)
        require_ok(unmerged_proc, args=["git", "ls-files", "-u"])
        if (unmerged_proc.stdout or "").strip():
            raise GhManagementError(
                "switching branches resulted in merge conflicts; resolve them and rerun PR creation."
            )

    _checkout_branch_for_commit()
    with push_priority(Priority.HIGH):
        has_worktree_changes = bool(_porcelain_status().strip())

        if has_worktree_changes:
            require_ok(
                run_gh(["git", "-C", repo_root, "add", "-A"], timeout_s=30.0),
                args=["git", "add"],
            )
            commit_proc = run_gh(["git", "-C", repo_root, "commit", "-m", title], timeout_s=60.0)
            if commit_proc.returncode != 0:
                combined = (commit_proc.stdout or "") + "\n" + (commit_proc.stderr or "")
                if "nothing to commit" not in combined.lower():
                    require_ok(commit_proc, args=["git", "commit"])

        ahead_count = None
        for base_ref in (base_branch, f"origin/{base_branch}"):
            count_proc = run_gh(
                ["git", "-C", repo_root, "rev-list", "--count", f"{base_ref}..HEAD"],
                timeout_s=15.0,
            )
            if count_proc.returncode == 0:
                try:
                    ahead_count = int((count_proc.stdout or "").strip() or "0")
                except ValueError:
                    ahead_count = None
                break

        if not has_worktree_changes and (ahead_count is not None and ahead_count <= 0):
            return None

        # Push with retry for transient network issues
        def _push_with_retry() -> None:
            proc = run_gh(["git", "-C", repo_root, "push", "-u", "origin", branch], timeout_s=180.0)
            require_ok(proc, args=["git", "push"])

        with_retry(
            _push_with_retry,
            operation_name="git push",
            retry_on=(OSError, TimeoutError, GhManagementError),
        )

        if not use_gh or not is_gh_available():
            return ""

        if not is_gh_authenticated(timeout_s=10.0, use_cache=True):
            raise GhManagementError("`gh` is not authenticated; run `gh auth login`")

        # Create PR with retry for transient network issues
        pr_url: str | None = None

        def _run_pr_create():
            return run_gh(
                [
                    "gh",
                    "pr",
                    "create",
                    "--head",
                    branch,
                    "--base",
                    base_branch,
                    "--title",
                    title,
                    "--body",
                    body,
                ],
                cwd=repo_root,
                timeout_s=180.0,
            )

        def _extract_pr_url(proc: subprocess.CompletedProcess[str]) -> bool:
            nonlocal pr_url
            if proc.returncode != 0:
                out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
                for line in out.splitlines():
                    line = line.strip()
                    if line.startswith("http"):
                        pr_url = line
                        return True
            else:
                out = (proc.stdout or "").strip()
                if out.startswith("http"):
                    pr_url = out.splitlines()[0].strip()
                    return True
                for line in out.splitlines():
                    line = line.strip()
                    if line.startswith("http"):
                        pr_url = line
                        return True
            return False

        def _create_pr_with_retry() -> None:
            nonlocal pr_url
            proc = _run_pr_create()
            if _extract_pr_url(proc):
                return
            if proc.returncode == 0:
                return

            # Rate-limit detection before require_ok
            if pr_retry_interval_minutes > 0:
                pause_s = _parse_rate_limit_seconds(proc.stderr or "", proc.stdout or "")
                if pause_s is not None:
                    original_msg = ((proc.stderr or "") + "\n" + (proc.stdout or "")).strip()
                    logger.info(
                        "[gh-pr-retry] rate-limited: retrying every %d minutes for up to %d minutes",
                        pr_retry_interval_minutes,
                        pr_retry_max_minutes,
                    )
                    if on_log:
                        on_log(
                            "[gh-pr-retry] Waiting for GitHub — will retry gh pr create in "
                            f"{pr_retry_interval_minutes} minutes"
                        )

                    start_time = time.monotonic()
                    max_s = pr_retry_max_minutes * 60
                    interval_s = pr_retry_interval_minutes * 60
                    attempt = 0

                    while True:
                        elapsed = time.monotonic() - start_time
                        if elapsed > max_s:
                            raise RuntimeError(
                                f"[gh-pr-retry] rate-limit retry exhausted after "
                                f"{pr_retry_max_minutes}m: {original_msg}"
                            )

                        time.sleep(interval_s)
                        attempt += 1
                        elapsed = time.monotonic() - start_time

                        if on_log:
                            on_log(
                                "[gh-pr-retry] Waiting for GitHub — retrying gh pr create now "
                                f"(attempt {attempt}, elapsed {elapsed:.0f}s)"
                            )

                        proc = _run_pr_create()
                        if _extract_pr_url(proc):
                            return
                        if proc.returncode == 0:
                            return

                        still_rate_limited = _parse_rate_limit_seconds(proc.stderr or "", proc.stdout or "")
                        if still_rate_limited is None:
                            # Different error — fall through to require_ok / with_retry
                            break

                    # Fall through: non-rate-limit error after retries
                    if proc.returncode != 0:
                        require_ok(proc, args=["gh", "pr", "create"])
                    return

            # Non-rate-limit failure, or disabled (interval=0)
            require_ok(proc, args=["gh", "pr", "create"])

        with_retry(
            _create_pr_with_retry,
            operation_name="gh pr create",
            retry_on=(OSError, TimeoutError, GhManagementError),
        )

        return pr_url
