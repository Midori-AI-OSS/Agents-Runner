from __future__ import annotations

import json
import subprocess

from unittest.mock import patch

import pytest

from agents_runner.gh.permissions import check_pr_creation_capability


@pytest.mark.parametrize(
    ("push", "expected_status", "expected_can_create"),
    [
        (True, "available", True),
        (False, "read_only", False),
        ("false", "unavailable", False),
        (None, "unavailable", False),
        (1, "unavailable", False),
    ],
)
def test_push_permission_requires_boolean(push: object, expected_status: str, expected_can_create: bool) -> None:
    response = subprocess.CompletedProcess([], 0, stdout=json.dumps({"permissions": {"push": push}}), stderr="")
    with (
        patch("agents_runner.gh.permissions.shutil.which", return_value="gh"),
        patch("agents_runner.gh.permissions.run_gh", return_value=response),
    ):
        capability = check_pr_creation_capability("owner", "repo", use_gh=True)

    assert capability.status == expected_status
    assert capability.can_create_pr is expected_can_create
