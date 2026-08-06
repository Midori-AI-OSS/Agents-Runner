"""Focused verification for the shared GitHub authentication snapshot."""

from __future__ import annotations

import subprocess
import threading
import time

from concurrent.futures import ThreadPoolExecutor
from typing import Callable

import pytest

from agents_runner.gh import auth
from agents_runner.gh.errors import GhManagementError


@pytest.fixture(autouse=True)
def _reset_auth_cache() -> None:
    auth.reset_gh_auth_cache()
    yield
    auth.reset_gh_auth_cache()


def _status_result(*, authenticated: bool, login: str = "octocat") -> subprocess.CompletedProcess[str]:
    output = f"Logged in to github.com account {login} (keyring)" if authenticated else "not logged in"
    return subprocess.CompletedProcess(["gh"], 0 if authenticated else 1, output, "")


def _run_concurrently(call: Callable[[], object], *, count: int = 24) -> list[object]:
    start = threading.Barrier(count)

    def synchronized_call() -> object:
        start.wait()
        return call()

    with ThreadPoolExecutor(max_workers=count) as executor:
        return list(executor.map(lambda _: synchronized_call(), range(count)))


def test_simultaneous_cold_cache_callers_launch_one_status_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def run_gh(args: list[str], *, timeout_s: float) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        time.sleep(0.05)
        return _status_result(authenticated=True)

    monkeypatch.setattr(auth, "run_gh", run_gh)
    results = _run_concurrently(auth.get_gh_auth_snapshot)

    assert calls == 1
    assert all(isinstance(result, auth.GhAuthSnapshot) and result.authenticated for result in results)


@pytest.mark.parametrize("authenticated", [True, False])
def test_authentication_results_are_cached(monkeypatch: pytest.MonkeyPatch, authenticated: bool) -> None:
    calls = 0

    def run_gh(args: list[str], *, timeout_s: float) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        return _status_result(authenticated=authenticated)

    monkeypatch.setattr(auth, "run_gh", run_gh)
    assert auth.is_gh_authenticated() is authenticated
    assert auth.is_gh_authenticated() is authenticated
    assert calls == 1


def test_authentication_and_login_queries_share_one_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def run_gh(args: list[str], *, timeout_s: float) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        return _status_result(authenticated=True, login="OctoCat")

    monkeypatch.setattr(auth, "run_gh", run_gh)
    assert auth.is_gh_authenticated()
    assert auth.resolve_authenticated_login() == "octocat"
    assert calls == 1


def test_failed_refresh_wakes_waiters(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def run_gh(args: list[str], *, timeout_s: float) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        time.sleep(0.05)
        raise GhManagementError("command timed out")

    monkeypatch.setattr(auth, "run_gh", run_gh)
    results = _run_concurrently(auth.get_gh_auth_snapshot)

    assert calls == 1
    assert all(
        isinstance(result, auth.GhAuthSnapshot) and result.error == auth.GhAuthError.TIMEOUT for result in results
    )


def test_transient_failure_is_retried_without_normal_cache_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def run_gh(args: list[str], *, timeout_s: float) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise GhManagementError("command timed out")
        return _status_result(authenticated=True)

    monkeypatch.setattr(auth, "run_gh", run_gh)
    assert not auth.is_gh_authenticated()
    assert auth.is_gh_authenticated()
    assert calls == 2


def test_invalidation_during_refresh_reprobes_before_publishing(monkeypatch: pytest.MonkeyPatch) -> None:
    first_probe_started = threading.Event()
    release_first_probe = threading.Event()
    calls = 0

    def run_gh(args: list[str], *, timeout_s: float) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            first_probe_started.set()
            assert release_first_probe.wait(timeout=2.0)
            return _status_result(authenticated=True, login="stale-user")
        return _status_result(authenticated=True, login="fresh-user")

    monkeypatch.setattr(auth, "run_gh", run_gh)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first_result = executor.submit(auth.get_gh_auth_snapshot)
        assert first_probe_started.wait(timeout=2.0)
        waiting_result = executor.submit(auth.get_gh_auth_snapshot)
        auth.invalidate_gh_auth_cache()
        release_first_probe.set()

    assert first_result.result().login == "fresh-user"
    assert waiting_result.result().login == "fresh-user"
    assert auth.resolve_authenticated_login() == "fresh-user"
    assert calls == 2


def test_forced_refresh_is_single_flight(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def run_gh(args: list[str], *, timeout_s: float) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        time.sleep(0.05)
        return _status_result(authenticated=True)

    monkeypatch.setattr(auth, "run_gh", run_gh)
    results = _run_concurrently(lambda: auth.get_gh_auth_snapshot(use_cache=False))

    assert calls == 1
    assert all(isinstance(result, auth.GhAuthSnapshot) and result.authenticated for result in results)


def test_expiry_uses_injected_monotonic_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [100.0]
    calls = 0
    auth.reset_gh_auth_cache(monotonic=lambda: now[0])

    def run_gh(args: list[str], *, timeout_s: float) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        return _status_result(authenticated=True)

    monkeypatch.setattr(auth, "run_gh", run_gh)
    auth.is_gh_authenticated()
    now[0] += 299.0
    auth.is_gh_authenticated()
    now[0] += 2.0
    auth.is_gh_authenticated()
    assert calls == 2


def test_api_fallback_runs_only_when_status_has_no_login(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def run_gh(args: list[str], *, timeout_s: float) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args[1:3] == ["auth", "status"]:
            login = "" if len(calls) == 1 else "status-user"
            return _status_result(authenticated=True, login=login)
        return subprocess.CompletedProcess(args, 0, '{"login": "api-user"}', "")

    monkeypatch.setattr(auth, "run_gh", run_gh)
    assert auth.resolve_authenticated_login() == "api-user"
    auth.invalidate_gh_auth_cache()
    assert auth.resolve_authenticated_login() == "status-user"
    assert [call[1] for call in calls] == ["auth", "api", "auth"]
