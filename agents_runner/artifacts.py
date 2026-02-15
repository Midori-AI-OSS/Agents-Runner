"""
Artifact encryption and management for agents-runner.

Provides secure storage of task artifacts with encryption based on task+environment hash.
Artifacts are stored in ~/.midoriai/agents-runner/artifacts/{task_id}/ with UUID4 filenames.
"""

from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
import multiprocessing
import queue
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from typing import cast
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


@dataclass
class ArtifactMeta:
    """Metadata for an encrypted artifact."""

    uuid: str
    original_filename: str
    mime_type: str
    encrypted_at: str
    size_bytes: int


@dataclass
class StagingArtifactMeta:
    """Metadata for a staging (unencrypted) artifact."""

    filename: str
    path: Path
    size_bytes: int
    modified_at: datetime
    mime_type: str


def get_artifact_key(task_dict: dict[str, Any], env_name: str) -> bytes:
    """
    Generate encryption key from task id and environment id.

    Args:
        task_dict: Task configuration as dictionary
        env_name: Environment identifier

    Returns:
        32-byte Fernet-compatible key (base64-encoded)
    """
    import base64

    # Create deterministic hash from task_id + environment_id.
    # Note: this intentionally ignores other task_dict fields to ensure the same
    # key is derived across UI/worker contexts.
    task_id = str(task_dict.get("task_id") or task_dict.get("id") or "")
    hasher = hashlib.sha256()
    hasher.update(task_id.encode("utf-8"))
    hasher.update(b"\0")
    hasher.update(str(env_name or "").encode("utf-8"))
    key_material = hasher.digest()

    # Fernet requires base64-encoded 32-byte key
    return base64.urlsafe_b64encode(key_material)


def _get_artifacts_dir(task_id: str) -> Path:
    """Get artifacts directory for a task, creating if needed."""
    artifacts_dir = Path.home() / ".midoriai" / "agents-runner" / "artifacts" / task_id
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return artifacts_dir


def encrypt_artifact(
    task_dict: dict[str, Any],
    env_name: str,
    source_path: str | Path,
    original_filename: str,
) -> str | None:
    """
    Encrypt and store an artifact file.

    Args:
        task_dict: Task configuration dictionary
        env_name: Environment name
        source_path: Path to file to encrypt
        original_filename: Original filename to store in metadata

    Returns:
        UUID string of encrypted artifact, or None on failure
    """
    source_path = Path(source_path)

    if not source_path.exists():
        logger.error(f"Source file not found: {source_path}")
        return None

    try:
        # Read source file
        source_data = source_path.read_bytes()

        # Generate encryption key
        key = get_artifact_key(task_dict, env_name)
        fernet = Fernet(key)

        # Encrypt data
        encrypted_data = fernet.encrypt(source_data)

        # Generate UUID for artifact
        artifact_uuid = str(uuid4())

        # Determine task_id from task_dict
        task_id = task_dict.get("id", task_dict.get("task_id", "default"))

        # Get artifacts directory
        artifacts_dir = _get_artifacts_dir(task_id)

        # Write encrypted file
        enc_path = artifacts_dir / f"{artifact_uuid}.enc"
        enc_path.write_bytes(encrypted_data)

        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(original_filename)
        if mime_type is None:
            mime_type = "application/octet-stream"

        # Create and write metadata
        metadata = {
            "uuid": artifact_uuid,
            "original_filename": original_filename,
            "mime_type": mime_type,
            "encrypted_at": datetime.now(timezone.utc).isoformat(),
            "size_bytes": len(source_data),
        }

        meta_path = artifacts_dir / f"{artifact_uuid}.meta"
        meta_path.write_text(json.dumps(metadata, indent=2))

        logger.info(f"Encrypted artifact {artifact_uuid}: {original_filename}")
        return artifact_uuid

    except Exception as e:
        logger.error(f"Failed to encrypt artifact: {e}", exc_info=True)
        return None


def decrypt_artifact(
    task_dict: dict[str, Any],
    env_name: str,
    artifact_uuid: str,
    dest_path: str | Path,
) -> bool:
    """
    Decrypt and restore an artifact file.

    Args:
        task_dict: Task configuration dictionary
        env_name: Environment name
        artifact_uuid: UUID of artifact to decrypt
        dest_path: Destination path for decrypted file

    Returns:
        True if successful, False otherwise
    """
    dest_path = Path(dest_path)

    try:
        # Determine task_id from task_dict
        task_id = task_dict.get("id", task_dict.get("task_id", "default"))

        # Get artifacts directory
        artifacts_dir = _get_artifacts_dir(task_id)

        # Check if encrypted file exists
        enc_path = artifacts_dir / f"{artifact_uuid}.enc"
        if not enc_path.exists():
            logger.error(f"Encrypted artifact not found: {artifact_uuid}")
            return False

        # Read encrypted data
        encrypted_data = enc_path.read_bytes()

        # Generate encryption key
        key = get_artifact_key(task_dict, env_name)
        fernet = Fernet(key)

        # Decrypt data
        try:
            decrypted_data = fernet.decrypt(encrypted_data)
        except InvalidToken:
            logger.error(f"Failed to decrypt artifact {artifact_uuid}: invalid key")
            return False

        # Ensure destination directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Write decrypted file
        dest_path.write_bytes(decrypted_data)

        logger.info(f"Decrypted artifact {artifact_uuid} to {dest_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to decrypt artifact: {e}", exc_info=True)
        return False


def list_artifacts(task_id: str) -> list[ArtifactMeta]:
    """
    List all artifacts for a task.

    Args:
        task_id: Task identifier

    Returns:
        List of artifact metadata objects
    """
    artifacts_dir = _get_artifacts_dir(task_id)

    if not artifacts_dir.exists():
        return []

    artifacts: list[ArtifactMeta] = []

    try:
        # Find all .meta files
        for meta_path in artifacts_dir.glob("*.meta"):
            try:
                metadata = json.loads(meta_path.read_text())

                # Validate required fields
                required_fields = [
                    "uuid",
                    "original_filename",
                    "mime_type",
                    "encrypted_at",
                    "size_bytes",
                ]
                if not all(field in metadata for field in required_fields):
                    logger.warning(f"Invalid metadata in {meta_path}")
                    continue

                artifact_meta = ArtifactMeta(
                    uuid=metadata["uuid"],
                    original_filename=metadata["original_filename"],
                    mime_type=metadata["mime_type"],
                    encrypted_at=metadata["encrypted_at"],
                    size_bytes=metadata["size_bytes"],
                )

                artifacts.append(artifact_meta)

            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse metadata {meta_path}: {e}")
                continue

    except Exception as e:
        logger.error(f"Failed to list artifacts for task {task_id}: {e}")

    return artifacts


def collect_artifacts_from_container(
    container_id: str, task_dict: dict[str, Any], env_name: str
) -> list[str]:
    """
    Collect artifacts from task's staging directory (already mounted to container).

    The staging directory is mounted as a volume to the container at /tmp/agents-artifacts,
    so files written by the agent are immediately available on the host. This function
    encrypts those files and moves them to permanent encrypted storage.

    Args:
        container_id: Docker container ID (unused, kept for API compatibility)
        task_dict: Task configuration as dictionary (must contain task_id)
        env_name: Environment name

    Returns:
        List of artifact UUIDs that were collected and encrypted
    """
    artifact_uuids: list[str] = []

    # Get task_id
    task_id = str(task_dict.get("task_id") or task_dict.get("id") or "")
    if not task_id:
        logger.warning("No task_id in task_dict, cannot collect artifacts")
        return []

    # Get staging directory (this was mounted to the container)
    artifacts_staging = get_staging_dir(task_id)

    if not artifacts_staging.exists():
        logger.debug(f"No staging directory found: {artifacts_staging}")
        return []

    try:
        files = [f for f in artifacts_staging.iterdir() if f.is_file()]

        if not files:
            logger.debug(f"No artifacts found in staging: {artifacts_staging}")
            return []

        logger.info(f"Found {len(files)} artifact(s) in staging directory")

        # Encrypt each file
        for file_path in files:
            try:
                artifact_uuid = encrypt_artifact(
                    task_dict, env_name, str(file_path), file_path.name
                )
                if artifact_uuid:
                    artifact_uuids.append(artifact_uuid)
                    logger.info(
                        f"Collected artifact: {file_path.name} -> {artifact_uuid}"
                    )
                    # Remove from staging after successful encryption
                    file_path.unlink()
            except Exception as e:
                logger.error(f"Failed to collect artifact {file_path.name}: {e}")
                continue

    except Exception as e:
        logger.error(f"Failed to collect artifacts from staging: {e}")

    finally:
        # ALWAYS clean up staging directory, even if encryption failed.
        # This is best-effort: log warnings, do not raise.

        # Robust recursive cleanup with retry/backoff to handle race conditions
        # with any active file watchers.
        delays_s = [0.0, 0.05, 0.1, 0.2, 0.4]
        last_exc: Exception | None = None
        for attempt, delay_s in enumerate(delays_s, start=1):
            if delay_s:
                time.sleep(delay_s)

            if not artifacts_staging.exists():
                last_exc = None
                break

            try:
                shutil.rmtree(artifacts_staging)
            except Exception as cleanup_exc:
                last_exc = cleanup_exc
                # Only warn on intermediate failures; log details on final failure below.
                logger.warning(
                    "Staging cleanup attempt %d/%d failed: %s",
                    attempt,
                    len(delays_s),
                    cleanup_exc,
                )
            else:
                logger.debug(f"Cleaned up staging directory: {artifacts_staging}")
                last_exc = None
                break

        if last_exc is not None and artifacts_staging.exists():
            logger.warning(f"Staging cleanup ultimately failed: {last_exc}")
            try:
                for entry in sorted(artifacts_staging.rglob("*"), key=str):
                    try:
                        stat = entry.lstat()
                        kind = (
                            "symlink"
                            if entry.is_symlink()
                            else "dir"
                            if entry.is_dir()
                            else "file"
                            if entry.is_file()
                            else "other"
                        )
                        logger.warning(
                            "Staging leftover: "
                            f"path={entry} kind={kind} size={stat.st_size} "
                            f"mode={oct(stat.st_mode)} mtime={stat.st_mtime}"
                        )
                    except Exception as entry_error:
                        logger.warning(
                            f"Staging leftover: path={entry} (failed to stat: {entry_error})"
                        )
            except Exception as list_error:
                logger.warning(
                    f"Staging cleanup failed while listing leftovers: {list_error}"
                )

    return artifact_uuids


def _collect_artifacts_child(
    result_q: multiprocessing.Queue[tuple[str, str | list[str]]],
    container_id: str,
    task_dict: dict[str, Any],
    env_name: str,
) -> None:
    try:
        artifact_uuids = collect_artifacts_from_container(
            container_id, task_dict, env_name
        )
        result_q.put(("ok", artifact_uuids))
    except Exception as exc:
        result_q.put(("err", f"{type(exc).__name__}: {exc}"))


def collect_artifacts_from_container_with_timeout(
    container_id: str,
    task_dict: dict[str, Any],
    env_name: str,
    *,
    timeout_s: float,
) -> list[str]:
    """
    Best-effort artifact collection with a hard timeout.

    Runs artifact collection in a child process so it can be terminated if it
    stalls (e.g., filesystem/IO hangs). On timeout, raises TimeoutError.
    """
    timeout_s = float(timeout_s)
    if timeout_s <= 0.0:
        raise ValueError("timeout_s must be > 0")

    ctx = multiprocessing.get_context("spawn")
    result_q: multiprocessing.Queue[tuple[str, str | list[str]]] = ctx.Queue()
    proc = ctx.Process(
        target=_collect_artifacts_child,
        args=(result_q, container_id, task_dict, env_name),
        daemon=True,
    )

    start = time.monotonic()
    proc.start()
    proc.join(timeout=timeout_s)

    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=2.0)
        if proc.is_alive():
            try:
                proc.kill()
            except Exception:
                pass
            proc.join(timeout=2.0)
        raise TimeoutError(
            f"artifact collection timed out after {timeout_s:.0f}s (elapsed {time.monotonic() - start:.1f}s)"
        )

    try:
        kind, payload = cast(tuple[str, object], result_q.get(timeout=1.0))
    except queue.Empty:
        exit_code = proc.exitcode
        raise RuntimeError(
            f"artifact collection process exited without result (exit_code={exit_code})"
        )
    finally:
        try:
            result_q.close()
            result_q.cancel_join_thread()
        except Exception:
            pass

    if kind == "ok":
        return cast(list[str], payload)
    raise RuntimeError(str(payload))


def get_staging_dir(task_id: str) -> Path:
    """
    Get path to staging directory for a task.

    Args:
        task_id: Task identifier

    Returns:
        Path to staging directory
    """
    artifacts_dir = _get_artifacts_dir(task_id)
    return artifacts_dir / "staging"


def list_staging_artifacts(task_id: str) -> list[StagingArtifactMeta]:
    """
    List artifacts in staging directory (for running tasks).

    Args:
        task_id: Task identifier

    Returns:
        List of staging artifact metadata
    """
    staging_dir = get_staging_dir(task_id)

    if not staging_dir.exists():
        return []

    artifacts: list[StagingArtifactMeta] = []

    try:
        for file_path in staging_dir.iterdir():
            if not file_path.is_file():
                continue

            stat = file_path.stat()
            mime_type, _ = mimetypes.guess_type(file_path.name)
            if mime_type is None:
                mime_type = "application/octet-stream"

            artifact = StagingArtifactMeta(
                filename=file_path.name,
                path=file_path,
                size_bytes=stat.st_size,
                modified_at=datetime.fromtimestamp(stat.st_mtime, timezone.utc),
                mime_type=mime_type,
            )
            artifacts.append(artifact)

        # Sort by modification time (newest first)
        artifacts.sort(key=lambda a: a.modified_at, reverse=True)

    except Exception as e:
        logger.error(f"Failed to list staging artifacts for task {task_id}: {e}")

    return artifacts


def get_staging_artifact_path(task_id: str, filename: str) -> Path | None:
    """
    Get path to a staging artifact (for direct access).

    Args:
        task_id: Task identifier
        filename: Artifact filename

    Returns:
        Path to staging file, or None if not found
    """
    staging_dir = get_staging_dir(task_id)
    file_path = staging_dir / filename

    if file_path.exists() and file_path.is_file():
        # Security: Verify file is within staging directory (prevent path traversal)
        try:
            if file_path.resolve().parent != staging_dir.resolve():
                logger.error(f"Path traversal attempt: {filename}")
                return None
        except Exception as e:
            logger.error(f"Failed to resolve path {filename}: {e}")
            return None
        return file_path

    return None


@dataclass
class ArtifactInfo:
    """Single source of truth for artifact locations and status."""

    host_artifacts_dir: Path
    container_artifacts_dir: str
    file_count: int
    exists: bool


def get_artifact_info(task_id: str) -> ArtifactInfo:
    """
    Get single source of truth for artifact status.

    Returns information about artifact storage for a task, prioritizing
    the host staging directory as the truth during execution and encrypted
    storage after finalization.

    Args:
        task_id: Task identifier

    Returns:
        ArtifactInfo with paths, counts, and existence status
    """
    # Host staging directory is the truth during execution
    staging_dir = get_staging_dir(task_id)

    # Count files in staging directory
    file_count = 0
    exists = staging_dir.exists()

    if exists:
        try:
            file_count = sum(1 for f in staging_dir.iterdir() if f.is_file())
        except Exception as e:
            logger.debug(f"Failed to count files in {staging_dir}: {e}")
            file_count = 0

    return ArtifactInfo(
        host_artifacts_dir=staging_dir,
        container_artifacts_dir="/tmp/agents-artifacts/",
        file_count=file_count,
        exists=exists,
    )
