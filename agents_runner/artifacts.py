"""
Artifact encryption and management for agents-runner.

Provides secure storage of task artifacts with encryption based on task+environment hash.
Artifacts are stored in ~/.midoriai/agents-runner/artifacts/{task_id}/ with UUID4 filenames.
"""

import hashlib
import json
import logging
import mimetypes
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
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
    artifacts_staging = (
        Path.home() / ".midoriai" / "agents-runner" / "artifacts" 
        / task_id / "staging"
    )
    
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
                    logger.info(f"Collected artifact: {file_path.name} -> {artifact_uuid}")
                    # Remove from staging after successful encryption
                    file_path.unlink()
            except Exception as e:
                logger.error(f"Failed to collect artifact {file_path.name}: {e}")
                continue
        
        # Clean up staging directory if empty
        try:
            if not any(artifacts_staging.iterdir()):
                artifacts_staging.rmdir()
                logger.debug(f"Removed empty staging directory: {artifacts_staging}")
        except Exception as e:
            logger.debug(f"Could not remove staging directory: {e}")
            
    except Exception as e:
        logger.error(f"Failed to collect artifacts from staging: {e}")
    
    return artifact_uuids
