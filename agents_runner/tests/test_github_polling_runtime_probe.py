from __future__ import annotations

import os
import time

from PySide6.QtCore import QCoreApplication
from PySide6.QtCore import QEventLoop
from PySide6.QtCore import QTimer

import pytest

from agents_runner.environments import Environment
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.ui.pages.github_work_coordinator import GitHubWorkCoordinator


_ENABLE_RUNTIME_TEST_ENV = "RUN_GITHUB_POLL_RUNTIME_TEST"
_DURATION_ENV = "GITHUB_POLL_RUNTIME_DURATION_S"
_INTERVAL_ENV = "GITHUB_POLL_RUNTIME_INTERVAL_S"


def _env_int(name: str, default: int, *, minimum: int) -> int:
    raw = str(os.environ.get(name, default)).strip()
    try:
        parsed = int(raw)
    except Exception:
        parsed = default
    return max(minimum, parsed)


def test_github_polling_runtime_refresh_counts() -> None:
    """Long-running runtime probe for GitHub background polling.

    This test is intentionally opt-in because it runs for a few minutes and uses
    live GitHub queries for Midori-AI-OSS/Agents-Runner.
    """

    if str(os.environ.get(_ENABLE_RUNTIME_TEST_ENV, "")).strip() != "1":
        pytest.skip(
            "Set RUN_GITHUB_POLL_RUNTIME_TEST=1 to run this multi-minute runtime probe."
        )

    duration_s = _env_int(_DURATION_ENV, 180, minimum=60)
    interval_s = _env_int(_INTERVAL_ENV, 15, minimum=5)

    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])

    coordinator = GitHubWorkCoordinator()
    counts: dict[str, int] = {"pr": 0, "issue": 0}
    started_at = time.monotonic()
    first_refresh_delay_s: float | None = None

    def _on_cache_updated(item_type: str, env_id: str) -> None:
        nonlocal first_refresh_delay_s

        key = str(item_type or "").strip().lower()
        if key not in counts:
            counts[key] = 0
        counts[key] += 1

        elapsed_s = time.monotonic() - started_at
        if first_refresh_delay_s is None:
            first_refresh_delay_s = elapsed_s

        print(
            f"[github-poll-runtime] +{elapsed_s:6.1f}s refreshed {key} for {env_id} "
            f"(count={counts[key]})",
            flush=True,
        )

    coordinator.cache_updated.connect(_on_cache_updated)

    env_id = "runtime-probe"
    coordinator.set_environments(
        {
            env_id: Environment(
                env_id=env_id,
                name="Runtime Probe",
                workspace_type=WORKSPACE_CLONED,
                workspace_target="Midori-AI-OSS/Agents-Runner",
                github_polling_enabled=True,
            )
        }
    )
    coordinator.set_settings_data(
        {
            "github_polling_enabled": True,
            "github_poll_interval_s": interval_s,
            "github_poll_startup_delay_s": 0,
            "agentsnova_auto_review_enabled": False,
        }
    )

    loop = QEventLoop()
    QTimer.singleShot(duration_s * 1000, loop.quit)
    loop.exec()

    coordinator.set_settings_data({"github_polling_enabled": False})

    elapsed_total_s = time.monotonic() - started_at
    total_refreshes = sum(counts.values())
    first_delay_text = (
        f"{first_refresh_delay_s:.1f}s" if first_refresh_delay_s is not None else "none"
    )

    print(
        "[github-poll-runtime] summary "
        f"duration={elapsed_total_s:.1f}s interval={interval_s}s "
        f"first_refresh={first_delay_text} "
        f"pr={counts.get('pr', 0)} issue={counts.get('issue', 0)} "
        f"total={total_refreshes}",
        flush=True,
    )

    assert total_refreshes > 0, (
        "Background GitHub polling produced zero refresh events. "
        f"duration={elapsed_total_s:.1f}s interval={interval_s}s "
        f"counts={counts}"
    )
