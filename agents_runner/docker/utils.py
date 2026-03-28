import os
import posixpath
import tempfile


def split_mount_spec(mount: str) -> tuple[str, str, str]:
    """Split a Docker ``-v`` mount string into host/container/mode parts."""
    mount_str = str(mount or "").strip()
    if not mount_str:
        return "", "", ""

    parts = mount_str.split(":", 2)
    if len(parts) < 2:
        return "", "", ""

    host_path = str(parts[0] or "").strip()
    container_path = str(parts[1] or "").strip()
    mode = str(parts[2] or "").strip() if len(parts) > 2 else ""
    return host_path, container_path, mode


def normalize_host_mount_path(path: str) -> str:
    """Normalize a host bind-mount path for comparisons."""
    raw = str(path or "").strip()
    if not raw:
        return ""
    return os.path.normpath(
        os.path.abspath(os.path.expanduser(os.path.expandvars(raw)))
    )


def normalize_container_mount_path(path: str) -> str:
    """Normalize a container bind-mount path for comparisons."""
    raw = str(path or "").strip()
    if not raw:
        return ""
    normalized = posixpath.normpath(raw)
    return raw if normalized == "." else normalized


def write_preflight_script(
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

    Deduplicates by both host path and container path:
    - If multiple mounts share the same host path, keeps the first occurrence
    - If multiple mounts share the same container path, keeps the first occurrence

    Host paths are normalized (expandvars + expanduser + abspath + normpath)
    and container paths are normalized as POSIX paths for comparison.

    Args:
        mounts: List of mount strings in format "host:container[:mode]"

    Returns:
        Deduplicated list of mounts preserving original order
    """
    seen_host_paths: set[str] = set()
    seen_container_paths: set[str] = set()
    result: list[str] = []

    for mount in mounts:
        mount_str = str(mount or "").strip()
        if not mount_str:
            continue

        host_path_raw, container_path_raw, _mode = split_mount_spec(mount_str)
        if not host_path_raw or not container_path_raw:
            continue

        host_path = normalize_host_mount_path(host_path_raw)
        container_path = normalize_container_mount_path(container_path_raw)

        # Skip if host path or container path already seen
        if host_path in seen_host_paths or container_path in seen_container_paths:
            continue

        seen_host_paths.add(host_path)
        seen_container_paths.add(container_path)
        result.append(mount_str)

    return result


def deduplicate_mount_args(mount_args: list[str]) -> list[str]:
    """Deduplicate flattened Docker ``-v`` mount arguments."""
    mount_specs: list[str] = []
    i = 0
    while i < len(mount_args):
        flag = str(mount_args[i] or "").strip()
        if flag != "-v":
            i += 1
            continue
        if i + 1 >= len(mount_args):
            break
        spec = str(mount_args[i + 1] or "").strip()
        if spec:
            mount_specs.append(spec)
        i += 2

    result: list[str] = []
    for mount in deduplicate_mounts(mount_specs):
        result.extend(["-v", mount])
    return result


def resolve_workspace_mount(
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
