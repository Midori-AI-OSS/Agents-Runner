import pytest

from agents_runner.pr_metadata import ensure_github_context_file
from agents_runner.pr_metadata import ensure_pr_metadata_file


@pytest.mark.parametrize("ensure_file", [ensure_pr_metadata_file, ensure_github_context_file])
@pytest.mark.parametrize("path", ["", "  "])
def test_metadata_creation_rejects_empty_path(ensure_file, path):
    with pytest.raises(ValueError, match="missing .* path"):
        ensure_file(path, task_id="task")
