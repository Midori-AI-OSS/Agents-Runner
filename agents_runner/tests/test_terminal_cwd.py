import subprocess

from agents_runner.terminal_apps import linux_terminal_args


def test_terminal_does_not_run_script_when_working_directory_is_missing(tmp_path):
    marker = tmp_path / "ran"
    script = f"touch '{marker}'; touch '{marker}'"
    args = linux_terminal_args("xterm", "xterm", script, str(tmp_path / "missing"))
    result = subprocess.run(args[2:], capture_output=True, check=False)
    assert result.returncode != 0
    assert not marker.exists()


def test_terminal_runs_script_in_requested_directory(tmp_path):
    args = linux_terminal_args("xterm", "xterm", "pwd", str(tmp_path))
    result = subprocess.run(args[2:], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == str(tmp_path)
