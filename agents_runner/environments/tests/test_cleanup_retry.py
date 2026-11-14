from unittest.mock import patch

from agents_runner.environments.cleanup import _cleanup_one_task_workspace


def test_cleanup_reports_failed_removal_retry(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    def failed_rmtree(path, *, onexc):
        onexc(lambda _: None, str(path), PermissionError("denied"))

    with (
        patch("agents_runner.environments.cleanup.is_safe_task_workspace_path", return_value=True),
        patch("agents_runner.environments.cleanup.shutil.rmtree", side_effect=failed_rmtree),
        patch("agents_runner.environments.cleanup.os.chmod", side_effect=PermissionError("denied")),
    ):
        assert not _cleanup_one_task_workspace(task_workspace=str(workspace), data_dir=None, on_log=None)
    assert workspace.exists()
