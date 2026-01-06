import re
import time

from dataclasses import dataclass

from ..agent_display import format_agent_markdown_link
from .errors import GhManagementError
from .gh_cli import is_gh_available
from .git_ops import (
    git_current_branch,
    git_default_base_branch,
    git_is_clean,
    git_list_branches,
    git_repo_root,
)
from .process import _expand_dir, _require_ok, _run

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

    footer = (
        "\n\n---\n"
        f"{_PR_ATTRIBUTION_MARKER}\n"
        f"Created by [Midori AI Agents Runner]({_MIDORI_AI_AGENTS_RUNNER_URL}).\n"
        f"Agent Used: {agent_used}\n"
        f"Related: [Midori AI Monorepo]({_MIDORI_AI_URL}).\n"
    )
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
    repo_root = _expand_dir(repo_root)
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
    repo_root = _expand_dir(repo_root)
    branch = (branch or "").strip()
    if not branch:
        return False
    proc = _run(
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
    repo_root = _expand_dir(repo_root)
    base_branch = (base_branch or "").strip()
    if not base_branch:
        return
    if not _has_origin_branch(repo_root, base_branch):
        return
    _require_ok(
        _run(
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
    repo_root = _expand_dir(repo_root)

    _require_ok(
        _run(["git", "-C", repo_root, "fetch", "--prune"], timeout_s=120.0),
        args=["git", "fetch"],
    )
    desired_base = str(base_branch or "").strip()
    base_branch = desired_base or _pick_auto_base_branch(repo_root)
    checkout_proc = _run(
        ["git", "-C", repo_root, "checkout", "-f", base_branch], timeout_s=20.0
    )
    if checkout_proc.returncode != 0:
        _require_ok(
            _run(
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

    _require_ok(
        _run(["git", "-C", repo_root, "checkout", "-B", branch], timeout_s=20.0),
        args=["git", "checkout", "-B"],
    )
    return base_branch, branch


def _sanitize_branch(value: str) -> str:
    value = (value or "").strip()
    value = re.sub(r"[^a-zA-Z0-9/_-]+", "-", value)
    value = value.strip("-")
    value = re.sub(r"/{2,}", "/", value)
    return value or "midoriaiagents/task"


def plan_repo_task(
    workdir: str,
    *,
    task_id: str,
    base_branch: str | None = None,
) -> RepoPlan | None:
    workdir = _expand_dir(workdir)
    repo_root = git_repo_root(workdir)
    if repo_root is None:
        return None
    branch = _sanitize_branch(f"midoriaiagents/{task_id}")
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
    repo_root = _expand_dir(repo_root)
    base_branch = str(base_branch or "").strip() or _pick_auto_base_branch(repo_root)
    body = _append_pr_attribution_footer(
        body, agent_cli=agent_cli, agent_cli_args=agent_cli_args
    )

    def _porcelain_status() -> str:
        proc = _run(["git", "-C", repo_root, "status", "--porcelain"], timeout_s=15.0)
        _require_ok(proc, args=["git", "status"])
        return str(proc.stdout or "")

    def _ensure_local_branch() -> None:
        branch_ref = f"refs/heads/{branch}"
        exists_proc = _run(
            ["git", "-C", repo_root, "show-ref", "--verify", "--quiet", branch_ref],
            timeout_s=8.0,
        )
        if exists_proc.returncode == 0:
            return
        create_proc = _run(
            ["git", "-C", repo_root, "branch", branch, base_branch], timeout_s=20.0
        )
        if create_proc.returncode != 0:
            create_proc = _run(
                ["git", "-C", repo_root, "branch", branch, f"origin/{base_branch}"],
                timeout_s=20.0,
            )
        _require_ok(create_proc, args=["git", "branch"])

    def _checkout_branch_for_commit() -> None:
        if git_current_branch(repo_root) == branch:
            return

        _ensure_local_branch()
        if not _porcelain_status().strip():
            _require_ok(
                _run(["git", "-C", repo_root, "checkout", branch], timeout_s=20.0),
                args=["git", "checkout"],
            )
            return

        # Preserve a dirty worktree without relying on patch-based stash apply
        # (which can conflict even for non-overlapping edits when the target
        # branch diverged). Instead, checkpoint the work on a temporary branch,
        # then cherry-pick onto the target branch.
        temp_branch = _sanitize_branch(f"midoriaiagents/_wip/{time.time_ns()}")
        _require_ok(
            _run(["git", "-C", repo_root, "checkout", "-b", temp_branch], timeout_s=20.0),
            args=["git", "checkout", "-b"],
        )
        _require_ok(
            _run(["git", "-C", repo_root, "add", "-A"], timeout_s=30.0),
            args=["git", "add"],
        )
        commit_proc = _run(
            ["git", "-C", repo_root, "commit", "-m", title], timeout_s=60.0
        )
        _require_ok(commit_proc, args=["git", "commit"])

        _require_ok(
            _run(["git", "-C", repo_root, "checkout", branch], timeout_s=20.0),
            args=["git", "checkout"],
        )
        cherry_proc = _run(
            ["git", "-C", repo_root, "cherry-pick", temp_branch], timeout_s=180.0
        )
        if cherry_proc.returncode != 0:
            _run(["git", "-C", repo_root, "cherry-pick", "--abort"], timeout_s=30.0)
            combined = (
                (cherry_proc.stdout or "") + "\n" + (cherry_proc.stderr or "")
            ).strip()
            raise GhManagementError(
                "failed to apply local changes onto the PR branch; "
                "resolve conflicts and rerun PR creation.\n"
                f"{combined}".rstrip()
            )
        _run(["git", "-C", repo_root, "branch", "-D", temp_branch], timeout_s=8.0)

    _checkout_branch_for_commit()

    has_worktree_changes = bool(_porcelain_status().strip())

    if has_worktree_changes:
        _require_ok(
            _run(["git", "-C", repo_root, "add", "-A"], timeout_s=30.0),
            args=["git", "add"],
        )
        commit_proc = _run(
            ["git", "-C", repo_root, "commit", "-m", title], timeout_s=60.0
        )
        if commit_proc.returncode != 0:
            combined = (commit_proc.stdout or "") + "\n" + (commit_proc.stderr or "")
            if "nothing to commit" not in combined.lower():
                _require_ok(commit_proc, args=["git", "commit"])

    ahead_count = None
    for base_ref in (base_branch, f"origin/{base_branch}"):
        count_proc = _run(
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

    push_proc = _run(
        ["git", "-C", repo_root, "push", "-u", "origin", branch], timeout_s=180.0
    )
    _require_ok(push_proc, args=["git", "push"])

    if not use_gh or not is_gh_available():
        return ""

    auth_proc = _run(["gh", "auth", "status"], timeout_s=10.0)
    if auth_proc.returncode != 0:
        raise GhManagementError("`gh` is not authenticated; run `gh auth login`")

    pr_proc = _run(
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
    if pr_proc.returncode != 0:
        out = ((pr_proc.stdout or "") + "\n" + (pr_proc.stderr or "")).strip()
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("http"):
                return line
        _require_ok(pr_proc, args=["gh", "pr", "create"])
    out = (pr_proc.stdout or "").strip()
    if out.startswith("http"):
        return out.splitlines()[0].strip()
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("http"):
            return line
    return None
