import re

from dataclasses import dataclass

from ..agent_display import format_agent_markdown_link
from ..prompts.loader import load_prompt
from .errors import GhManagementError
from .gh_cli import is_gh_available
from .git_ops import (
    git_current_branch,
    git_default_base_branch,
    git_is_clean,
    git_list_branches,
    git_repo_root,
)
from .pr_retry import with_retry
from .process import expand_dir, require_ok, run_gh

_TASK_BRANCH_PREFIXES: tuple[str, ...] = ("midoriaiagents/",)
_COMMON_BASE_BRANCHES: tuple[str, ...] = ("main", "master", "trunk", "develop")

_MIDORI_AI_AGENTS_RUNNER_URL = "https://github.com/Midori-AI-OSS/Agents-Runner"
_MIDORI_AI_URL = "https://github.com/Midori-AI-OSS/Midori-AI"
_PR_ATTRIBUTION_MARKER = "<!-- midori-ai-agents-runner-pr-footer -->"


def _append_pr_attribution_footer(
    body: str, agent_cli: str = "", agent_cli_args: str = ""
) -> str:
    body = (body or "").rstrip()
    if _PR_ATTRIBUTION_MARKER in body:
        return body + "\n"

    agent_cli_name = agent_cli.strip()
    agent_args = agent_cli_args.strip()

    if agent_cli_name:
        agent_link = format_agent_markdown_link(agent_cli_name)
        if agent_args:
            agent_used = f"{agent_link} {agent_args}"
        else:
            agent_used = agent_link
    else:
        agent_used = "(unknown)"

    footer_content = load_prompt(
        "pr_attribution_footer",
        agent_used=agent_used,
        agentsrun_ghner_url=_MIDORI_AI_AGENTS_RUNNER_URL,
        midori_ai_url=_MIDORI_AI_URL,
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
    checkout_proc = run_gh(
        ["git", "-C", repo_root, "checkout", "-f", base_branch], timeout_s=20.0
    )
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
        raise GhManagementError(
            "repo has uncommitted changes; commit/stash before running"
        )

    require_ok(
        run_gh(["git", "-C", repo_root, "checkout", "-B", branch], timeout_s=20.0),
        args=["git", "checkout", "-B"],
    )
    return base_branch, branch


def _sanitize_branch(value: str) -> str:
    value = (value or "").strip()
    value = re.sub(r"[^a-zA-Z0-9/_-]+", "-", value)
    value = value.strip("-")
    value = re.sub(r"/{2,}", "/", value)
    return value or "midoriaiagents/task"


def _find_next_available_branch(
    repo_root: str, base_branch_name: str, *, max_attempts: int = 100
) -> str:
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
) -> RepoPlan | None:
    workdir = expand_dir(workdir)
    repo_root = git_repo_root(workdir)
    if repo_root is None:
        return None
    base_branch_name = _sanitize_branch(f"midoriaiagents/{task_id}")
    branch = _find_next_available_branch(repo_root, base_branch_name)
    desired_base = str(base_branch or "").strip()
    base_branch = desired_base or _pick_auto_base_branch(repo_root)
    return RepoPlan(
        workdir=workdir, repo_root=repo_root, base_branch=base_branch, branch=branch
    )


def commit_push_and_pr(
    repo_root: str,
    *,
    branch: str,
    base_branch: str,
    title: str,
    body: str,
    use_gh: bool = True,
    agent_cli: str = "",
    agent_cli_args: str = "",
) -> str | None:
    repo_root = expand_dir(repo_root)
    base_branch = str(base_branch or "").strip() or _pick_auto_base_branch(repo_root)
    body = _append_pr_attribution_footer(
        body, agent_cli=agent_cli, agent_cli_args=agent_cli_args
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
        create_proc = run_gh(
            ["git", "-C", repo_root, "branch", branch, base_branch], timeout_s=20.0
        )
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

        merge_proc = run_gh(
            ["git", "-C", repo_root, "checkout", "--merge", branch], timeout_s=20.0
        )
        if merge_proc.returncode != 0:
            combined = (
                (merge_proc.stdout or "") + "\n" + (merge_proc.stderr or "")
            ).strip()
            raise GhManagementError(
                "failed to switch to PR branch while preserving local changes; "
                "commit/stash your work (or switch back to the base branch) and rerun PR creation.\n"
                f"{combined}".rstrip()
            )
        unmerged_proc = run_gh(
            ["git", "-C", repo_root, "ls-files", "-u"], timeout_s=8.0
        )
        require_ok(unmerged_proc, args=["git", "ls-files", "-u"])
        if (unmerged_proc.stdout or "").strip():
            raise GhManagementError(
                "switching branches resulted in merge conflicts; resolve them and rerun PR creation."
            )

    _checkout_branch_for_commit()

    has_worktree_changes = bool(_porcelain_status().strip())

    if has_worktree_changes:
        require_ok(
            run_gh(["git", "-C", repo_root, "add", "-A"], timeout_s=30.0),
            args=["git", "add"],
        )
        commit_proc = run_gh(
            ["git", "-C", repo_root, "commit", "-m", title], timeout_s=60.0
        )
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
        proc = run_gh(
            ["git", "-C", repo_root, "push", "-u", "origin", branch], timeout_s=180.0
        )
        require_ok(proc, args=["git", "push"])

    with_retry(
        _push_with_retry,
        operation_name="git push",
        retry_on=(OSError, TimeoutError, GhManagementError),
    )

    if not use_gh or not is_gh_available():
        return ""

    auth_proc = run_gh(["gh", "auth", "status"], timeout_s=10.0)
    if auth_proc.returncode != 0:
        raise GhManagementError("`gh` is not authenticated; run `gh auth login`")

    # Create PR with retry for transient network issues
    pr_url: str | None = None

    def _create_pr_with_retry() -> None:
        nonlocal pr_url
        proc = run_gh(
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
        if proc.returncode != 0:
            out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("http"):
                    pr_url = line
                    return
            require_ok(proc, args=["gh", "pr", "create"])
        else:
            out = (proc.stdout or "").strip()
            if out.startswith("http"):
                pr_url = out.splitlines()[0].strip()
            else:
                for line in out.splitlines():
                    line = line.strip()
                    if line.startswith("http"):
                        pr_url = line
                        break

    with_retry(
        _create_pr_with_retry,
        operation_name="gh pr create",
        retry_on=(OSError, TimeoutError, GhManagementError),
    )

    return pr_url
