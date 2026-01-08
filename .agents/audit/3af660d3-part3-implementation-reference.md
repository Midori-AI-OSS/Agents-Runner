# Part 3 Implementation Reference: Code Snippets

**Audit ID:** 3af660d3  
**Related:** 3af660d3-part3-container-caching-analysis.audit.md

This document provides ready-to-use code snippets for implementing Part 3.

---

## 1. Environment Model Updates

**File:** `agents_runner/environments/model.py`

```python
@dataclass
class Environment:
    env_id: str
    name: str
    color: str = "emerald"
    host_workdir: str = ""
    host_codex_dir: str = ""
    agent_cli_args: str = ""
    max_agents_running: int = -1
    headless_desktop_enabled: bool = False
    
    # Desktop caching (Part 2)
    cache_desktop_build: bool = False
    
    # Container caching (Part 3 - NEW)
    cache_container_build: bool = False
    cached_preflight_script: str = ""
    run_preflight_script: str = ""
    
    # Legacy single preflight (keep for backward compatibility)
    preflight_enabled: bool = False
    preflight_script: str = ""
    
    env_vars: dict[str, str] = field(default_factory=dict)
    extra_mounts: list[str] = field(default_factory=list)
    gh_management_mode: str = GH_MANAGEMENT_NONE
    gh_management_target: str = ""
    gh_management_locked: bool = False
    gh_last_base_branch: str = ""
    gh_use_host_cli: bool = True
    gh_context_enabled: bool = False
    prompts: list[PromptConfig] = field(default_factory=list)
    prompts_unlocked: bool = False
    agent_selection: AgentSelection | None = None
    _cached_is_git_repo: bool | None = None
```

---

## 2. Docker Config Updates

**File:** `agents_runner/docker/config.py`

```python
@dataclass(frozen=True)
class DockerRunnerConfig:
    task_id: str
    image: str
    host_codex_dir: str
    host_workdir: str
    agent_cli: str = "codex"
    container_codex_dir: str = "/home/midori-ai/.codex"
    container_workdir: str = "/home/midori-ai/workspace"
    auto_remove: bool = True
    pull_before_run: bool = True
    
    # Desktop caching (Part 2)
    headless_desktop_enabled: bool = False
    desktop_cache_enabled: bool = False
    
    # Container caching (Part 3 - NEW)
    container_cache_enabled: bool = False
    cached_preflight_script: str | None = None
    run_preflight_script: str | None = None
    
    # Legacy single preflight (keep for backward compatibility)
    settings_preflight_script: str | None = None
    environment_preflight_script: str | None = None
    
    environment_id: str = ""
    container_settings_preflight_path: str = (
        "/tmp/agents-runner-preflight-settings-{task_id}.sh"
    )
    container_environment_preflight_path: str = (
        "/tmp/agents-runner-preflight-environment-{task_id}.sh"
    )
    container_run_preflight_path: str = (
        "/tmp/agents-runner-preflight-run-{task_id}.sh"
    )
    env_vars: dict[str, str] = field(default_factory=dict)
    extra_mounts: list[str] = field(default_factory=list)
    agent_cli_args: list[str] = field(default_factory=list)
    gh_repo: str | None = None
    gh_prefer_gh_cli: bool = True
    gh_recreate_if_needed: bool = True
    gh_base_branch: str | None = None
    gh_context_file_path: str | None = None
    artifact_collection_timeout_s: float = 30.0
```

---

## 3. Environment Image Builder

**New File:** `agents_runner/docker/env_image_builder.py`

```python
"""Docker environment image builder for caching preflight setup.

This module provides utilities to pre-build Docker images with environment
preflight scripts executed, allowing for faster task startup times by reusing
cached images with pre-installed packages and configuration.
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
from agents_runner.docker.image_builder import _get_base_image_digest
from agents_runner.docker.image_builder import compute_desktop_cache_key
from agents_runner.docker.image_builder import ensure_desktop_image

logger = logging.getLogger(__name__)


def compute_env_cache_key(
    base_image_key: str,
    cached_preflight_script: str,
) -> str:
    """Compute cache key for environment image.
    
    The cache key is based on:
    - Base image key (desktop key if desktop caching ON, else pixelarch digest)
    - Hash of cached_preflight_script
    - Hash of Dockerfile template
    
    Args:
        base_image_key: Either desktop cache key or base image digest
        cached_preflight_script: Script to run at build time
        
    Returns:
        Cache key string (e.g., "emerald-abc123-xyz789-def456")
    """
    # Hash the cached preflight script
    script_hash = hashlib.sha256(
        cached_preflight_script.encode()
    ).hexdigest()[:16]
    
    # Hash the Dockerfile template
    dockerfile_template = _get_env_dockerfile_template()
    dockerfile_hash = hashlib.sha256(
        dockerfile_template.encode()
    ).hexdigest()[:16]
    
    return f"{base_image_key}-{script_hash}-{dockerfile_hash}"


def _get_env_dockerfile_template() -> str:
    """Get the Dockerfile template for building environment image.
    
    Returns:
        Dockerfile template as a string
    """
    return """FROM {base_image}

# Copy cached preflight script
COPY cached_preflight.sh /tmp/cached_preflight.sh

# Run cached preflight at build time
RUN chmod +x /tmp/cached_preflight.sh && \\
    /tmp/cached_preflight.sh && \\
    rm -f /tmp/cached_preflight.sh

# Environment is now ready with cached setup
"""


def build_env_image(
    base_image: str,
    tag: str,
    cached_preflight_script: str,
    *,
    on_log: Callable[[str], None] | None = None,
) -> None:
    """Build a Docker image with cached preflight executed.
    
    Args:
        base_image: Base image to build from (pixelarch or desktop image)
        tag: Tag for the new image (e.g., agent-runner-env:<key>)
        cached_preflight_script: Script to execute at build time
        on_log: Optional callback for logging messages
        
    Raises:
        RuntimeError: If the build fails
        ValueError: If cached_preflight_script is empty
    """
    if on_log is None:
        on_log = logger.info
    
    # Validate cached preflight script
    if not cached_preflight_script.strip():
        raise ValueError("cached_preflight_script cannot be empty")
    
    on_log(f"[env-builder] building environment image: {tag}")
    on_log(f"[env-builder] base image: {base_image}")
    
    # Create temporary directory for build context
    with tempfile.TemporaryDirectory() as build_dir:
        build_path = Path(build_dir)
        
        # Write cached preflight script
        script_path = build_path / "cached_preflight.sh"
        script_path.write_text(cached_preflight_script, encoding="utf-8")
        
        # Write Dockerfile
        dockerfile_content = _get_env_dockerfile_template().format(
            base_image=base_image
        )
        dockerfile_path = build_path / "Dockerfile"
        dockerfile_path.write_text(dockerfile_content, encoding="utf-8")
        
        on_log(f"[env-builder] build context prepared in {build_dir}")
        
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
                        on_log(f"[env-builder] {line}")
            
            # Wait for completion
            return_code = process.wait(timeout=600.0)  # 10 minute timeout
            
            if return_code != 0:
                raise RuntimeError(
                    f"Docker build failed with exit code {return_code}"
                )
            
            on_log(f"[env-builder] successfully built: {tag}")
            
        except subprocess.TimeoutExpired:
            process.kill()
            raise RuntimeError("Docker build timed out after 10 minutes")
        except Exception as exc:
            raise RuntimeError(f"Failed to build environment image: {exc}") from exc


def ensure_env_image(
    base_image: str,
    cached_preflight_script: str,
    desktop_enabled: bool,
    desktop_cached: bool,
    *,
    on_log: Callable[[str], None] | None = None,
) -> str:
    """Ensure environment image exists, building if necessary.
    
    This orchestrates the layered build:
    1. If desktop caching ON: ensure desktop image exists first
    2. Compute env cache key based on base layer
    3. Check if env image exists, build if not
    4. Return final image name to use
    
    Args:
        base_image: Original base image (e.g., "lunamidori5/pixelarch:emerald")
        cached_preflight_script: Script to execute at build time
        desktop_enabled: Whether headless desktop is enabled
        desktop_cached: Whether desktop should be cached
        on_log: Optional callback for logging messages
        
    Returns:
        Name of the environment image to use (either cached or fallback)
        
    Note:
        On build failure, falls back to base_image for runtime execution.
    """
    if on_log is None:
        on_log = logger.info
    
    try:
        # Step 1: Determine base for env image
        if desktop_enabled and desktop_cached:
            # Build/get desktop image first
            on_log("[env-builder] desktop caching enabled; ensuring desktop image")
            desktop_image = ensure_desktop_image(base_image, on_log=on_log)
            env_base = desktop_image
            
            # Use desktop cache key as base key
            if desktop_image != base_image:
                # Successfully got desktop image, use its key
                desktop_key = compute_desktop_cache_key(base_image)
                base_key = f"desktop-{desktop_key}"
                on_log(f"[env-builder] layering on desktop image: {desktop_image}")
            else:
                # Desktop image build failed, fall back to pixelarch
                base_key = f"emerald-{_get_base_image_digest(base_image)}"
                on_log("[env-builder] desktop build failed; using base image")
        else:
            env_base = base_image
            base_key = f"emerald-{_get_base_image_digest(base_image)}"
            on_log(f"[env-builder] building from base image: {base_image}")
        
        # Step 2: Compute env cache key
        env_cache_key = compute_env_cache_key(base_key, cached_preflight_script)
        env_image_tag = f"agent-runner-env:{env_cache_key}"
        
        on_log(f"[env-builder] checking for cached env image: {env_image_tag}")
        
        # Step 3: Check if cached image exists
        if _has_image(env_image_tag):
            on_log(f"[env-builder] cache HIT: reusing existing image")
            return env_image_tag
        
        # Cache miss - need to build
        on_log(f"[env-builder] cache MISS: building new image")
        on_log(f"[env-builder] cache key: {env_cache_key}")
        
        # Step 4: Build the env image
        build_env_image(
            env_base,
            env_image_tag,
            cached_preflight_script,
            on_log=on_log,
        )
        
        return env_image_tag
        
    except Exception as exc:
        # Log error but don't fail - fall back to runtime execution
        on_log(f"[env-builder] ERROR: {exc}")
        on_log(f"[env-builder] falling back to runtime preflight execution")
        logger.exception("Failed to build environment image, falling back to runtime")
        return base_image
```

---

## 4. Agent Worker Updates

**File:** `agents_runner/docker/agent_worker.py`

### 4.1 Add Container Caching Logic (after line 257)

```python
# EXISTING: Desktop caching (Part 2)
runtime_image = self._config.image
desktop_enabled = bool(self._config.headless_desktop_enabled)
desktop_cached = bool(self._config.desktop_cache_enabled)

if desktop_enabled and desktop_cached:
    # Try to use/build cached desktop image
    self._on_log("[desktop] cache enabled; checking for cached image")
    try:
        runtime_image = ensure_desktop_image(
            self._config.image,
            on_log=self._on_log,
        )
        if runtime_image != self._config.image:
            self._on_log(f"[desktop] using cached image: {runtime_image}")
        else:
            self._on_log("[desktop] cache build failed; falling back to runtime install")
    except Exception as exc:
        self._on_log(f"[desktop] cache error: {exc}; falling back to runtime install")
        runtime_image = self._config.image

# NEW: Container caching (Part 3)
container_cached = bool(self._config.container_cache_enabled)
cached_preflight = (self._config.cached_preflight_script or "").strip()

if container_cached and cached_preflight:
    self._on_log("[env-cache] container caching enabled")
    try:
        from agents_runner.docker.env_image_builder import ensure_env_image
        
        # This handles layered building internally
        runtime_image = ensure_env_image(
            base_image=self._config.image,  # Original pixelarch image
            cached_preflight_script=cached_preflight,
            desktop_enabled=desktop_enabled,
            desktop_cached=desktop_cached,
            on_log=self._on_log,
        )
        
        if runtime_image != self._config.image:
            self._on_log(f"[env-cache] using cached image: {runtime_image}")
        else:
            self._on_log("[env-cache] cache build failed; falling back to runtime")
    except Exception as exc:
        self._on_log(f"[env-cache] error: {exc}; falling back to runtime")
        # runtime_image stays as current value (desktop or base)
```

### 4.2 Update Preflight Clause Building (replace lines 382-397)

```python
# NEW: Run preflight (Part 3)
run_preflight_tmp_path: str | None = None
run_container_path = (
    self._config.container_run_preflight_path.replace(
        "{task_id}", task_token
    )
)

if (self._config.run_preflight_script or "").strip():
    run_preflight_tmp_path = _write_preflight_script(
        str(self._config.run_preflight_script or ""),
        "run",
        self._config.task_id,
        preflight_tmp_paths,
    )

if run_preflight_tmp_path is not None:
    self._on_log(
        f"[host] run preflight enabled; mounting -> {run_container_path} (ro)"
    )
    preflight_mounts.extend(
        [
            "-v",
            f"{run_preflight_tmp_path}:{run_container_path}:ro",
        ]
    )
    preflight_clause += (
        f"PREFLIGHT_RUN={shlex.quote(run_container_path)}; "
        'echo "[preflight] run: running"; '
        '/bin/bash "${PREFLIGHT_RUN}"; '
        'echo "[preflight] run: done"; '
    )

# BACKWARD COMPATIBILITY: Legacy single environment preflight
# Only used if new run_preflight not specified
if not run_preflight_tmp_path:
    environment_preflight_tmp_path: str | None = None
    environment_container_path = (
        self._config.container_environment_preflight_path.replace(
            "{task_id}", task_token
        )
    )
    
    if (self._config.environment_preflight_script or "").strip():
        environment_preflight_tmp_path = _write_preflight_script(
            str(self._config.environment_preflight_script or ""),
            "environment",
            self._config.task_id,
            preflight_tmp_paths,
        )
    
    if environment_preflight_tmp_path is not None:
        self._on_log(
            f"[host] environment preflight enabled (legacy); mounting -> {environment_container_path} (ro)"
        )
        preflight_mounts.extend(
            [
                "-v",
                f"{environment_preflight_tmp_path}:{environment_container_path}:ro",
            ]
        )
        preflight_clause += (
            f"PREFLIGHT_ENV={shlex.quote(environment_container_path)}; "
            'echo "[preflight] environment: running"; '
            '/bin/bash "${PREFLIGHT_ENV}"; '
            'echo "[preflight] environment: done"; '
        )
```

---

## 5. Serialization Updates

**File:** `agents_runner/environments/serialize.py`

### 5.1 Update Load Function

```python
def _load_environment_v1(payload: dict) -> Environment:
    """Load environment from v1 format with migration support."""
    
    # ... existing field loading ...
    
    # NEW: Load container caching fields
    cache_container_build = bool(payload.get("cache_container_build", False))
    cached_preflight_script = payload.get("cached_preflight_script", "")
    run_preflight_script = payload.get("run_preflight_script", "")
    
    # Legacy single preflight fields
    preflight_enabled = bool(payload.get("preflight_enabled", False))
    preflight_script = payload.get("preflight_script", "")
    
    # MIGRATION: Old single preflight → run preflight
    if preflight_script and not run_preflight_script:
        run_preflight_script = preflight_script
        logger.info(
            f"Environment {env_id}: migrated preflight_script to run_preflight_script"
        )
        
        # Warn if container caching enabled but no cached preflight
        if cache_container_build and not cached_preflight_script:
            logger.warning(
                f"Environment {env_id}: container caching enabled but "
                "cached_preflight_script is empty. Split your preflight script "
                "to enable caching benefits."
            )
    
    return Environment(
        env_id=env_id,
        name=name,
        # ... other fields ...
        cache_container_build=cache_container_build,
        cached_preflight_script=cached_preflight_script,
        run_preflight_script=run_preflight_script,
        preflight_enabled=preflight_enabled,  # Keep for reference
        preflight_script=preflight_script,    # Keep for reference
        # ... other fields ...
    )
```

### 5.2 Update Save Function

```python
def _save_environment(env: Environment) -> dict:
    """Save environment to v1 format."""
    
    payload = {
        "version": ENVIRONMENT_VERSION,
        "env_id": env.env_id,
        "name": env.name,
        # ... other fields ...
        
        # NEW: Container caching fields
        "cache_container_build": bool(getattr(env, "cache_container_build", False)),
        "cached_preflight_script": getattr(env, "cached_preflight_script", ""),
        "run_preflight_script": getattr(env, "run_preflight_script", ""),
        
        # Legacy fields (keep for backward compatibility)
        "preflight_enabled": bool(getattr(env, "preflight_enabled", False)),
        "preflight_script": getattr(env, "preflight_script", ""),
        
        # ... other fields ...
    }
    
    return payload
```

---

## 6. UI Updates - Checkbox

**File:** `agents_runner/ui/pages/environments.py`

### 6.1 Add Checkbox Widget (after line 178)

```python
self._cache_container_build = QCheckBox(
    "Enable container caching"
)
self._cache_container_build.setToolTip(
    "When enabled, environment preflight is split into two stages:\n"
    "1. Cached preflight: Runs at image build time (packages, system config)\n"
    "2. Run preflight: Runs at task start (dynamic config, per-run setup)\n\n"
    "This reduces task startup time by pre-baking environment setup.\n"
    "Independent of desktop caching - both can be enabled together.\n\n"
    "IMPORTANT: You must split your preflight script into two parts.\n"
    "See Preflight tab for cached vs run preflight editors."
)
```

### 6.2 Update Layout (around line 207-210)

```python
headless_desktop_layout = QHBoxLayout(headless_desktop_row)
headless_desktop_layout.setContentsMargins(0, 0, 0, 0)
headless_desktop_layout.setSpacing(BUTTON_ROW_SPACING)
headless_desktop_layout.addWidget(self._headless_desktop_enabled)
headless_desktop_layout.addWidget(self._cache_desktop_build)
headless_desktop_layout.addWidget(self._cache_container_build)  # NEW
headless_desktop_layout.addStretch(1)
```

### 6.3 Update Load Method (around line 422)

```python
def _on_env_loaded(self, env: Environment) -> None:
    """Load environment data into UI widgets."""
    
    # ... existing field loading ...
    
    # NEW: Container caching
    self._cache_container_build.setChecked(
        bool(getattr(env, "cache_container_build", False))
    )
```

### 6.4 Update Save Method (around line 250)

```python
def _gather_environment_for_save(self) -> Environment:
    """Gather environment data from UI widgets."""
    
    # ... existing field gathering ...
    
    return Environment(
        env_id=self._current_env_id or "",
        name=self._name.text().strip(),
        # ... other fields ...
        cache_desktop_build=bool(self._cache_desktop_build.isChecked()),
        cache_container_build=bool(self._cache_container_build.isChecked()),  # NEW
        cached_preflight_script=self._cached_preflight_editor.toPlainText(),  # NEW
        run_preflight_script=self._run_preflight_editor.toPlainText(),        # NEW
        # ... other fields ...
    )
```

---

## 7. Task Agent Window Updates

**File:** `agents_runner/ui/main_window_tasks_agent.py`

### 7.1 Extract Container Caching Config (after line 266)

```python
# Existing
desktop_cache_enabled = (
    bool(getattr(env, "cache_desktop_build", False)) if env else False
)
desktop_cache_enabled = desktop_cache_enabled and headless_desktop_enabled

# NEW: Container caching
container_cache_enabled = (
    bool(getattr(env, "cache_container_build", False)) if env else False
)
cached_preflight = getattr(env, "cached_preflight_script", "") if env else ""
run_preflight = getattr(env, "run_preflight_script", "") if env else ""

# Legacy single preflight (for backward compatibility)
legacy_preflight = getattr(env, "preflight_script", "") if env else ""
```

### 7.2 Build Config with New Fields (around line 422)

```python
config = DockerRunnerConfig(
    task_id=task_id,
    image=pixelarch_image,
    host_codex_dir=config_dir,
    host_workdir=workdir,
    agent_cli=agent_cli,
    # ... other existing fields ...
    
    # Desktop caching (Part 2)
    headless_desktop_enabled=headless_desktop_enabled,
    desktop_cache_enabled=desktop_cache_enabled,
    
    # Container caching (Part 3 - NEW)
    container_cache_enabled=container_cache_enabled,
    cached_preflight_script=(
        cached_preflight if cached_preflight.strip() else None
    ),
    run_preflight_script=(
        run_preflight if run_preflight.strip() else None
    ),
    
    # Legacy single preflight (for backward compatibility)
    settings_preflight_script=settings_preflight or None,
    environment_preflight_script=(
        legacy_preflight if legacy_preflight.strip() else None
    ),
    
    # ... other fields ...
)
```

---

## 8. Preflight Analyzer Utility

**New File:** `agents_runner/utils/preflight_analyzer.py`

```python
"""Preflight script analyzer for helping users split single scripts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


@dataclass
class ScriptLine:
    """Represents a line from the preflight script with categorization."""
    
    line: str
    line_number: int
    category: Literal["cached", "run", "ambiguous", "comment", "empty"]
    reason: str


def analyze_preflight_script(
    script: str
) -> tuple[list[ScriptLine], list[ScriptLine]]:
    """Analyze preflight script and suggest split into cached/run parts.
    
    Args:
        script: Single preflight script text
        
    Returns:
        Tuple of (cached_lines, run_lines) with categorized suggestions
    """
    cached_lines: list[ScriptLine] = []
    run_lines: list[ScriptLine] = []
    
    for idx, line in enumerate(script.splitlines(), start=1):
        stripped = line.strip()
        
        # Skip empty lines
        if not stripped:
            continue
        
        # Keep comments in both (user can filter later)
        if stripped.startswith("#"):
            cached_lines.append(ScriptLine(
                line=line,
                line_number=idx,
                category="comment",
                reason="Comment (keep in both if needed)",
            ))
            run_lines.append(ScriptLine(
                line=line,
                line_number=idx,
                category="comment",
                reason="Comment (keep in both if needed)",
            ))
            continue
        
        # Detect cached patterns (static operations)
        if _is_package_install(stripped):
            cached_lines.append(ScriptLine(
                line=line,
                line_number=idx,
                category="cached",
                reason="Package installation (static, slow, benefits from caching)",
            ))
        elif _is_download_binary(stripped):
            cached_lines.append(ScriptLine(
                line=line,
                line_number=idx,
                category="cached",
                reason="Download binary (static, slow, benefits from caching)",
            ))
        elif _is_system_config(stripped):
            cached_lines.append(ScriptLine(
                line=line,
                line_number=idx,
                category="cached",
                reason="System configuration (static, applies to all tasks)",
            ))
        elif _is_static_directory(stripped):
            cached_lines.append(ScriptLine(
                line=line,
                line_number=idx,
                category="cached",
                reason="Static directory creation (applies to all tasks)",
            ))
        # Detect run patterns (dynamic operations)
        elif _is_env_var_export(stripped):
            run_lines.append(ScriptLine(
                line=line,
                line_number=idx,
                category="run",
                reason="Environment variable export (dynamic, per-task)",
            ))
        elif _uses_task_variable(stripped):
            run_lines.append(ScriptLine(
                line=line,
                line_number=idx,
                category="run",
                reason="Uses task-specific variable (per-task)",
            ))
        elif _is_temp_directory(stripped):
            run_lines.append(ScriptLine(
                line=line,
                line_number=idx,
                category="run",
                reason="Temporary directory creation (per-task)",
            ))
        else:
            # Ambiguous - default to run for safety
            run_lines.append(ScriptLine(
                line=line,
                line_number=idx,
                category="ambiguous",
                reason="Unable to classify - defaulting to run (safe)",
            ))
    
    return cached_lines, run_lines


def _is_package_install(line: str) -> bool:
    """Detect package installation commands."""
    patterns = [
        r"\byay\s+-S\b",
        r"\bpacman\s+-S\b",
        r"\bpip\s+install\b",
        r"\bnpm\s+install\s+-g\b",
        r"\byarn\s+global\s+add\b",
        r"\bapt-get\s+install\b",
        r"\bapk\s+add\b",
    ]
    return any(re.search(p, line) for p in patterns)


def _is_download_binary(line: str) -> bool:
    """Detect binary downloads."""
    patterns = [
        r"\bwget\b.*\s+-O\s+/usr",
        r"\bcurl\b.*\s+-o\s+/usr",
        r"\bgit\s+clone\b.*\s+/opt",
        r"\bwget\b.*\s+-O\s+/opt",
        r"\bcurl\b.*\s+-o\s+/opt",
    ]
    return any(re.search(p, line) for p in patterns)


def _is_system_config(line: str) -> bool:
    """Detect system configuration."""
    patterns = [
        r"\bchmod\b.*\s+/usr",
        r"\bchmod\b.*\s+/opt",
        r"\bchown\b.*\s+/opt",
        r"\bchown\b.*\s+/usr",
        r"\bln\s+-s\b.*\s+/usr",
    ]
    return any(re.search(p, line) for p in patterns)


def _is_static_directory(line: str) -> bool:
    """Detect static directory creation."""
    patterns = [
        r"\bmkdir\b.*\s+/opt",
        r"\bmkdir\b.*\s+/usr/local",
    ]
    return any(re.search(p, line) for p in patterns)


def _is_env_var_export(line: str) -> bool:
    """Detect environment variable exports."""
    return bool(re.search(r"\bexport\s+\w+=", line))


def _uses_task_variable(line: str) -> bool:
    """Detect usage of task-specific variables."""
    patterns = [
        r"\$\{?AGENTS_RUNNER_TASK_ID\}?",
        r"\$\{?TASK_ID\}?",
        r"\$\{?AGENTS_RUNNER_",
    ]
    return any(re.search(p, line) for p in patterns)


def _is_temp_directory(line: str) -> bool:
    """Detect temporary directory operations."""
    return bool(re.search(r"\bmkdir\b.*\s+/tmp/", line))
```

---

## 9. Example Split Scripts

### 9.1 Example: Python Development Environment

**Original Single Preflight:**
```bash
#!/bin/bash
set -euo pipefail

# Install Python packages
yay -S --noconfirm python-requests python-numpy python-pandas

# Install Node.js for tooling
yay -S --noconfirm nodejs npm

# Download code formatter
curl -L https://github.com/psf/black/releases/download/23.1.0/black -o /usr/local/bin/black
chmod +x /usr/local/bin/black

# Set environment variables
export PYTHONPATH=/home/midori-ai/workspace
export LOG_LEVEL=INFO

# Create workspace directory
mkdir -p /tmp/workspace-${AGENTS_RUNNER_TASK_ID}
```

**Split: Cached Preflight**
```bash
#!/bin/bash
set -euo pipefail

echo "[cached-preflight] Installing Python packages..."
yay -S --noconfirm python-requests python-numpy python-pandas

echo "[cached-preflight] Installing Node.js for tooling..."
yay -S --noconfirm nodejs npm

echo "[cached-preflight] Downloading code formatter..."
curl -L https://github.com/psf/black/releases/download/23.1.0/black -o /usr/local/bin/black
chmod +x /usr/local/bin/black

echo "[cached-preflight] Complete"
```

**Split: Run Preflight**
```bash
#!/bin/bash
set -euo pipefail

echo "[run-preflight] Setting environment variables..."
export PYTHONPATH=/home/midori-ai/workspace
export LOG_LEVEL=INFO

echo "[run-preflight] Creating workspace directory..."
mkdir -p /tmp/workspace-${AGENTS_RUNNER_TASK_ID}

echo "[run-preflight] Complete"
```

### 9.2 Example: Web Development Environment

**Cached Preflight:**
```bash
#!/bin/bash
set -euo pipefail

# Install web tooling
yay -S --noconfirm nodejs npm yarn git

# Install global npm packages
npm install -g typescript eslint prettier

# Create shared directories
mkdir -p /opt/nodejs
mkdir -p /opt/cache

# Set permissions
chmod 777 /opt/cache
```

**Run Preflight:**
```bash
#!/bin/bash
set -euo pipefail

# Set task-specific environment
export NODE_ENV=development
export TASK_ID=${AGENTS_RUNNER_TASK_ID}
export CACHE_DIR=/opt/cache/${TASK_ID}

# Create task-specific cache
mkdir -p ${CACHE_DIR}

# Log task start
echo "Task ${TASK_ID} started at $(date)" > ${CACHE_DIR}/start.log
```

---

## 10. Integration with Supervisor

**File:** `agents_runner/execution/supervisor.py`

### 10.1 Ensure Config Fields are Passed Through

```python
def _build_agent_config(self, agent: AgentInstance) -> DockerRunnerConfig:
    """Build DockerRunnerConfig for specific agent."""
    
    # ... existing code ...
    
    config = DockerRunnerConfig(
        task_id=self._config.task_id,
        image=self._config.image,
        host_codex_dir=agent.config_dir or self._config.host_codex_dir,
        host_workdir=self._config.host_workdir,
        agent_cli=agent.agent_cli,
        # ... existing fields ...
        
        # Desktop caching (Part 2)
        headless_desktop_enabled=self._config.headless_desktop_enabled,
        desktop_cache_enabled=self._config.desktop_cache_enabled,  # NEW (if not already)
        
        # Container caching (Part 3 - NEW)
        container_cache_enabled=self._config.container_cache_enabled,
        cached_preflight_script=self._config.cached_preflight_script,
        run_preflight_script=self._config.run_preflight_script,
        
        # Legacy
        settings_preflight_script=self._config.settings_preflight_script,
        environment_preflight_script=self._config.environment_preflight_script,
        
        # ... other fields ...
    )
    return config
```

---

**END OF IMPLEMENTATION REFERENCE**
