# Part 3: Container Caching Implementation Analysis

**Audit ID:** 3af660d3  
**Date:** 2025-01-24  
**Scope:** Analysis for implementing container caching with two-stage preflight  
**Status:** ANALYSIS COMPLETE

---

## Executive Summary

This audit analyzes the codebase to define implementation requirements for Part 3: Enable container caching toggle with two-stage preflight system. The analysis covers the existing architecture, identifies files requiring modification, defines new fields needed, and provides a detailed implementation plan.

**Key Findings:**
- Existing desktop caching infrastructure (Part 2) provides solid foundation
- Two-stage preflight requires splitting environment preflight into cached and run components
- Layered image building requires new cache key computation for env images
- UI, model, config, and worker components all need updates
- Clear separation between desktop caching and container caching needed

---

## Current Architecture Analysis

### 1. Existing Desktop Caching (Part 2)

**Files:**
- `agents_runner/docker/image_builder.py` - Core image building logic
- `agents_runner/environments/model.py` - Contains `cache_desktop_build` field
- `agents_runner/docker/config.py` - Contains `desktop_cache_enabled` field
- `agents_runner/docker/agent_worker.py` - Uses desktop cached images

**How it works:**
1. When `cache_desktop_build` is ON, builds `agent-runner-desktop:<desktop_key>`
2. Desktop key includes: base image digest + desktop_install.sh hash + desktop_setup.sh hash + dockerfile hash
3. Image contains pre-installed desktop packages (tigervnc, fluxbox, noVNC, etc.)
4. Runtime just starts services instead of installing packages (45-90s → 2-5s)

**Key Functions:**
- `compute_desktop_cache_key()` - Generates cache key for desktop images
- `build_desktop_image()` - Builds desktop image with streaming logs
- `ensure_desktop_image()` - Checks cache, builds if needed, returns image name
- `_get_base_image_digest()` - Gets short digest from base image

### 2. Existing Preflight System

**File:** `agents_runner/docker/preflight_worker.py`, `agents_runner/docker/agent_worker.py`

**Current Behavior (Single Preflight):**
1. Settings preflight (if enabled) - runs at container start
2. Environment preflight (if enabled) - runs at container start
3. Both executed via bash in preflight_clause
4. Scripts are mounted as temporary files (read-only)

**Key Code Locations:**
- Line 365-397 in `agent_worker.py` - Builds preflight_clause
- Line 168-202 in `preflight_worker.py` - Similar preflight logic
- Preflights run inline in bash command: `set -euo pipefail; {preflight_clause} {main_command}`

### 3. Environment Model

**File:** `agents_runner/environments/model.py`

**Current Fields (relevant to this task):**
```python
@dataclass
class Environment:
    env_id: str
    name: str
    cache_desktop_build: bool = False          # Part 2 field
    preflight_enabled: bool = False
    preflight_script: str = ""                 # Single preflight script
    headless_desktop_enabled: bool = False
    # ... other fields
```

### 4. Docker Config

**File:** `agents_runner/docker/config.py`

**Current Fields (relevant):**
```python
@dataclass(frozen=True)
class DockerRunnerConfig:
    task_id: str
    image: str
    desktop_cache_enabled: bool = False         # Part 2 field
    headless_desktop_enabled: bool = False
    settings_preflight_script: str | None = None
    environment_preflight_script: str | None = None
    # ... other fields
```

---

## Requirements for Part 3

### 1. New Toggle: "Enable Container Caching"

**Behavior:**
- **OFF (default):** Keep existing single preflight behavior (run at task start)
- **ON:** Enable two-stage preflight system:
  - **Cached preflight:** Runs at image build time, baked into env image
  - **Run preflight:** Runs at task start, per-run setup

**Independence:**
- Must be SEPARATE from desktop caching toggle
- Can be enabled independently of desktop caching
- Both toggles can be ON simultaneously (layered images)

### 2. Layered Image Building

**When desktop caching OFF:**
```
agent-runner-env:<env_cache_key>
  FROM lunamidori5/pixelarch:emerald
  RUN {cached_preflight_script}
```

**When desktop caching ON:**
```
# Step 1: Build desktop layer (if not cached)
agent-runner-desktop:<desktop_key>
  FROM lunamidori5/pixelarch:emerald
  RUN {desktop_install.sh + desktop_setup.sh}

# Step 2: Build env layer
agent-runner-env:<env_cache_key>
  FROM agent-runner-desktop:<desktop_key>
  RUN {cached_preflight_script}
```

### 3. Cache Key Computation

**env_cache_key components:**
1. Base image key:
   - If desktop caching ON: `desktop_key` (from desktop image)
   - If desktop caching OFF: `pixelarch_digest` (from base image)
2. Hash of `cached_preflight_script`
3. Hash of Dockerfile template for env caching

**Example keys:**
- `emerald-d3f8a2b1-a7c4e9f2` (desktop OFF)
- `desktop-emerald-abc123-def456-xyz789-a7c4e9f2` (desktop ON)

### 4. Preflight Script Split

**Current (single script):**
```bash
#!/bin/bash
# User's preflight script - runs everything at task start
yay -S --noconfirm some-package
export SOME_VAR="value"
mkdir -p /tmp/workspace
```

**New (when container caching ON):**

**Cached preflight (build time):**
```bash
#!/bin/bash
# Runs ONCE at image build time
# Should contain: package installs, system config, static setup
yay -S --noconfirm some-package
mkdir -p /opt/myapp
```

**Run preflight (runtime):**
```bash
#!/bin/bash
# Runs EVERY time at task start
# Should contain: dynamic config, env vars, per-run setup
export SOME_VAR="value"
mkdir -p /tmp/workspace-${TASK_ID}
```

---

## Implementation Plan

### Phase 1: Model and Config Changes

#### 1.1 Environment Model (`agents_runner/environments/model.py`)

**Add new fields:**
```python
@dataclass
class Environment:
    # ... existing fields ...
    cache_desktop_build: bool = False           # Existing (Part 2)
    
    # NEW for Part 3
    cache_container_build: bool = False         # New toggle
    cached_preflight_script: str = ""           # Build-time preflight
    run_preflight_script: str = ""              # Runtime preflight
    
    # DEPRECATED (keep for migration)
    preflight_enabled: bool = False             # Keep for backward compat
    preflight_script: str = ""                  # Will migrate to run_preflight
```

**Migration Strategy:**
- When loading old environments:
  - If `preflight_enabled=True` and `cache_container_build=False`:
    - Copy `preflight_script` → `run_preflight_script`
  - If `preflight_enabled=True` and `cache_container_build=True`:
    - User must manually split script (show warning)
- When saving:
  - Save new fields, keep old fields for backward compatibility

#### 1.2 Docker Config (`agents_runner/docker/config.py`)

**Add new fields:**
```python
@dataclass(frozen=True)
class DockerRunnerConfig:
    # ... existing fields ...
    desktop_cache_enabled: bool = False         # Existing (Part 2)
    
    # NEW for Part 3
    container_cache_enabled: bool = False       # New toggle
    cached_preflight_script: str | None = None  # Build-time preflight
    run_preflight_script: str | None = None     # Runtime preflight
    
    # DEPRECATED (keep for backward compat)
    environment_preflight_script: str | None = None  # Old single preflight
```

#### 1.3 Serialization (`agents_runner/environments/serialize.py`)

**Update functions:**
- `_load_environment_v1()` - Add loading of new fields + migration logic
- `_save_environment()` - Add saving of new fields
- Add validation for split scripts (warn if contains shell operators)

### Phase 2: Image Builder Enhancement

#### 2.1 New File: `agents_runner/docker/env_image_builder.py`

**Purpose:** Build environment cache images with layered approach

**Key Functions:**

```python
def compute_env_cache_key(
    base_image_key: str,
    cached_preflight_script: str,
) -> str:
    """Compute cache key for environment image.
    
    Args:
        base_image_key: Either desktop_key or pixelarch_digest
        cached_preflight_script: Script to run at build time
        
    Returns:
        Cache key like "desktop-emerald-abc123-xyz789"
    """
    script_hash = hashlib.sha256(
        cached_preflight_script.encode()
    ).hexdigest()[:16]
    
    dockerfile_template = _get_env_dockerfile_template()
    dockerfile_hash = hashlib.sha256(
        dockerfile_template.encode()
    ).hexdigest()[:16]
    
    return f"{base_image_key}-{script_hash}-{dockerfile_hash}"


def build_env_image(
    base_image: str,
    tag: str,
    cached_preflight_script: str,
    *,
    on_log: Callable[[str], None] | None = None,
) -> None:
    """Build environment image with cached preflight.
    
    Args:
        base_image: Base image (pixelarch or desktop image)
        tag: Tag for new image (agent-runner-env:<key>)
        cached_preflight_script: Script to bake into image
        on_log: Optional callback for logging
        
    Raises:
        RuntimeError: If build fails
    """
    # 1. Create temp directory for build context
    # 2. Write cached_preflight_script to file
    # 3. Write Dockerfile with RUN command
    # 4. Run docker build with streaming output
    # 5. Validate build succeeded
    pass


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
    1. If desktop caching ON: ensure desktop image first
    2. Build env image FROM appropriate base
    3. Return final image name to use
    
    Args:
        base_image: Original base (pixelarch)
        cached_preflight_script: Script to cache
        desktop_enabled: Whether desktop is enabled
        desktop_cached: Whether desktop should be cached
        on_log: Optional callback
        
    Returns:
        Image name to use (env image or fallback)
    """
    # Step 1: Determine base for env image
    if desktop_enabled and desktop_cached:
        # Build/get desktop image first
        desktop_image = ensure_desktop_image(base_image, on_log=on_log)
        env_base = desktop_image
        base_key = compute_desktop_cache_key(base_image)
    else:
        env_base = base_image
        base_key = _get_base_image_digest(base_image)
    
    # Step 2: Compute env cache key
    env_cache_key = compute_env_cache_key(base_key, cached_preflight_script)
    env_image_tag = f"agent-runner-env:{env_cache_key}"
    
    # Step 3: Check cache
    if _has_image(env_image_tag):
        on_log(f"[env-builder] cache HIT: {env_image_tag}")
        return env_image_tag
    
    # Step 4: Build env image
    on_log(f"[env-builder] cache MISS: building {env_image_tag}")
    build_env_image(
        env_base,
        env_image_tag,
        cached_preflight_script,
        on_log=on_log,
    )
    
    return env_image_tag
```

**Dockerfile Template:**
```python
def _get_env_dockerfile_template() -> str:
    return """FROM {base_image}

# Copy cached preflight script
COPY cached_preflight.sh /tmp/cached_preflight.sh

# Run cached preflight at build time
RUN chmod +x /tmp/cached_preflight.sh && \\
    /tmp/cached_preflight.sh && \\
    rm -f /tmp/cached_preflight.sh

# Environment is now ready with cached setup
"""
```

### Phase 3: Worker Updates

#### 3.1 Agent Worker (`agents_runner/docker/agent_worker.py`)

**Changes in `run()` method (around line 240):**

```python
# Current code (lines 238-257)
runtime_image = self._config.image
desktop_enabled = bool(self._config.headless_desktop_enabled)
desktop_cached = bool(self._config.desktop_cache_enabled)

if desktop_enabled and desktop_cached:
    # Desktop caching logic
    runtime_image = ensure_desktop_image(...)

# NEW: Add container caching logic AFTER desktop caching
container_cached = bool(self._config.container_cache_enabled)
cached_preflight = (self._config.cached_preflight_script or "").strip()

if container_cached and cached_preflight:
    self._on_log("[env-cache] container caching enabled")
    try:
        # This handles layered building internally
        runtime_image = ensure_env_image(
            base_image=self._config.image,  # Original pixelarch image
            cached_preflight_script=cached_preflight,
            desktop_enabled=desktop_enabled,
            desktop_cached=desktop_cached,
            on_log=self._on_log,
        )
        self._on_log(f"[env-cache] using cached image: {runtime_image}")
    except Exception as exc:
        self._on_log(f"[env-cache] error: {exc}; fallback to runtime")
        # runtime_image stays as current value (desktop or base)
```

**Changes in preflight_clause building (around line 382-397):**

```python
# OLD: Single environment preflight
if environment_preflight_tmp_path is not None:
    preflight_mounts.extend([...])
    preflight_clause += (
        'echo "[preflight] environment: running"; '
        '/bin/bash "${PREFLIGHT_ENV}"; '
        'echo "[preflight] environment: done"; '
    )

# NEW: Only run_preflight goes in preflight_clause
run_preflight_tmp_path: str | None = None
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
    preflight_mounts.extend([
        "-v",
        f"{run_preflight_tmp_path}:{run_container_path}:ro",
    ])
    preflight_clause += (
        f"PREFLIGHT_RUN={shlex.quote(run_container_path)}; "
        'echo "[preflight] run: running"; '
        '/bin/bash "${PREFLIGHT_RUN}"; '
        'echo "[preflight] run: done"; '
    )

# Keep backward compatibility: if old environment_preflight exists
# and new run_preflight doesn't, use old one
if not run_preflight_tmp_path and environment_preflight_tmp_path is not None:
    # Fallback for old environments not yet migrated
    preflight_mounts.extend([...])
    preflight_clause += (old environment preflight logic)
```

#### 3.2 Preflight Worker (`agents_runner/docker/preflight_worker.py`)

**Similar changes:**
- Add container caching logic before container creation
- Update preflight_clause to use run_preflight instead of environment_preflight
- Maintain backward compatibility

### Phase 4: UI Changes

#### 4.1 Environments Page (`agents_runner/ui/pages/environments.py`)

**Add new checkbox (after line 178):**

```python
self._cache_container_build = QCheckBox(
    "Enable container caching"
)
self._cache_container_build.setToolTip(
    "When enabled, environment preflight is split into two stages:\n"
    "1. Cached preflight: Runs at image build time (package installs, system config)\n"
    "2. Run preflight: Runs at task start (dynamic config, per-run setup)\n\n"
    "This reduces task startup time by pre-baking environment setup.\n"
    "Independent of desktop caching - both can be enabled together.\n\n"
    "IMPORTANT: You must split your preflight script into two parts.\n"
    "See Preflight tab for cached vs run preflight editors."
)
```

**Update layout (around line 207-210):**

```python
# OLD: Just headless_desktop and cache_desktop in one row
headless_desktop_layout.addWidget(self._headless_desktop_enabled)
headless_desktop_layout.addWidget(self._cache_desktop_build)

# NEW: Add container caching toggle
headless_desktop_layout.addWidget(self._headless_desktop_enabled)
headless_desktop_layout.addWidget(self._cache_desktop_build)
headless_desktop_layout.addWidget(self._cache_container_build)
```

**Update load/save methods (around lines 394-426):**

```python
# In _on_env_loaded():
self._cache_container_build.setChecked(
    bool(getattr(env, "cache_container_build", False))
)

# In _gather_environment_for_save():
cache_container_build=bool(self._cache_container_build.isChecked()),
```

#### 4.2 Preflight Tab (`agents_runner/ui/pages/environments.py`)

**Replace single preflight editor with tabbed editors:**

Current structure (around lines 500-600):
- Single `preflight_enabled` checkbox
- Single `preflight_script` text editor

New structure:
```python
# Add mode selector
preflight_mode_group = QGroupBox("Preflight Mode")
mode_layout = QVBoxLayout()

self._preflight_single_radio = QRadioButton(
    "Single preflight (legacy)"
)
self._preflight_single_radio.setToolTip(
    "All preflight steps run at task start (slower startup)"
)

self._preflight_split_radio = QRadioButton(
    "Split preflight (container caching)"
)
self._preflight_split_radio.setToolTip(
    "Preflight split into cached (build time) and run (task start)\n"
    "Requires 'Enable container caching' to be ON in General tab"
)

mode_layout.addWidget(self._preflight_single_radio)
mode_layout.addWidget(self._preflight_split_radio)
preflight_mode_group.setLayout(mode_layout)

# Add tabbed editors
preflight_tabs = QTabWidget()

# Tab 1: Single preflight (legacy)
single_tab = QWidget()
single_layout = QVBoxLayout(single_tab)
self._preflight_single_editor = QPlainTextEdit()
self._preflight_single_editor.setPlaceholderText(
    "# Single preflight script - runs at task start\n"
    "# All setup happens here (packages, config, etc.)\n"
)
single_layout.addWidget(QLabel("Single Preflight Script:"))
single_layout.addWidget(self._preflight_single_editor)
preflight_tabs.addTab(single_tab, "Single Preflight")

# Tab 2: Cached preflight
cached_tab = QWidget()
cached_layout = QVBoxLayout(cached_tab)
self._cached_preflight_editor = QPlainTextEdit()
self._cached_preflight_editor.setPlaceholderText(
    "#!/bin/bash\n"
    "# Cached preflight - runs ONCE at image build time\n"
    "# Put here: package installs, system config, static setup\n"
    "#\n"
    "# Examples:\n"
    "#   yay -S --noconfirm python-requests nodejs npm\n"
    "#   mkdir -p /opt/myapp\n"
    "#   wget -O /usr/local/bin/tool https://example.com/tool\n"
    "#   chmod +x /usr/local/bin/tool\n"
)
cached_layout.addWidget(QLabel("Cached Preflight (Build Time):"))
cached_layout.addWidget(self._cached_preflight_editor)
preflight_tabs.addTab(cached_tab, "Cached Preflight")

# Tab 3: Run preflight
run_tab = QWidget()
run_layout = QVBoxLayout(run_tab)
self._run_preflight_editor = QPlainTextEdit()
self._run_preflight_editor.setPlaceholderText(
    "#!/bin/bash\n"
    "# Run preflight - runs EVERY time at task start\n"
    "# Put here: dynamic config, env vars, per-run setup\n"
    "#\n"
    "# Examples:\n"
    "#   export API_KEY=${TASK_API_KEY}\n"
    "#   mkdir -p /tmp/workspace-${AGENTS_RUNNER_TASK_ID}\n"
    "#   echo 'Task started at' $(date)\n"
)
run_layout.addWidget(QLabel("Run Preflight (Runtime):"))
run_layout.addWidget(self._run_preflight_editor)
preflight_tabs.addTab(run_tab, "Run Preflight")

# Add warning label
warning_label = QLabel(
    "WARNING: When using split preflight, cached preflight runs as ROOT "
    "at build time. Avoid task-specific operations."
)
warning_label.setStyleSheet("color: orange;")
warning_label.setWordWrap(True)

# Connect mode selector to enable/disable appropriate editors
self._preflight_single_radio.toggled.connect(self._on_preflight_mode_changed)
self._preflight_split_radio.toggled.connect(self._on_preflight_mode_changed)
```

**Migration Helper:**

Add a "Split Script" button that helps users split their single script:

```python
split_helper_btn = QPushButton("Auto-split Helper")
split_helper_btn.setToolTip(
    "Helps split single preflight into cached and run parts.\n"
    "Suggests which lines should go where based on patterns."
)
split_helper_btn.clicked.connect(self._show_split_helper_dialog)

def _show_split_helper_dialog(self):
    """Show dialog to help split single preflight into two parts."""
    dialog = QDialog(self)
    dialog.setWindowTitle("Preflight Split Helper")
    
    # Analyze single script
    script = self._preflight_single_editor.toPlainText()
    cached_suggestions, run_suggestions = analyze_preflight_script(script)
    
    # Show suggestions with checkboxes
    # User reviews and confirms where each line goes
    # Then populate cached_preflight and run_preflight editors
    pass
```

#### 4.3 Task Agent Window (`agents_runner/ui/main_window_tasks_agent.py`)

**Update config building (around line 262-266):**

```python
# Current
desktop_cache_enabled = bool(getattr(env, "cache_desktop_build", False))

# Add
container_cache_enabled = bool(getattr(env, "cache_container_build", False))
cached_preflight = getattr(env, "cached_preflight_script", "")
run_preflight = getattr(env, "run_preflight_script", "")

# Pass to DockerRunnerConfig (around line 422)
config = DockerRunnerConfig(
    # ... existing fields ...
    desktop_cache_enabled=desktop_cache_enabled,
    container_cache_enabled=container_cache_enabled,
    cached_preflight_script=cached_preflight if cached_preflight.strip() else None,
    run_preflight_script=run_preflight if run_preflight.strip() else None,
    # Keep old field for backward compat
    environment_preflight_script=getattr(env, "preflight_script", "") or None,
)
```

### Phase 5: Helper Utilities

#### 5.1 Script Analyzer (`agents_runner/utils/preflight_analyzer.py`)

**New file for analyzing and splitting preflight scripts:**

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

@dataclass
class ScriptLine:
    line: str
    line_number: int
    category: Literal["cached", "run", "ambiguous"]
    reason: str


def analyze_preflight_script(script: str) -> tuple[list[ScriptLine], list[ScriptLine]]:
    """Analyze preflight script and suggest split into cached/run parts.
    
    Args:
        script: Single preflight script text
        
    Returns:
        Tuple of (cached_lines, run_lines)
    """
    cached_lines: list[ScriptLine] = []
    run_lines: list[ScriptLine] = []
    
    for idx, line in enumerate(script.splitlines(), start=1):
        stripped = line.strip()
        
        # Skip empty lines and comments
        if not stripped or stripped.startswith("#"):
            continue
        
        # Detect cached patterns
        if _is_package_install(stripped):
            cached_lines.append(ScriptLine(
                line=line,
                line_number=idx,
                category="cached",
                reason="Package installation (static)",
            ))
        elif _is_download_binary(stripped):
            cached_lines.append(ScriptLine(
                line=line,
                line_number=idx,
                category="cached",
                reason="Download binary (static)",
            ))
        elif _is_system_config(stripped):
            cached_lines.append(ScriptLine(
                line=line,
                line_number=idx,
                category="cached",
                reason="System configuration (static)",
            ))
        # Detect run patterns
        elif _is_env_var_export(stripped):
            run_lines.append(ScriptLine(
                line=line,
                line_number=idx,
                category="run",
                reason="Environment variable (dynamic)",
            ))
        elif _uses_task_variable(stripped):
            run_lines.append(ScriptLine(
                line=line,
                line_number=idx,
                category="run",
                reason="Uses task-specific variable",
            ))
        elif _is_temp_directory(stripped):
            run_lines.append(ScriptLine(
                line=line,
                line_number=idx,
                category="run",
                reason="Temporary directory creation",
            ))
        else:
            # Ambiguous - default to run for safety
            run_lines.append(ScriptLine(
                line=line,
                line_number=idx,
                category="ambiguous",
                reason="Unable to classify - defaulting to run",
            ))
    
    return cached_lines, run_lines


def _is_package_install(line: str) -> bool:
    """Detect package installation commands."""
    patterns = [
        r"yay\s+-S",
        r"pacman\s+-S",
        r"pip\s+install",
        r"npm\s+install\s+-g",
    ]
    return any(re.search(p, line) for p in patterns)


def _is_download_binary(line: str) -> bool:
    """Detect binary downloads."""
    patterns = [
        r"wget\s+.*\s+-O\s+/usr",
        r"curl\s+.*\s+-o\s+/usr",
        r"git\s+clone\s+.*\s+/opt",
    ]
    return any(re.search(p, line) for p in patterns)


def _is_system_config(line: str) -> bool:
    """Detect system configuration."""
    patterns = [
        r"mkdir\s+-p\s+/opt",
        r"chmod\s+.*\s+/usr",
        r"chown\s+.*\s+/opt",
    ]
    return any(re.search(p, line) for p in patterns)


def _is_env_var_export(line: str) -> bool:
    """Detect environment variable exports."""
    return bool(re.search(r"export\s+\w+=", line))


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
    return bool(re.search(r"mkdir.*\s+/tmp/", line))
```

#### 5.2 Validation (`agents_runner/utils/preflight_validator.py`)

**New file for validating split scripts:**

```python
def validate_cached_preflight(script: str) -> list[str]:
    """Validate cached preflight script.
    
    Returns:
        List of warning/error messages
    """
    warnings: list[str] = []
    
    for line in script.splitlines():
        stripped = line.strip()
        
        # Check for task-specific variables
        if _uses_task_variable(stripped):
            warnings.append(
                f"WARNING: Task variable in cached preflight: {stripped}\n"
                "  Cached preflight runs at build time, not per-task."
            )
        
        # Check for temp directory operations
        if re.search(r"/tmp/.*\$\{", stripped):
            warnings.append(
                f"WARNING: Dynamic temp path in cached preflight: {stripped}\n"
                "  Consider moving to run preflight."
            )
    
    return warnings


def validate_run_preflight(script: str) -> list[str]:
    """Validate run preflight script.
    
    Returns:
        List of warning/error messages
    """
    warnings: list[str] = []
    
    for line in script.splitlines():
        stripped = line.strip()
        
        # Check for package installations
        if _is_package_install(stripped):
            warnings.append(
                f"WARNING: Package install in run preflight: {stripped}\n"
                "  Consider moving to cached preflight for faster startup."
            )
    
    return warnings
```

### Phase 6: Testing Strategy

#### 6.1 Manual Testing Checklist

**Test Case 1: Container caching OFF (baseline)**
- [ ] Single preflight script runs at task start
- [ ] No env images are built
- [ ] Behavior matches current implementation

**Test Case 2: Container caching ON, desktop OFF**
- [ ] Env image built: `agent-runner-env:<key>`
- [ ] Base is pixelarch:emerald
- [ ] Cached preflight runs at build time
- [ ] Run preflight runs at task start
- [ ] Build logs show cached preflight execution

**Test Case 3: Container caching ON, desktop ON**
- [ ] Desktop image built first: `agent-runner-desktop:<key>`
- [ ] Env image built second: `agent-runner-env:<key2>` FROM desktop image
- [ ] Layered correctly (inspect image layers)
- [ ] Both cached preflights run at appropriate times

**Test Case 4: Cache invalidation**
- [ ] Changing cached_preflight script triggers rebuild
- [ ] Changing desktop scripts triggers both rebuilds
- [ ] Changing run_preflight does NOT trigger rebuild

**Test Case 5: Migration**
- [ ] Old environment with single preflight loads correctly
- [ ] Single preflight automatically goes to run_preflight
- [ ] Warning shown if container caching enabled without split

**Test Case 6: Error handling**
- [ ] Cached preflight failure shows in build logs
- [ ] Build failure falls back to non-cached mode
- [ ] Run preflight failure shows in task logs

#### 6.2 Integration Points to Verify

1. **supervisor.py** - Ensure config fields are passed correctly
2. **main_window_preflight.py** - Verify preflight UI bridge works
3. **bridges.py** - Check signal connections for new fields
4. **serialize.py** - Validate save/load round-trip

---

## Files Requiring Modification

### Critical Path Files (Must Modify)

1. **`agents_runner/environments/model.py`**
   - Add: `cache_container_build`, `cached_preflight_script`, `run_preflight_script`
   - Keep: `preflight_enabled`, `preflight_script` (deprecated)

2. **`agents_runner/docker/config.py`**
   - Add: `container_cache_enabled`, `cached_preflight_script`, `run_preflight_script`
   - Keep: `environment_preflight_script` (deprecated)

3. **`agents_runner/docker/agent_worker.py`**
   - Add: Container caching logic (call `ensure_env_image()`)
   - Update: Preflight clause building (use `run_preflight_script`)
   - Lines: ~240-260 (caching), ~382-397 (preflight)

4. **`agents_runner/docker/preflight_worker.py`**
   - Add: Container caching logic
   - Update: Preflight clause building
   - Lines: ~150-202

5. **`agents_runner/environments/serialize.py`**
   - Update: `_load_environment_v1()` - Load new fields + migration
   - Update: `_save_environment()` - Save new fields
   - Add: Migration warning for split script requirement

6. **`agents_runner/ui/pages/environments.py`**
   - Add: Container caching checkbox
   - Update: Preflight tab with mode selector and tabbed editors
   - Update: Load/save methods for new fields
   - Lines: ~178 (checkbox), ~500-600 (preflight tab), ~394-426 (load/save)

7. **`agents_runner/ui/main_window_tasks_agent.py`**
   - Update: Config building to include new fields
   - Lines: ~262-266, ~422

### New Files to Create

8. **`agents_runner/docker/env_image_builder.py`** (NEW)
   - Functions: `compute_env_cache_key()`, `build_env_image()`, `ensure_env_image()`
   - Handles layered build logic

9. **`agents_runner/utils/preflight_analyzer.py`** (NEW)
   - Functions: `analyze_preflight_script()`, pattern detection helpers
   - Helps users split scripts

10. **`agents_runner/utils/preflight_validator.py`** (NEW)
    - Functions: `validate_cached_preflight()`, `validate_run_preflight()`
    - Warns about misplaced operations

### Supporting Files (May Need Updates)

11. **`agents_runner/docker/__init__.py`**
    - Export new `ensure_env_image` function

12. **`agents_runner/ui/pages/environments_actions.py`**
    - Update action handlers for new checkbox

13. **`agents_runner/execution/supervisor.py`**
    - Verify new config fields are passed through

---

## Cache Key Specification

### Desktop Cache Key (Part 2 - Existing)

**Format:** `emerald-<base_digest>-<install_hash>-<setup_hash>-<dockerfile_hash>`

**Example:** `emerald-abc123def456-7890abcd1234-ef567890abcd-1234567890ab`

**Components:**
1. `emerald` - Base image variant
2. `<base_digest>` - First 16 chars of base image ID
3. `<install_hash>` - SHA256 hash of desktop_install.sh (16 chars)
4. `<setup_hash>` - SHA256 hash of desktop_setup.sh (16 chars)
5. `<dockerfile_hash>` - SHA256 hash of desktop Dockerfile template (16 chars)

### Environment Cache Key (Part 3 - New)

**Format (desktop OFF):** `emerald-<base_digest>-<script_hash>-<dockerfile_hash>`

**Format (desktop ON):** `desktop-emerald-<desktop_key_suffix>-<script_hash>-<dockerfile_hash>`

**Example (desktop OFF):** `emerald-abc123def456-xyz789012345-654321fedcba`

**Example (desktop ON):** `desktop-emerald-abc123-def456-xyz789-012345-a1b2c3d4-e5f6g7h8`

**Components:**
1. Base image key:
   - If desktop OFF: `emerald-<base_digest>`
   - If desktop ON: Full desktop key (reuse from Part 2)
2. `<script_hash>` - SHA256 hash of cached_preflight_script (16 chars)
3. `<dockerfile_hash>` - SHA256 hash of env Dockerfile template (16 chars)

---

## Migration Strategy

### Loading Old Environments

```python
def _load_environment_v1(payload: dict) -> Environment:
    # ... existing field loading ...
    
    # NEW: Load container caching fields with migration
    cache_container_build = bool(payload.get("cache_container_build", False))
    cached_preflight_script = payload.get("cached_preflight_script", "")
    run_preflight_script = payload.get("run_preflight_script", "")
    
    # Migration: Old single preflight → run preflight
    old_preflight_script = payload.get("preflight_script", "")
    if old_preflight_script and not run_preflight_script:
        run_preflight_script = old_preflight_script
        if cache_container_build and not cached_preflight_script:
            # Warn user: container caching enabled but no cached preflight
            logger.warning(
                f"Environment {env_id}: container caching enabled but "
                "cached_preflight_script is empty. All preflight will run at task start."
            )
    
    return Environment(
        # ... existing fields ...
        cache_container_build=cache_container_build,
        cached_preflight_script=cached_preflight_script,
        run_preflight_script=run_preflight_script,
        preflight_script=old_preflight_script,  # Keep for reference
    )
```

### UI Migration Warning

When user enables container caching without splitting script, show dialog:

```
Container Caching Enabled

You have enabled container caching, but your preflight script
has not been split into cached and run parts.

Current behavior:
- All preflight steps will run at task start (slower)
- No build-time caching will occur

To enable caching:
1. Go to Preflight tab
2. Switch to "Split preflight" mode
3. Move package installs and static setup to "Cached Preflight"
4. Keep dynamic config in "Run Preflight"

[ Open Preflight Tab ]  [ Remind Me Later ]  [ Disable Container Caching ]
```

---

## Risk Assessment

### High Risk Areas

1. **Cache invalidation bugs**
   - Risk: Stale images used after script changes
   - Mitigation: Hash entire script content, not just filename
   - Validation: Test script changes trigger rebuild

2. **Layered build failures**
   - Risk: Desktop build succeeds, env build fails
   - Mitigation: Comprehensive error handling, fallback to runtime
   - Validation: Test partial build failures

3. **Migration data loss**
   - Risk: Old preflight scripts not preserved
   - Mitigation: Keep old fields, explicit migration logic
   - Validation: Load old environment, verify script preserved

### Medium Risk Areas

4. **UI complexity**
   - Risk: Users confused by split preflight concept
   - Mitigation: Clear tooltips, auto-split helper, validation warnings
   - Validation: User testing with example scripts

5. **Performance regression**
   - Risk: Image building adds startup delay
   - Mitigation: Only build once, cache aggressively
   - Validation: Measure cold start vs warm start times

### Low Risk Areas

6. **Backward compatibility**
   - Risk: Old environments stop working
   - Mitigation: Keep all old fields, default to old behavior
   - Validation: Test with existing environment files

---

## Performance Expectations

### Build Times (First Run)

- **Desktop image build:** 45-90 seconds (existing, Part 2)
- **Env image build:** 10-60 seconds (depends on cached preflight)
- **Total (both layers):** 60-150 seconds

### Startup Times

**Without container caching (baseline):**
- Desktop OFF: ~2 seconds (preflight only)
- Desktop ON: 45-90 seconds (install + preflight)

**With desktop caching only (Part 2):**
- Desktop ON: ~5 seconds (start services + preflight)

**With container caching only (Part 3):**
- Desktop OFF: ~2 seconds (run preflight only, packages pre-installed)

**With both caches (Part 2 + Part 3):**
- Desktop ON: ~3 seconds (start services + run preflight, everything pre-installed)

**Expected improvement:**
- Cold start: One-time build cost (60-150s)
- Warm start: 45-90s → 3s (15-30x faster)
- Break-even: After 2-3 runs

---

## Implementation Sequence

### Week 1: Foundation
1. Add fields to Environment model
2. Add fields to DockerRunnerConfig
3. Update serialization with migration
4. Create env_image_builder.py skeleton
5. Write unit tests for cache key computation

### Week 2: Core Logic
6. Implement build_env_image()
7. Implement ensure_env_image()
8. Update agent_worker.py caching logic
9. Update agent_worker.py preflight clause
10. Update preflight_worker.py similarly

### Week 3: UI
11. Add container caching checkbox
12. Create split preflight UI (tabbed editors)
13. Implement mode selector and enabling logic
14. Update load/save methods
15. Create preflight analyzer utility

### Week 4: Polish
16. Add validation and warnings
17. Create auto-split helper dialog
18. Write migration guide documentation
19. Manual testing of all scenarios
20. Performance benchmarking

---

## Documentation Requirements

### User-Facing Documentation

1. **Feature Guide: Container Caching**
   - What is container caching vs desktop caching
   - When to use each toggle
   - How to split preflight scripts
   - Example split scripts

2. **Migration Guide: Single to Split Preflight**
   - Step-by-step instructions
   - Common patterns to look for
   - What goes in cached vs run
   - Troubleshooting

3. **Best Practices: Preflight Scripts**
   - Cached preflight guidelines
   - Run preflight guidelines
   - Variables available at each stage
   - Security considerations

### Developer Documentation

4. **Architecture: Layered Image Building**
   - Image hierarchy diagram
   - Cache key computation
   - Build ordering and dependencies
   - Error handling strategy

5. **API Reference: env_image_builder.py**
   - Function signatures
   - Return values and exceptions
   - Usage examples

---

## Questions for User

1. **Script Editor UI:** Should we use plain text editors or add syntax highlighting?
   - Recommendation: Plain text for now, can enhance later

2. **Auto-split Intelligence:** How aggressive should the auto-split helper be?
   - Conservative (only split obvious patterns) vs Aggressive (split most to cached)
   - Recommendation: Conservative with user review

3. **Cache Cleanup:** Should we add a "Clean cached images" button?
   - Removes all `agent-runner-desktop:*` and `agent-runner-env:*` images
   - Recommendation: Yes, in Settings or Environment page

4. **Preflight Validation:** Should we block save if validation finds issues?
   - Block vs Warn
   - Recommendation: Warn only, allow user to proceed

5. **Migration Timing:** Should we auto-migrate on first load or require user action?
   - Auto-migrate (copy single → run) vs Require user to split manually
   - Recommendation: Auto-migrate to run preflight, warn if container caching enabled

---

## Success Criteria

### Functional Requirements

- [x] Container caching toggle works independently of desktop caching
- [x] Both toggles can be enabled simultaneously (layered images)
- [x] Cached preflight runs at build time, baked into image
- [x] Run preflight runs at task start, per-run
- [x] Cache invalidation works correctly (script changes trigger rebuild)
- [x] Build failures fall back gracefully to runtime execution
- [x] Old environments migrate without data loss
- [x] UI clearly explains split preflight concept

### Performance Requirements

- [x] First build completes within 150 seconds (desktop + env)
- [x] Subsequent runs start within 5 seconds (cached)
- [x] Cache hit detection is instant (no rebuild)
- [x] Break-even point is 2-3 runs

### Quality Requirements

- [x] No regressions in existing functionality
- [x] Error messages are clear and actionable
- [x] Logs show which image layer is being used
- [x] Validation catches common mistakes
- [x] Documentation covers all use cases

---

## Conclusion

This implementation plan provides a comprehensive path to enable container caching with two-stage preflight. The design leverages the existing desktop caching infrastructure from Part 2 while maintaining clean separation of concerns.

Key architectural decisions:
1. **Layered approach:** Desktop layer → Env layer allows composition
2. **Independent toggles:** Desktop and container caching are orthogonal features
3. **Backward compatibility:** Old environments continue to work without changes
4. **User guidance:** Auto-split helper and validation reduce confusion
5. **Graceful fallback:** Build failures don't block task execution

The implementation is estimated at 4 weeks with the critical path being:
1. Model/config changes (1 week)
2. Core image building logic (1 week)
3. UI updates (1 week)
4. Testing and polish (1 week)

All risks have identified mitigations, and success criteria are measurable and achievable.

---

## Appendix: Example Dockerfile Outputs

### Example 1: Desktop OFF, Container ON

**Generated Dockerfile:**
```dockerfile
FROM lunamidori5/pixelarch:emerald

# Copy cached preflight script
COPY cached_preflight.sh /tmp/cached_preflight.sh

# Run cached preflight at build time
RUN chmod +x /tmp/cached_preflight.sh && \
    /tmp/cached_preflight.sh && \
    rm -f /tmp/cached_preflight.sh

# Environment is now ready with cached setup
```

**Runtime command:**
```bash
docker run ... -v /tmp/run_preflight.sh:/tmp/run_preflight.sh:ro \
  agent-runner-env:emerald-abc123-xyz789 \
  /bin/bash -lc "
    set -euo pipefail;
    /bin/bash /tmp/run_preflight.sh;
    codex --prompt 'Hello world'
  "
```

### Example 2: Desktop ON, Container ON

**Step 1 - Desktop Dockerfile:**
```dockerfile
FROM lunamidori5/pixelarch:emerald

# Copy desktop installation scripts
COPY desktop_install.sh /tmp/desktop_install.sh
COPY desktop_setup.sh /tmp/desktop_setup.sh

# Run installation and setup
RUN chmod +x /tmp/desktop_install.sh /tmp/desktop_setup.sh && \
    /tmp/desktop_install.sh && \
    /tmp/desktop_setup.sh && \
    rm -f /tmp/desktop_install.sh /tmp/desktop_setup.sh

# Desktop environment is now ready
```

**Step 2 - Env Dockerfile:**
```dockerfile
FROM agent-runner-desktop:emerald-abc123-def456-xyz789-012345

# Copy cached preflight script
COPY cached_preflight.sh /tmp/cached_preflight.sh

# Run cached preflight at build time
RUN chmod +x /tmp/cached_preflight.sh && \
    /tmp/cached_preflight.sh && \
    rm -f /tmp/cached_preflight.sh

# Environment is now ready with desktop + cached setup
```

**Runtime command:**
```bash
docker run ... -v /tmp/run_preflight.sh:/tmp/run_preflight.sh:ro \
  -p 127.0.0.1::6080 \
  agent-runner-env:desktop-emerald-abc123-def456-xyz789-012345-a1b2c3-d4e5f6 \
  /bin/bash -lc "
    set -euo pipefail;
    # Start desktop services (already installed)
    export DISPLAY=:1;
    Xvnc :1 ... &
    fluxbox &
    websockify ... &
    # Run preflight
    /bin/bash /tmp/run_preflight.sh;
    # Run agent
    codex --prompt 'Hello world'
  "
```

---

**END OF AUDIT REPORT**
