import pytest

from agents_runner.gh.errors import GhManagementError
from agents_runner.gh.repo_clone import ensure_github_clone


@pytest.mark.parametrize("destination", ["", "   "])
def test_clone_rejects_blank_destination_without_touching_cwd(tmp_path, monkeypatch, destination):
    monkeypatch.chdir(tmp_path)
    marker = tmp_path / "marker"
    marker.write_text("keep")

    with pytest.raises(GhManagementError, match="missing clone destination"):
        ensure_github_clone("owner/repo", destination, recreate_if_needed=True)

    assert marker.read_text() == "keep"
    assert list(tmp_path.parent.glob(f"{tmp_path.name}.bak-*")) == []
