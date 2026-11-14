from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from agents_runner.artifacts import ArtifactMeta, StagingArtifactMeta
from agents_runner.ui.pages.artifacts_tab import ArtifactsTab


def test_artifact_timestamps_can_be_compared_with_mixed_timezone_metadata() -> None:
    encrypted = ArtifactMeta("id", "file", "text/plain", "2025-01-01T00:00:00", 1)
    staging = StagingArtifactMeta("file", Path("file"), 1, datetime(2025, 1, 4, tzinfo=timezone.utc), "text/plain")

    encrypted_time = ArtifactsTab._artifact_modified_at(cast(ArtifactsTab, None), encrypted)
    staging_time = ArtifactsTab._artifact_modified_at(cast(ArtifactsTab, None), staging)

    assert encrypted_time is not None
    assert staging_time is not None
    assert encrypted_time.tzinfo is not None
    assert staging_time.tzinfo is not None
    assert encrypted_time < staging_time
