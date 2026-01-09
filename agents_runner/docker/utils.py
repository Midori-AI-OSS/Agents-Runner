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


def _is_system_directory(path: str) -> bool:
    """
    Check if path is a system directory that should never be mounted.
    
    Args:
        path: Path to check
        
    Returns:
        True if path is a system directory, False otherwise
    """
    system_dirs = {"/etc", "/var", "/usr", "/opt", "/srv", "/root", "/boot", "/sys", "/proc"}
    path_abs = os.path.abspath(path)
    
    # Exact match
    if path_abs in system_dirs:
        return True
    
    # Starts with system dir
    for sys_dir in system_dirs:
        if path_abs == sys_dir or path_abs.startswith(sys_dir + os.sep):
            return True
    
    return False


def _is_safe_mount_root(path: str, original_workdir: str, max_depth: int = 3) -> bool:
    """
    Validate that a mount root is safe to mount.
    
    This function enforces security boundaries to prevent mounting sensitive
    directories like home directories, root filesystem, or system directories.
    
    Security boundaries:
    1. Home directory itself cannot be mounted
    2. Root filesystem (/) cannot be mounted
    3. System directories (/etc, /var, etc.) cannot be mounted
    4. Maximum traversal depth is enforced
    
    Args:
        path: Candidate mount root to validate
        original_workdir: Original user-requested working directory
        max_depth: Maximum allowed traversal depth (default: 3)
        
    Returns:
        True if safe to mount, False otherwise
    """
    path = os.path.abspath(path)
    original_workdir = os.path.abspath(original_workdir)
    home = os.path.expanduser("~")
    
    # Boundary check 1: Don't mount home directory itself
    if path == home:
        return False
    
    # Boundary check 2: Don't mount root filesystem
    if path == "/":
        return False
    
    # Boundary check 3: Don't mount system directories
    if _is_system_directory(path):
        return False
    
    # Boundary check 4: Limit traversal depth
    try:
        rel = os.path.relpath(original_workdir, path)
        # Count directory levels (ignore '.' components)
        depth = len([p for p in rel.split(os.sep) if p and p != "."])
        if depth > max_depth:
            return False
    except ValueError:
        # Paths on different drives (Windows) or other errors
        return False
    
    return True


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
    
    SECURITY: This function enforces strict boundaries to prevent mounting
    sensitive directories:
    - Home directory (~) cannot be mounted
    - Root filesystem (/) cannot be mounted
    - System directories (/etc, /var, etc.) cannot be mounted
    - Maximum traversal depth of 3 levels is enforced
    
    Raises:
        ValueError: If a parent directory mount is detected that violates
                   security boundaries
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

    # SECURITY VALIDATION: Check if mount_root is safe
    if mount_root != host_workdir:
        # Verify this isn't the same directory (symlinks, etc.)
        try:
            is_same = os.path.samefile(mount_root, host_workdir)
        except (OSError, FileNotFoundError):
            is_same = False
        
        if not is_same and not _is_safe_mount_root(mount_root, host_workdir):
            # Determine which boundary was violated for clear error message
            home = os.path.expanduser("~")
            if mount_root == home:
                reason = f"home directory ({home})"
            elif mount_root == "/":
                reason = "root filesystem (/)"
            elif _is_system_directory(mount_root):
                reason = f"system directory ({mount_root})"
            else:
                reason = "maximum traversal depth exceeded (3 levels)"
            
            raise ValueError(
                f"Refusing to mount unsafe directory: {mount_root}\n"
                f"  Reason: {reason}\n"
                f"  Requested workdir: {host_workdir}\n"
                f"  This is a security boundary to prevent exposing sensitive data.\n"
                f"  Consider changing to the project directory or initializing a git repository there."
            )

    rel = os.path.relpath(host_workdir, mount_root)
    if rel in {"", "."}:
        return mount_root, container_mount
    if rel.startswith(".."):
        return host_workdir, container_mount
    return mount_root, os.path.join(container_mount, rel)
