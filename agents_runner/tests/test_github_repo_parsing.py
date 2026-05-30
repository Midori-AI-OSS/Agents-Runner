from __future__ import annotations

from pathlib import Path

import pytest

from agents_runner.environments.model import WORKSPACE_CLONED
from agents_runner.environments.preflight_snapshot import build_preflight_identity_token
from agents_runner.gh import repo_clone
from agents_runner.gh.errors import GhManagementError
from agents_runner.gh.git_ops import normalize_github_repo_slug, parse_github_url


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Owner/Repo", ("Owner", "Repo")),
        ("owner/repo.name", ("owner", "repo.name")),
        ("https://github.com/Owner/Repo", ("Owner", "Repo")),
        ("https://github.com/owner/repo.name.git", ("owner", "repo.name")),
        ("git@github.com:Owner/Repo.git", ("Owner", "Repo")),
        ("ssh://git@github.com/owner/repo.name", ("owner", "repo.name")),
        ("ssh://git@github.com:22/owner/repo", ("owner", "repo")),
    ],
)
def test_parse_github_url_accepts_supported_formats(value: str, expected: tuple[str, str]) -> None:
    assert parse_github_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "https://example.com/github.com/owner/repo",
        "https://github.com/owner/repo/tree/main",
        "https://www.github.com/owner/repo",
        "ssh://github.com/owner/repo",
        "owner/repo/extra",
        "owner only/repo",
    ],
)
def test_parse_github_url_rejects_embedded_hosts_and_extra_segments(
    value: str,
) -> None:
    assert parse_github_url(value) == (None, None)


def test_normalize_github_repo_slug_lowercases_and_preserves_dotted_repo_names() -> None:
    assert normalize_github_repo_slug("https://github.com/Owner/Repo.Name.git") == ("owner/repo.name")


def test_build_preflight_identity_token_distinguishes_github_lookalikes() -> None:
    real = build_preflight_identity_token(
        env_id="env-1",
        workspace_type=WORKSPACE_CLONED,
        workspace_target="https://github.com/Owner/Repo.git",
        host_workdir="",
    )
    lookalike = build_preflight_identity_token(
        env_id="env-1",
        workspace_type=WORKSPACE_CLONED,
        workspace_target="https://example.com/github.com/Owner/Repo.git",
        host_workdir="",
    )

    assert real != lookalike


def test_build_preflight_identity_token_keeps_non_github_targets_distinct() -> None:
    first = build_preflight_identity_token(
        env_id="env-1",
        workspace_type=WORKSPACE_CLONED,
        workspace_target="https://gitlab.com/example/repo-a.git",
        host_workdir="",
    )
    second = build_preflight_identity_token(
        env_id="env-1",
        workspace_type=WORKSPACE_CLONED,
        workspace_target="https://gitlab.com/example/repo-b.git",
        host_workdir="",
    )

    assert first != second


def test_ensure_github_clone_accepts_equivalent_existing_repo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def _is_git_repo(_path: str, *, timeout_s: float = 8.0) -> bool:
        _ = timeout_s
        return True

    def _read_origin_url(_dest_dir: str) -> str:
        return "git@github.com:owner/repo.name.git"

    dest = tmp_path / "repo"
    dest.mkdir()
    monkeypatch.setattr(repo_clone, "is_git_repo", _is_git_repo)
    monkeypatch.setattr(repo_clone, "_read_origin_url", _read_origin_url)

    repo_clone.ensure_github_clone(
        "https://github.com/Owner/Repo.Name.git",
        str(dest),
    )


def test_ensure_github_clone_rejects_invalid_ref_against_existing_repo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _is_git_repo(_path: str, *, timeout_s: float = 8.0) -> bool:
        _ = timeout_s
        return True

    def _read_origin_url(_dest_dir: str) -> str:
        return "https://github.com/owner/repo.git"

    dest = tmp_path / "repo"
    dest.mkdir()
    monkeypatch.setattr(repo_clone, "is_git_repo", _is_git_repo)
    monkeypatch.setattr(repo_clone, "_read_origin_url", _read_origin_url)

    with pytest.raises(GhManagementError, match="destination contains a different repo"):
        repo_clone.ensure_github_clone(
            "https://example.com/github.com/owner/repo",
            str(dest),
        )
