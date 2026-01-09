"""Docker image builder for caching desktop environment setup.

This module provides utilities to pre-build Docker images with desktop components
installed, allowing for faster task startup times by reusing cached images.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from agents_runner.docker.process import _run_docker
from agents_runner.docker.process import _has_image

logger = logging.getLogger(__name__)

# Default paths to desktop scripts
DESKTOP_INSTALL_SCRIPT = Path(__file__).parent.parent / "preflights" / "desktop_install.sh"
DESKTOP_SETUP_SCRIPT = Path(__file__).parent.parent / "preflights" / "desktop_setup.sh"


def _compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of a file.
    
    Args:
        file_path: Path to the file to hash
        
    Returns:
        Hex digest of the file's SHA256 hash
        
    Raises:
        FileNotFoundError: If the file does not exist
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Script not found: {file_path}")
    
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()[:16]


def _get_base_image_digest(base_image: str) -> str:
    """Get the digest of a base image.
    
    Args:
        base_image: Name of the base Docker image
        
    Returns:
        Short digest (first 16 chars) of the image ID
        
    Raises:
        RuntimeError: If docker inspect fails
    """
    try:
        raw = _run_docker(["image", "inspect", base_image], timeout_s=30.0)
        payload = json.loads(raw)
        if payload and len(payload) > 0:
            image_id = payload[0].get("Id", "")
            # Strip 'sha256:' prefix if present
            if image_id.startswith("sha256:"):
                image_id = image_id[7:]
            return image_id[:16]
    except Exception as exc:
        logger.warning(f"Failed to get image digest for {base_image}: {exc}")
    
    # Fallback to image name hash if inspect fails
    return hashlib.sha256(base_image.encode()).hexdigest()[:16]


def compute_desktop_cache_key(base_image: str) -> str:
    """Compute cache key for desktop image.
    
    The cache key is based on:
    - Base image digest
    - Hash of desktop_install.sh
    - Hash of desktop_setup.sh
    - Hash of Dockerfile template
    
    Args:
        base_image: Name of the base Docker image
        
    Returns:
        Cache key string (e.g., "emerald-abc123-def456-789012-ghi345")
    """
    try:
        base_digest = _get_base_image_digest(base_image)
    except Exception as exc:
        logger.warning(f"Failed to get base image digest: {exc}, using fallback")
        base_digest = "unknown"
    
    try:
        install_hash = _compute_file_hash(DESKTOP_INSTALL_SCRIPT)
    except Exception as exc:
        logger.warning(f"Failed to hash desktop_install.sh: {exc}")
        install_hash = "missing"
    
    try:
        setup_hash = _compute_file_hash(DESKTOP_SETUP_SCRIPT)
    except Exception as exc:
        logger.warning(f"Failed to hash desktop_setup.sh: {exc}")
        setup_hash = "missing"
    
    # Dockerfile template hash (inline template, hash the template string)
    dockerfile_template = _get_dockerfile_template()
    dockerfile_hash = hashlib.sha256(dockerfile_template.encode()).hexdigest()[:16]
    
    return f"emerald-{base_digest}-{install_hash}-{setup_hash}-{dockerfile_hash}"


def _get_dockerfile_template() -> str:
    """Get the Dockerfile template for building desktop image.
    
    Returns:
        Dockerfile template as a string
    """
    return """FROM {base_image}

# Copy desktop installation scripts
COPY desktop_install.sh /tmp/desktop_install.sh
COPY desktop_setup.sh /tmp/desktop_setup.sh

# Switch to root for system-level operations
USER root

# Run installation and setup
RUN /bin/bash /tmp/desktop_install.sh && /bin/bash /tmp/desktop_setup.sh && rm -f /tmp/desktop_install.sh /tmp/desktop_setup.sh

# Switch back to non-root user for runtime security
USER midori-ai

# Desktop environment is now ready
"""


def build_desktop_image(
    base_image: str,
    tag: str,
    *,
    on_log: Callable[[str], None] | None = None,
) -> None:
    """Build a Docker image with desktop components pre-installed.
    
    Args:
        base_image: Base image to build from
        tag: Tag for the new image
        on_log: Optional callback for logging messages
        
    Raises:
        RuntimeError: If the build fails
        FileNotFoundError: If required scripts are missing
    """
    if on_log is None:
        on_log = logger.info
    
    # Validate that required scripts exist
    if not DESKTOP_INSTALL_SCRIPT.exists():
        raise FileNotFoundError(f"Desktop install script not found: {DESKTOP_INSTALL_SCRIPT}")
    if not DESKTOP_SETUP_SCRIPT.exists():
        raise FileNotFoundError(f"Desktop setup script not found: {DESKTOP_SETUP_SCRIPT}")
    
    on_log(f"[image-builder] building desktop image: {tag}")
    on_log(f"[image-builder] base image: {base_image}")
    
    # Create temporary directory for build context
    with tempfile.TemporaryDirectory() as build_dir:
        build_path = Path(build_dir)
        
        # Copy scripts to build context
        import shutil
        shutil.copy(DESKTOP_INSTALL_SCRIPT, build_path / "desktop_install.sh")
        shutil.copy(DESKTOP_SETUP_SCRIPT, build_path / "desktop_setup.sh")
        
        # Write Dockerfile
        dockerfile_content = _get_dockerfile_template().format(base_image=base_image)
        dockerfile_path = build_path / "Dockerfile"
        dockerfile_path.write_text(dockerfile_content, encoding="utf-8")
        
        on_log(f"[image-builder] build context prepared in {build_dir}")
        
        # Build image
        try:
            build_args = [
                "build",
                "-t", tag,
                "-f", str(dockerfile_path),
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
                        on_log(f"[image-builder] {line}")
            
            # Wait for completion
            return_code = process.wait(timeout=600.0)  # 10 minute timeout
            
            if return_code != 0:
                raise RuntimeError(f"Docker build failed with exit code {return_code}")
            
            on_log(f"[image-builder] successfully built: {tag}")
            
        except subprocess.TimeoutExpired:
            process.kill()
            raise RuntimeError("Docker build timed out after 10 minutes")
        except Exception as exc:
            raise RuntimeError(f"Failed to build desktop image: {exc}") from exc


def ensure_desktop_image(
    base_image: str,
    *,
    on_log: Callable[[str], None] | None = None,
) -> str:
    """Ensure desktop image exists, building if necessary.
    
    This function checks if a cached desktop image already exists. If it does,
    it returns the cached image name. Otherwise, it builds a new image.
    
    Args:
        base_image: Base image to build from (e.g., "lunamidori5/pixelarch:emerald")
        on_log: Optional callback for logging messages
        
    Returns:
        Name of the desktop image to use (either base_image or cached image)
        
    Note:
        On build failure, falls back to base_image for runtime installation.
    """
    if on_log is None:
        on_log = logger.info
    
    try:
        cache_key = compute_desktop_cache_key(base_image)
        cached_image_tag = f"agent-runner-desktop:{cache_key}"
        
        on_log(f"[image-builder] checking for cached desktop image: {cached_image_tag}")
        
        # Check if cached image exists
        if _has_image(cached_image_tag):
            on_log(f"[image-builder] cache HIT: reusing existing image")
            return cached_image_tag
        
        # Cache miss - need to build
        on_log(f"[image-builder] cache MISS: building new image")
        on_log(f"[image-builder] cache key: {cache_key}")
        
        # Build the image
        build_desktop_image(base_image, cached_image_tag, on_log=on_log)
        
        return cached_image_tag
        
    except Exception as exc:
        # Log error but don't fail - fall back to runtime installation
        on_log(f"[image-builder] ERROR: {exc}")
        on_log(f"[image-builder] falling back to runtime desktop installation")
        logger.exception("Failed to build desktop image, falling back to runtime install")
        return base_image
