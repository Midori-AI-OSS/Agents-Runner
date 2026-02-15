"""Docker image builder for caching environment-specific preflight setup.

This module provides utilities to pre-build Docker images with environment-specific
preflight scripts executed at build time, allowing for faster task startup times by
reusing cached images with pre-installed dependencies.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from agents_runner.docker.process import run_docker
from agents_runner.docker.process import has_image
from agents_runner.log_format import format_log

logger = logging.getLogger(__name__)


def _compute_content_hash(content: str) -> str:
    """Compute SHA256 hash of a string.

    Args:
        content: String content to hash

    Returns:
        Hex digest of the content's SHA256 hash (first 16 chars)
    """
    sha256 = hashlib.sha256()
    sha256.update(content.encode("utf-8"))
    return sha256.hexdigest()[:16]


def _get_base_image_digest(base_image: str) -> str:
    """Get the digest of a base image.

    Args:
        base_image: Name of the base Docker image

    Returns:
        Short digest (first 16 chars) of the image ID
    """
    try:
        raw = run_docker(["image", "inspect", base_image], timeout_s=30.0)
        payload = json.loads(raw)
        if payload and len(payload) > 0:
            image_id = payload[0].get("Id", "")
            # Strip 'sha256:' prefix if present
            if image_id.startswith("sha256:"):
                image_id = image_id[7:]
            return image_id[:16]
    except Exception as exc:
        logger.warning(
            format_log(
                "env",
                "image",
                "WARN",
                f"Failed to get image digest for {base_image}: {exc}",
            )
        )

    # Fallback to image name hash if inspect fails
    return hashlib.sha256(base_image.encode()).hexdigest()[:16]


def compute_env_cache_key(base_image_or_key: str, cached_preflight: str) -> str:
    """Compute cache key for environment image.

    The cache key is based on:
    - Base image digest or desktop cache key
    - Hash of cached_preflight_script

    Args:
        base_image_or_key: Base image name or desktop cache key
        cached_preflight: Cached preflight script content

    Returns:
        Cache key string (e.g., "abc123-def456")
    """
    # Determine if input is a cache key (contains '-') or an image name
    if "-" in base_image_or_key and base_image_or_key.startswith("emerald-"):
        # Already a cache key (from desktop image)
        base_key = base_image_or_key
    else:
        # It's an image name - get its digest
        try:
            base_digest = _get_base_image_digest(base_image_or_key)
        except Exception as exc:
            logger.warning(
                format_log(
                    "env",
                    "image",
                    "WARN",
                    f"Failed to get base image digest: {exc}, using fallback",
                )
            )
            base_digest = hashlib.sha256(base_image_or_key.encode()).hexdigest()[:16]
        base_key = base_digest

    # Hash the cached preflight script
    preflight_hash = _compute_content_hash(cached_preflight or "")

    return f"{base_key}-{preflight_hash}"


def _get_dockerfile_template() -> str:
    """Get the Dockerfile template for building environment image.

    Returns:
        Dockerfile template as a string
    """
    return """FROM {base_image}

# Copy cached preflight script
COPY cached_preflight.sh /tmp/cached_preflight.sh

# Run cached preflight at build time
RUN /bin/bash /tmp/cached_preflight.sh && sudo rm -f /tmp/cached_preflight.sh

# Environment-specific setup is now cached
"""


def build_env_image(
    base_image: str,
    tag: str,
    cached_preflight: str,
    *,
    on_log: Callable[[str], None] | None = None,
) -> None:
    """Build a Docker image with cached preflight script executed.

    Args:
        base_image: Base image to build from (can be desktop image)
        tag: Tag for the new image
        cached_preflight: Cached preflight script content
        on_log: Optional callback for logging messages

    Raises:
        RuntimeError: If the build fails
    """
    if on_log is None:
        on_log = logger.info

    on_log(format_log("env", "build", "INFO", f"building environment image: {tag}"))
    on_log(format_log("env", "build", "INFO", f"base image: {base_image}"))

    # Create temporary directory for build context
    with tempfile.TemporaryDirectory() as build_dir:
        build_path = Path(build_dir)

        # Write cached preflight script to build context
        preflight_path = build_path / "cached_preflight.sh"
        preflight_path.write_text(cached_preflight or "", encoding="utf-8")

        # Write Dockerfile
        dockerfile_content = _get_dockerfile_template().format(base_image=base_image)
        dockerfile_path = build_path / "Dockerfile"
        dockerfile_path.write_text(dockerfile_content, encoding="utf-8")

        on_log(
            format_log("env", "build", "INFO", f"build context prepared in {build_dir}")
        )

        # Build image
        process = None
        try:
            build_args = [
                "build",
                "-t",
                tag,
                "-f",
                str(dockerfile_path),
                str(build_path),
            ]

            # Run docker build with streaming output
            process = subprocess.Popen(
                ["docker", *build_args],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            # Stream output
            if process.stdout:
                for line in process.stdout:
                    line = line.rstrip()
                    if line:
                        on_log(format_log("env", "build", "INFO", line))

            # Wait for completion
            return_code = process.wait(timeout=600.0)  # 10 minute timeout

            if return_code != 0:
                raise RuntimeError(f"Docker build failed with exit code {return_code}")

            on_log(format_log("env", "build", "INFO", f"successfully built: {tag}"))

        except subprocess.TimeoutExpired:
            if process is not None:
                process.kill()
            raise RuntimeError("Docker build timed out after 10 minutes")
        except Exception as exc:
            raise RuntimeError(f"Failed to build environment image: {exc}") from exc


def ensure_env_image(
    base_image: str,
    desktop_key: str | None,
    cached_preflight: str,
    *,
    on_log: Callable[[str], None] | None = None,
) -> str:
    """Ensure environment image exists, building if necessary.

    This function checks if a cached environment image already exists. If it does,
    it returns the cached image name. Otherwise, it builds a new image.

    Args:
        base_image: Base image name (e.g., "lunamidori5/pixelarch:emerald")
        desktop_key: Desktop cache key if desktop caching is enabled, None otherwise
        cached_preflight: Cached preflight script content
        on_log: Optional callback for logging messages

    Returns:
        Name of the environment image to use

    Note:
        On build failure, falls back to base_image for runtime installation.
    """
    if on_log is None:
        on_log = logger.info

    # If no cached preflight, return the base image
    if not (cached_preflight or "").strip():
        on_log(
            format_log(
                "env", "image", "INFO", "no cached preflight script; skipping env cache"
            )
        )
        return base_image

    try:
        # Determine the actual base image to use
        if desktop_key:
            # Use desktop image as base
            actual_base = f"agent-runner-desktop:{desktop_key}"
            on_log(
                format_log(
                    "env",
                    "image",
                    "INFO",
                    f"using desktop image as base: {actual_base}",
                )
            )
            base_key_for_hash = desktop_key
        else:
            # Use original base image
            actual_base = base_image
            base_key_for_hash = base_image

        # Compute cache key
        cache_key = compute_env_cache_key(base_key_for_hash, cached_preflight)
        cached_image_tag = f"agent-runner-env:{cache_key}"

        on_log(
            format_log(
                "env",
                "image",
                "INFO",
                f"checking for cached environment image: {cached_image_tag}",
            )
        )

        # Check if cached image exists
        if has_image(cached_image_tag):
            on_log(
                format_log("env", "image", "INFO", "cache HIT: reusing existing image")
            )
            return cached_image_tag

        # Cache miss - need to build
        on_log(format_log("env", "image", "INFO", "cache MISS: building new image"))
        on_log(format_log("env", "image", "INFO", f"cache key: {cache_key}"))

        # Build the image
        build_env_image(actual_base, cached_image_tag, cached_preflight, on_log=on_log)

        return cached_image_tag

    except Exception as exc:
        # Log error but don't fail - fall back to runtime installation
        on_log(format_log("env", "image", "ERROR", str(exc)))
        on_log(
            format_log(
                "env", "image", "WARN", "falling back to runtime preflight execution"
            )
        )
        logger.exception(
            format_log(
                "env",
                "image",
                "ERROR",
                "Failed to build environment image, falling back to runtime",
            )
        )
        return base_image
