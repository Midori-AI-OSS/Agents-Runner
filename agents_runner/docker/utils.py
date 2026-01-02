import os
import tempfile


def _write_preflight_script(
    script: str,
    label: str,
    task_id: str,
    preflight_tmp_paths: list[str],
) -> str:
    fd, tmp_path = tempfile.mkstemp(
        prefix=f"codex-preflight-{label}-{task_id or 'task'}-",
        suffix=".sh",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            if not script.endswith("\n"):
                script += "\n"
            f.write(script)
    except Exception:
        try:
            os.close(fd)
        except Exception:
            pass
        raise
    preflight_tmp_paths.append(tmp_path)
    return tmp_path

