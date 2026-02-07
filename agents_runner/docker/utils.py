import os
import tempfile


def _write_preflight_script(
    script: str,
    label: str,
    task_id: str,
    preflight_tmp_paths: list[str],
) -> str:
    fd, tmp_path = tempfile.mkstemp(
        prefix=f"agents-runner-preflight-{label}-{task_id or 'task'}-",
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


def deduplicate_mounts(mounts: list[str]) -> list[str]:
    """
    Deduplicate mount specifications while preserving order.

    Compares mount points by their container path (the part before the first or
    second colon). If multiple mounts target the same container path, keeps only
    the first occurrence.

    Args:
        mounts: List of mount strings in format "host:container[:mode]"

    Returns:
        Deduplicated list of mounts preserving original order
    """
    seen_container_paths: set[str] = set()
    result: list[str] = []

    for mount in mounts:
        mount_str = str(mount or "").strip()
        if not mount_str:
            continue

        # Extract container path (second part of host:container[:mode])
        parts = mount_str.split(":")
        if len(parts) < 2:
            # Malformed mount, skip
            continue

        container_path = parts[1]

        if container_path not in seen_container_paths:
            seen_container_paths.add(container_path)
            result.append(mount_str)

    return result


def _resolve_workspace_mount(
    host_workdir: str,
    *,
    container_mount: str,
) -> tuple[str, str]:
    """
    Resolve a stable mount root and container working directory.

    When users point to a subdirectory inside a repo/project, mounting only that
    subdirectory can break tooling that searches parent directories (e.g. for
    `.git/` or `pyproject.toml`). This helper finds a suitable ancestor to mount
    while preserving the original working directory inside the container.
    """

    host_workdir = os.path.abspath(os.path.expanduser(str(host_workdir or "").strip()))
    container_mount = str(container_mount or "").strip()
    if not host_workdir or not container_mount:
        return host_workdir, container_mount

    def _has_markers(path: str) -> bool:
        return os.path.exists(os.path.join(path, ".git")) or os.path.isfile(
            os.path.join(path, "pyproject.toml")
        )

    mount_root = host_workdir
    if os.path.isdir(host_workdir):
        cursor = host_workdir
        while True:
            if os.path.isdir(cursor) and _has_markers(cursor):
                mount_root = cursor
                break
            parent = os.path.dirname(cursor)
            if parent == cursor:
                break
            cursor = parent

    rel = os.path.relpath(host_workdir, mount_root)
    if rel in {"", "."}:
        return mount_root, container_mount
    if rel.startswith(".."):
        return host_workdir, container_mount
    return mount_root, os.path.join(container_mount, rel)
