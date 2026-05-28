from __future__ import annotations

import os
import shutil
import time

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .paths import safe_env_id
from .paths import safe_task_id


TASK_WORKSPACE_LOCATION_APP_DATA = "app_data"
TASK_WORKSPACE_LOCATION_SCRATCH_DRIVE = "scratch_drive"
TASK_WORKSPACE_LOCATIONS = {
    TASK_WORKSPACE_LOCATION_APP_DATA,
    TASK_WORKSPACE_LOCATION_SCRATCH_DRIVE,
}
SCRATCH_TASK_WORKSPACES_ROOT = "/tmp/midoriai/agents-runner/task-workspaces"
RECOMMENDED_SCRATCH_FREE_BYTES = 16 * 1024**3

DEFAULT_TASK_WORKSPACE_CLEANUP_RETENTION_DAYS = 30
DEFAULT_TASK_WORKSPACE_CLEANUP_INTERVAL_MINUTES = 60
DEFAULT_TASK_WORKSPACE_CLEANUP_SCAN_DELAY_SECONDS = 5


@dataclass(frozen=True)
class ScratchDriveStatus:
    path: str
    exists_or_creatable: bool
    is_ram_drive: bool
    free_bytes: int
    free_gib: float
    has_recommended_space: bool
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class WorkspaceMoveResult:
    source: str
    destination: str
    moved: bool
    skipped: bool
    error: str = ""


def normalize_task_workspace_location(value: object) -> str:
    location = str(value or "").strip().lower()
    if location in TASK_WORKSPACE_LOCATIONS:
        return location
    return TASK_WORKSPACE_LOCATION_APP_DATA


def clamp_int(value: object, *, minimum: int, maximum: int, default: int) -> int:
    try:
        parsed = int(str(value).strip())
    except Exception:
        parsed = default
    return max(minimum, min(maximum, parsed))


def normalize_task_workspace_settings(settings: dict[str, object]) -> dict[str, object]:
    normalized = dict(settings)
    normalized["task_workspace_location"] = normalize_task_workspace_location(
        normalized.get("task_workspace_location")
    )
    normalized["task_workspace_cleanup_retention_days"] = clamp_int(
        normalized.get("task_workspace_cleanup_retention_days"),
        minimum=1,
        maximum=365,
        default=DEFAULT_TASK_WORKSPACE_CLEANUP_RETENTION_DAYS,
    )
    normalized["task_workspace_cleanup_interval_minutes"] = clamp_int(
        normalized.get("task_workspace_cleanup_interval_minutes"),
        minimum=5,
        maximum=1440,
        default=DEFAULT_TASK_WORKSPACE_CLEANUP_INTERVAL_MINUTES,
    )
    normalized["task_workspace_cleanup_scan_delay_seconds"] = clamp_int(
        normalized.get("task_workspace_cleanup_scan_delay_seconds"),
        minimum=0,
        maximum=60,
        default=DEFAULT_TASK_WORKSPACE_CLEANUP_SCAN_DELAY_SECONDS,
    )
    return normalized


def app_data_task_workspaces_root(data_dir: str | None = None) -> str:
    from .paths import default_data_dir

    base = data_dir or default_data_dir()
    return os.path.join(base, "managed-repos")


def task_workspaces_root(
    *, data_dir: str | None = None, location: object = TASK_WORKSPACE_LOCATION_APP_DATA
) -> str:
    normalized = normalize_task_workspace_location(location)
    if normalized == TASK_WORKSPACE_LOCATION_SCRATCH_DRIVE:
        return SCRATCH_TASK_WORKSPACES_ROOT
    return app_data_task_workspaces_root(data_dir=data_dir)


def task_workspace_path(
    env_id: str,
    *,
    data_dir: str | None = None,
    task_id: str | None = None,
    location: object = TASK_WORKSPACE_LOCATION_APP_DATA,
) -> str:
    base = os.path.join(
        task_workspaces_root(data_dir=data_dir, location=location),
        safe_env_id(env_id),
    )
    if task_id:
        return os.path.join(base, "tasks", safe_task_id(task_id))
    return base


def task_workspace_candidates(
    env_id: str,
    task_id: str,
    *,
    data_dir: str | None = None,
) -> tuple[str, str]:
    return (
        task_workspace_path(
            env_id,
            data_dir=data_dir,
            task_id=task_id,
            location=TASK_WORKSPACE_LOCATION_APP_DATA,
        ),
        task_workspace_path(
            env_id,
            data_dir=data_dir,
            task_id=task_id,
            location=TASK_WORKSPACE_LOCATION_SCRATCH_DRIVE,
        ),
    )


def _mount_point_from_mountinfo(encoded: str) -> str:
    return encoded.replace("\\040", " ")


def is_tmp_ram_drive() -> bool:
    tmp_path = Path("/tmp").resolve()
    best_match = ""
    best_fs = ""
    try:
        with open("/proc/self/mountinfo", "r", encoding="utf-8") as f:
            for line in f:
                before, sep, after = line.partition(" - ")
                if not sep:
                    continue
                fields = before.split()
                if len(fields) < 5:
                    continue
                mount_point = _mount_point_from_mountinfo(fields[4])
                try:
                    mount_path = Path(mount_point).resolve()
                except Exception:
                    continue
                if tmp_path == mount_path or tmp_path.is_relative_to(mount_path):
                    fs_type = after.split()[0] if after.split() else ""
                    if len(str(mount_path)) > len(best_match):
                        best_match = str(mount_path)
                        best_fs = fs_type
    except Exception:
        return False
    return best_fs == "tmpfs"


def scratch_drive_status() -> ScratchDriveStatus:
    path = SCRATCH_TASK_WORKSPACES_ROOT
    root_path = Path(path)
    exists_or_creatable = root_path.is_dir()
    warnings: list[str] = []
    if not exists_or_creatable:
        probe = root_path.parent
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        exists_or_creatable = probe.is_dir() and os.access(probe, os.W_OK | os.X_OK)
        if not exists_or_creatable:
            warnings.append("Scratch drive is not writable.")

    try:
        usage = shutil.disk_usage("/tmp")
        free_bytes = int(usage.free)
    except Exception as exc:
        free_bytes = 0
        warnings.append(f"Scratch drive free space could not be checked: {exc}")

    free_gib = float(free_bytes) / float(1024**3)
    is_ram = is_tmp_ram_drive()
    has_space = free_bytes >= RECOMMENDED_SCRATCH_FREE_BYTES
    if not is_ram:
        warnings.append("Scratch drive is not a RAM drive.")
    if not has_space:
        warnings.append("Scratch drive has less than 16 GiB free.")
    if is_ram and has_space:
        warnings.append("Scratch drive storage is temporary and clears on reboot.")

    return ScratchDriveStatus(
        path=path,
        exists_or_creatable=exists_or_creatable,
        is_ram_drive=is_ram,
        free_bytes=free_bytes,
        free_gib=free_gib,
        has_recommended_space=has_space,
        warnings=tuple(warnings),
    )


def ensure_task_workspace_root(
    *, data_dir: str | None = None, location: object = TASK_WORKSPACE_LOCATION_APP_DATA
) -> str:
    root = task_workspaces_root(data_dir=data_dir, location=location)
    Path(root).mkdir(parents=True, exist_ok=True)
    if not Path(root).is_dir():
        raise RuntimeError(f"Task workspace root is not a directory: {root}")
    return root


def _expected_roots(data_dir: str | None = None) -> tuple[Path, Path]:
    return (
        Path(app_data_task_workspaces_root(data_dir=data_dir)).expanduser().resolve(),
        Path(SCRATCH_TASK_WORKSPACES_ROOT).expanduser().resolve(),
    )


def is_safe_task_workspace_path(path: str, *, data_dir: str | None = None) -> bool:
    if not path:
        return False
    try:
        candidate = Path(path).expanduser().resolve()
    except Exception:
        return False
    if candidate in {Path("/"), Path.home().resolve()}:
        return False
    if candidate.is_symlink():
        return False
    parts = set(candidate.parts)
    if "tasks" not in parts:
        return False
    for root in _expected_roots(data_dir=data_dir):
        if candidate == root or root in candidate.parents:
            return True
    return False


def move_task_workspace(
    *,
    env_id: str,
    task_id: str,
    data_dir: str | None,
    source_location: object,
    destination_location: object,
    on_progress: Callable[[str], None] | None = None,
) -> WorkspaceMoveResult:
    source = task_workspace_path(
        env_id,
        task_id=task_id,
        data_dir=data_dir,
        location=source_location,
    )
    destination = task_workspace_path(
        env_id,
        task_id=task_id,
        data_dir=data_dir,
        location=destination_location,
    )

    if not os.path.exists(source):
        return WorkspaceMoveResult(
            source=source, destination=destination, moved=False, skipped=True
        )
    if os.path.islink(source) or not is_safe_task_workspace_path(
        source, data_dir=data_dir
    ):
        return WorkspaceMoveResult(
            source=source,
            destination=destination,
            moved=False,
            skipped=False,
            error="unsafe source workspace",
        )
    if os.path.exists(destination):
        return WorkspaceMoveResult(
            source=source, destination=destination, moved=False, skipped=True
        )
    if not is_safe_task_workspace_path(destination, data_dir=data_dir):
        return WorkspaceMoveResult(
            source=source,
            destination=destination,
            moved=False,
            skipped=False,
            error="unsafe destination workspace",
        )

    try:
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        if on_progress:
            on_progress(destination)
        try:
            os.replace(source, destination)
        except OSError:
            shutil.copytree(source, destination, symlinks=True)
            if not os.path.isdir(destination):
                raise RuntimeError("destination was not created")
            shutil.rmtree(source)
        return WorkspaceMoveResult(
            source=source, destination=destination, moved=True, skipped=False
        )
    except Exception as exc:
        return WorkspaceMoveResult(
            source=source,
            destination=destination,
            moved=False,
            skipped=False,
            error=str(exc),
        )


def finished_cutoff_s(*, retention_days: int, now_s: float | None = None) -> float:
    now = float(time.time() if now_s is None else now_s)
    return now - (max(1, int(retention_days)) * 86400.0)
