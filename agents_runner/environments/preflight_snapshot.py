from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken

from .model import WORKSPACE_CLONED
from .model import WORKSPACE_MOUNTED
from .model import WORKSPACE_NONE


def normalize_setup_agents_script_text(text: str) -> str:
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    if normalized and not normalized.endswith("\n"):
        normalized += "\n"
    return normalized


def normalize_setup_agents_snapshot_hash(value: object) -> str:
    token = str(value or "").strip().lower()
    if len(token) != 64:
        return ""
    if any(ch not in "0123456789abcdef" for ch in token):
        return ""
    return token


def _normalize_repo_identity(target: str) -> str:
    text = str(target or "").strip()
    if not text:
        return ""
    if text.startswith("git@github.com:"):
        text = text.removeprefix("git@github.com:").strip()
    elif "github.com/" in text:
        text = text.split("github.com/", 1)[-1].strip()
    text = text.split("#", 1)[0].split("?", 1)[0].strip().strip("/")
    if text.endswith(".git"):
        text = text[: -len(".git")].strip().strip("/")
    parts = [part for part in text.split("/") if part]
    if len(parts) >= 2:
        return f"{parts[-2].lower()}/{parts[-1].lower()}"
    return text.lower()


def _workspace_identity_baseline(
    *,
    workspace_type: str,
    workspace_target: str,
    host_workdir: str,
) -> str:
    normalized_type = str(workspace_type or WORKSPACE_NONE).strip().lower()
    target = str(workspace_target or "").strip()
    legacy_workdir = str(host_workdir or "").strip()

    if normalized_type == WORKSPACE_MOUNTED:
        identity = os.path.abspath(os.path.expanduser(target)) if target else ""
    elif normalized_type == WORKSPACE_CLONED:
        identity = _normalize_repo_identity(target)
    else:
        identity = (
            os.path.abspath(os.path.expanduser(legacy_workdir))
            if legacy_workdir
            else ""
        )
    return f"{normalized_type}\0{identity}"


def build_preflight_identity_token(
    *,
    env_id: str,
    workspace_type: str,
    workspace_target: str,
    host_workdir: str,
) -> str:
    hasher = hashlib.sha256()
    hasher.update(str(env_id or "").encode("utf-8"))
    hasher.update(b"\0")
    baseline = _workspace_identity_baseline(
        workspace_type=workspace_type,
        workspace_target=workspace_target,
        host_workdir=host_workdir,
    )
    hasher.update(baseline.encode("utf-8"))
    return hasher.hexdigest()


def derive_setup_agents_snapshot_key(*, env_id: str, identity_token: str) -> bytes:
    hasher = hashlib.sha256()
    hasher.update(str(env_id or "").encode("utf-8"))
    hasher.update(b"\0")
    hasher.update(str(identity_token or "").encode("utf-8"))
    key_material = hasher.digest()
    return base64.urlsafe_b64encode(key_material)


def setup_agents_snapshot_hash(plaintext: str) -> str:
    normalized = normalize_setup_agents_script_text(plaintext)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def encrypt_setup_agents_snapshot(
    *,
    env_id: str,
    identity_token: str,
    plaintext: str,
) -> tuple[str, str]:
    normalized = normalize_setup_agents_script_text(plaintext)
    key = derive_setup_agents_snapshot_key(
        env_id=env_id,
        identity_token=identity_token,
    )
    ciphertext = Fernet(key).encrypt(normalized.encode("utf-8")).decode("utf-8")
    return ciphertext, setup_agents_snapshot_hash(normalized)


def decrypt_setup_agents_snapshot(
    *,
    env_id: str,
    identity_token: str,
    ciphertext: str,
    expected_hash: str = "",
) -> str | None:
    env = str(env_id or "").strip()
    token = str(identity_token or "").strip()
    payload = str(ciphertext or "").strip()
    if not env or not token or not payload:
        return None
    key = derive_setup_agents_snapshot_key(env_id=env, identity_token=token)
    try:
        plaintext = Fernet(key).decrypt(payload.encode("utf-8")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, ValueError):
        return None

    normalized = normalize_setup_agents_script_text(plaintext)
    expected = normalize_setup_agents_snapshot_hash(expected_hash)
    if expected and setup_agents_snapshot_hash(normalized) != expected:
        return None
    return normalized
