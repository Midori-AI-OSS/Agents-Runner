# pyright: reportPrivateUsage=false
from __future__ import annotations

import os
import time
from collections.abc import Callable
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from types import SimpleNamespace

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import pytest

from agents_runner.environments import Environment
from agents_runner.environments import GitHubRepoContext
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.gh.polling_state import PollingStateStore
from agents_runner.gh.work_items import GitHubComment
from agents_runner.gh.work_items import GitHubReactionSummary
from agents_runner.gh.work_items import GitHubWorkItem
from agents_runner.gh.work_items import list_issue_comments
from agents_runner.gh.work_items import list_pull_request_review_comments
from agents_runner.ui.pages import github_auto_review
from agents_runner.ui.pages import github_work_coordinator
from agents_runner.ui.pages.github_auto_review import AutoReviewCollector
from agents_runner.ui.pages.github_work_coordinator import GitHubWorkCoordinator

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _store(tmp_path) -> PollingStateStore:
    return PollingStateStore(
        database_path=str(tmp_path / "state.sqlite3"),
        key_path=str(tmp_path / "state.key"),
        lock_path=str(tmp_path / "state.lock"),
    )


def _collector(
    store: PollingStateStore | None = None, settings: dict[str, object] | None = None
) -> AutoReviewCollector:
    return AutoReviewCollector(
        store=store,
        settings_provider=lambda: {
            "agentsnova_auto_review_enabled": True,
            "agentsnova_auto_reactions_enabled": False,
            "agentsnova_trusted_users_global": ["trusted-user"],
            **(settings or {}),
        },
        environments_provider=lambda: {},
    )


def _item(*, updated_at: str, created_at: str = "2025-01-01T00:00:00Z") -> GitHubWorkItem:
    return GitHubWorkItem(
        item_type="issue",
        number=1,
        title="Issue",
        state="open",
        url="https://github.com/org/repo/issues/1",
        author="other",
        created_at=created_at,
        updated_at=updated_at,
        body="",
        is_draft=False,
        head_ref="",
        base_ref="",
        head_repo_owner="",
        head_repo_name="",
        is_cross_repo=False,
    )


def _recent_timestamp(days_ago: int = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _comment(comment_id: int, body: str = "@agentsnova please help", created_at: str | None = None) -> GitHubComment:
    created_at = created_at or _recent_timestamp()
    return GitHubComment(
        comment_id=comment_id,
        node_id=str(comment_id),
        body=body,
        author="trusted-user",
        created_at=created_at,
        updated_at=created_at,
        url=f"https://github.com/org/repo/issues/1#issuecomment-{comment_id}",
        reactions=GitHubReactionSummary(),
    )


def _scan(monkeypatch: pytest.MonkeyPatch, comments: list[GitHubComment] | None = None) -> list[int]:
    calls: list[int] = []

    def fetch(_owner: str, _repo: str, *, issue_number: int, **_kwargs: object) -> list[GitHubComment]:
        calls.append(issue_number)
        return list(comments or [])

    monkeypatch.setattr(github_auto_review, "list_issue_comments", fetch)
    return calls


def test_active_item_is_scanned(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _scan(monkeypatch, [_comment(1)])
    results = _collector().collect(
        env=None, repo_owner="org", repo_name="repo", items=[_item(updated_at=_recent_timestamp())]
    )
    assert results
    assert calls == [1]


def test_inactive_item_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _scan(monkeypatch, [_comment(1)])
    results = _collector(
        settings={"github_poll_inactive_filter_enabled": True, "github_poll_inactive_max_age_days": 5}
    ).collect(env=None, repo_owner="org", repo_name="repo", items=[_item(updated_at="2020-01-01T00:00:00Z")])
    assert results == []
    assert calls == []


def test_reactivated_old_item_becomes_eligible(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _scan(monkeypatch, [_comment(1)])
    results = _collector(
        settings={"github_poll_inactive_filter_enabled": True, "github_poll_inactive_max_age_days": 5}
    ).collect(env=None, repo_owner="org", repo_name="repo", items=[_item(updated_at=_recent_timestamp())])
    assert results
    assert calls == [1]


def test_unparseable_timestamp_is_treated_active(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _scan(monkeypatch, [_comment(1)])
    results = _collector().collect(
        env=None, repo_owner="org", repo_name="repo", items=[_item(updated_at="not-a-date", created_at="also-bad")]
    )
    assert results
    assert calls == [1]


def test_per_env_disable_overrides_global(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _scan(monkeypatch, [_comment(1)])
    env = Environment(
        env_id="env",
        name="Env",
        workspace_type=WORKSPACE_CLONED,
        workspace_target="org/repo",
        github_poll_inactive_filter_mode="disabled",
    )
    results = _collector(settings={"github_poll_inactive_filter_enabled": True}).collect(
        env=env, repo_owner="org", repo_name="repo", items=[_item(updated_at="2020-01-01T00:00:00Z")]
    )
    assert results
    assert calls == [1]


def test_per_env_age_override(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _scan(monkeypatch, [_comment(1)])
    env = Environment(
        env_id="env",
        name="Env",
        workspace_type=WORKSPACE_CLONED,
        workspace_target="org/repo",
        github_poll_inactive_max_age_days=1000,
    )
    activity = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
    results = _collector(
        settings={"github_poll_inactive_filter_enabled": True, "github_poll_inactive_max_age_days": 5}
    ).collect(env=env, repo_owner="org", repo_name="repo", items=[_item(updated_at=activity)])
    assert results
    assert calls == [1]


def test_pending_anchor_bypasses_filter(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store(tmp_path)
    store.set_pending_anchor(mention_key="issue_comment:1", repo="org/repo", item_type="issue", number=1, now_epoch=1)
    collector = _collector(store, {"github_poll_inactive_filter_enabled": True, "github_poll_inactive_max_age_days": 5})
    collector.seed_from_store(now_epoch=2)
    calls = _scan(monkeypatch, [_comment(1)])
    results = collector.collect(
        env=None, repo_owner="org", repo_name="repo", items=[_item(updated_at="2020-01-01T00:00:00Z")]
    )
    assert results
    assert calls == [1]


def test_observation_recorded_even_when_filtered(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store(tmp_path)
    _scan(monkeypatch)
    item = _item(updated_at="2020-01-01T00:00:00Z")
    assert (
        _collector(store, {"github_poll_inactive_filter_enabled": True}).collect(
            env=None, repo_owner="org", repo_name="repo", items=[item]
        )
        == []
    )
    assert store.get_observation(repo="org/repo", item_type="issue", number=1) is not None


def test_multiple_mentions_progress_across_cycles(monkeypatch: pytest.MonkeyPatch) -> None:
    _scan(monkeypatch, [_comment(1, created_at=_recent_timestamp(1)), _comment(2)])
    collector = _collector()
    item = _item(updated_at=_recent_timestamp())
    first = collector.collect(env=None, repo_owner="org", repo_name="repo", items=[item])
    assert len(first) == 1
    assert first[0]["mention_key"] == "issue_comment:2"
    assert collector.emit_decision(
        emit_key="org/repo:issue:1:issue_comment:issue_comment:2",
        mention_key=str(first[0]["mention_key"]),
        repo_slug="org/repo",
        item_type="issue",
        number=1,
        item_key="org/repo:issue:1",
        is_item_active=lambda _key: False,
        now_epoch=100000,
    )
    second = collector.collect(env=None, repo_owner="org", repo_name="repo", items=[item])
    assert second[0]["mention_key"] == "issue_comment:1"


def _emit(collector: AutoReviewCollector, emit_key: str = "emit", mention_key: str = "mention") -> bool:
    return collector.emit_decision(
        emit_key=emit_key,
        mention_key=mention_key,
        repo_slug="org/repo",
        item_type="issue",
        number=1,
        item_key="org/repo:issue:1",
        is_item_active=lambda _key: False,
        now_epoch=100000,
    )


def test_emit_decision_dedupes_within_process() -> None:
    collector = _collector()
    assert _emit(collector) is True
    assert _emit(collector) is False


def test_emit_decision_suppressed_after_restart_reserved(tmp_path) -> None:
    store = _store(tmp_path)
    assert _emit(_collector(store)) is True
    restarted = _collector(store)
    restarted.seed_from_store(now_epoch=100000)
    assert _emit(restarted) is False


def test_stale_reservation_released_after_restart(tmp_path) -> None:
    store = _store(tmp_path)
    assert store.reserve_mention(
        emit_key="emit", mention_key="mention", repo="org/repo", item_type="issue", number=1, now_epoch=1
    )
    collector = _collector(store)
    collector.seed_from_store(now_epoch=100000)
    assert _emit(collector) is True


def test_processed_mention_never_reemits(tmp_path) -> None:
    store = _store(tmp_path)
    assert _emit(_collector(store)) is True
    assert store.ack_item_mentions(repo="org/repo", item_type="issue", number=1, now_epoch=100001) == 1
    restarted = _collector(store)
    restarted.seed_from_store(now_epoch=100002)
    assert _emit(restarted) is False


def test_emit_decision_unblocks_pending_anchor(tmp_path) -> None:
    store = _store(tmp_path)
    store.set_pending_anchor(mention_key="mention", repo="org/repo", item_type="issue", number=1, now_epoch=1)
    collector = _collector(store)
    collector.seed_from_store(now_epoch=2)
    assert _emit(collector) is True
    assert store.list_pending_anchors() == []
    assert _emit(collector) is False


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        return QApplication([])
    if not isinstance(app, QApplication):
        pytest.skip("QApplication is required for Qt widget lifecycle compatibility.")
    return app


def _wait_until(predicate: Callable[[], bool], *, timeout_ms: int = 2000) -> bool:
    app = _app()
    deadline = time.monotonic() + timeout_ms / 1000.0
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        QTest.qWait(10)
    app.processEvents()
    return bool(predicate())


def _coordinator_env(env_id: str) -> Environment:
    return Environment(env_id=env_id, name=env_id, workspace_type=WORKSPACE_CLONED, workspace_target="org/repo")


def test_shared_repo_fetches_once_per_cycle(monkeypatch: pytest.MonkeyPatch) -> None:
    _app()
    coordinator = GitHubWorkCoordinator()
    coordinator.set_environments({"env-a": _coordinator_env("env-a"), "env-b": _coordinator_env("env-b")})
    context = GitHubRepoContext(
        repo_owner="org", repo_name="repo", repo_url="https://github.com/org/repo", source="test"
    )
    monkeypatch.setattr(github_work_coordinator, "resolve_environment_github_repo", lambda _env: context)
    pr_calls: list[int] = []
    issue_calls: list[int] = []
    item = _item(updated_at="2026-01-01T00:00:00Z")
    monkeypatch.setattr(
        github_work_coordinator, "list_open_pull_requests", lambda *_args, **_kwargs: pr_calls.append(1) or [item]
    )
    monkeypatch.setattr(
        github_work_coordinator, "list_open_issues", lambda *_args, **_kwargs: issue_calls.append(1) or [item]
    )
    collected: list[str] = []
    monkeypatch.setattr(
        coordinator._auto_review, "collect", lambda *, env, **_kwargs: collected.append(env.env_id) or []
    )
    coordinator._run_poll_cycle(["env-a", "env-b"])
    assert _wait_until(
        lambda: all(
            coordinator.get_cache_entry(item_type=kind, env_id=env) is not None
            for env in ("env-a", "env-b")
            for kind in ("pr", "issue")
        )
    )
    assert len(pr_calls) == len(issue_calls) == 1
    assert sorted(collected) == ["env-a", "env-a", "env-b", "env-b"]
    entries = {
        (env, kind): coordinator.get_cache_entry(item_type=kind, env_id=env)
        for env in ("env-a", "env-b")
        for kind in ("pr", "issue")
    }
    assert all(entry is not None and entry.items for entry in entries.values())


def test_env_without_repo_still_completes(monkeypatch: pytest.MonkeyPatch) -> None:
    _app()
    coordinator = GitHubWorkCoordinator()
    coordinator.set_environments({"env-a": _coordinator_env("env-a"), "env-b": _coordinator_env("env-b")})
    context = GitHubRepoContext(
        repo_owner="org", repo_name="repo", repo_url="https://github.com/org/repo", source="test"
    )
    monkeypatch.setattr(
        github_work_coordinator,
        "resolve_environment_github_repo",
        lambda env: None if env and env.env_id == "env-a" else context,
    )
    monkeypatch.setattr(github_work_coordinator, "list_open_pull_requests", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(github_work_coordinator, "list_open_issues", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(coordinator._auto_review, "collect", lambda **_kwargs: [])
    coordinator._run_poll_cycle(["env-a", "env-b"])
    assert _wait_until(
        lambda: all(
            coordinator.get_cache_entry(item_type=kind, env_id=env) is not None
            for env in ("env-a", "env-b")
            for kind in ("pr", "issue")
        )
    )
    assert all(
        (entry := coordinator.get_cache_entry(item_type=kind, env_id="env-a")) is not None and entry.items == []
        for kind in ("pr", "issue")
    )
    assert all(
        (entry := coordinator.get_cache_entry(item_type=kind, env_id="env-b")) is not None
        and entry.repo_context is not None
        for kind in ("pr", "issue")
    )


def test_review_comments_desc_stops_at_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def page(args: list[str], **_kwargs: object) -> list[dict[str, object]]:
        calls.append(args)
        page_number = int(next(part.split("=")[1] for part in args[1].split("&") if part.startswith("page=")))
        first = 301 - (page_number - 1) * 100
        return [
            {
                "id": value,
                "node_id": str(value),
                "body": "",
                "user": {"login": "user"},
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
                "html_url": "",
                "reactions": {},
            }
            for value in range(first, first - 100, -1)
        ]

    monkeypatch.setattr("agents_runner.gh.work_items.run_gh_gh_json_read", page)
    comments = list_pull_request_review_comments("org", "repo", pull_number=1, limit=300, newest_first=True)
    assert len(calls) == 3
    assert len(comments) == 300
    assert [comment.comment_id for comment in comments] == list(range(301, 1, -1))


def test_issue_comments_keep_existing_pagination(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def page(args: list[str], **_kwargs: object) -> list[dict[str, object]]:
        calls.append(args)
        page_number = int(next(part.split("=")[1] for part in args[1].split("&") if part.startswith("page=")))
        if page_number <= 3:
            first = (page_number - 1) * 100 + 1
            return [
                {
                    "id": value,
                    "node_id": str(value),
                    "body": "",
                    "user": {"login": "user"},
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "html_url": "",
                    "reactions": {},
                }
                for value in range(first, first + 100)
            ]
        return []

    monkeypatch.setattr("agents_runner.gh.work_items.run_gh_gh_json_read", page)
    comments = list_issue_comments("org", "repo", issue_number=1, limit=250, newest_first=True)
    assert len(calls) == 4
    assert len(comments) == 250
    assert all("sort=" not in args[1] and "direction=" not in args[1] for args in calls)
