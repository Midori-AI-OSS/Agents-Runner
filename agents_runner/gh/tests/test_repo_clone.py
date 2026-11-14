import subprocess

from pathlib import Path

import pytest

from agents_runner.gh import repo_clone


def test_recreate_mismatched_repo_clones_after_backup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dest = tmp_path / "repo"
    dest.mkdir()
    (dest / "original").write_text("preserved")
    monkeypatch.setattr(repo_clone, "is_git_repo", lambda _path: True)
    monkeypatch.setattr(repo_clone, "_read_origin_url", lambda _path: "https://github.com/old/repo.git")
    calls: list[list[str]] = []

    def clone(args: list[str], *, timeout_s: float) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        dest.mkdir()
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(repo_clone, "run_gh", clone)
    repo_clone.ensure_github_clone(
        "https://github.com/new/repo.git", str(dest), prefer_gh=False, recreate_if_needed=True
    )

    assert calls == [["git", "clone", "https://github.com/new/repo.git", str(dest)]]
    backups = list(tmp_path.glob("repo.bak-*"))
    assert len(backups) == 1
    assert (backups[0] / "original").read_text() == "preserved"
    assert dest.is_dir()
