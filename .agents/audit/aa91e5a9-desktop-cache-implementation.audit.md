# Desktop Cache Implementation Audit Report

**Audit ID:** aa91e5a9  
**Date:** 2024  
**Auditor:** AI Assistant (Auditor Mode)  
**Scope:** Part 2 - Cache desktop build per-environment toggle

---

## Executive Summary

This audit analyzed the Agents Runner codebase to understand how to implement a per-environment "Cache desktop build" toggle feature. The feature will allow environments to pre-build Docker images with desktop components installed, significantly reducing startup time for desktop-enabled tasks.

**Key Findings:**
1. Well-structured environment model with clear serialization patterns
2. UI already has desktop toggle infrastructure in place
3. Docker system uses a single base image (PIXELARCH_EMERALD_IMAGE)
4. Desktop installation scripts are modular and well-separated
5. No existing image building infrastructure - needs to be created
6. Clear separation between install/setup/run phases for desktop

**Recommendation:** Proceed with implementation. The codebase is well-architected for this feature.

---

## Codebase Analysis

### 1. Environment Model (`agents_runner/environments/model.py`)

**Current State:**
- Environment dataclass with 20+ fields
- `headless_desktop_enabled: bool = False` field already exists
- Version tracking: `ENVIRONMENT_VERSION = 1`
- Serialization handled via `serialize.py`

**Required Changes:**
```python
@dataclass
class Environment:
    # ... existing fields ...
    headless_desktop_enabled: bool = False
    cache_desktop_build: bool = False  # NEW FIELD
    # ... remaining fields ...
```

**Risk Assessment:** LOW
- Simple boolean addition
- Follows existing pattern
- Version bump required

---

### 2. Environment UI (`agents_runner/ui/pages/environments.py`)

**Current State:**
- General tab contains headless desktop checkbox at line 161-167
- Grid layout with proper spacing (GRID_VERTICAL_SPACING)
- Checkbox positioned at row 5 in grid

**Required Changes:**
```python
# After headless_desktop_enabled checkbox (around line 193)
self._cache_desktop_build = QCheckBox("Cache desktop build")
self._cache_desktop_build.setToolTip(
    "Pre-build Docker image with desktop environment installed.\n"
    "Reduces task startup time but requires rebuilding when desktop scripts change.\n"
    "Only available when headless desktop is enabled."
)
self._cache_desktop_build.setEnabled(False)  # Disabled by default

# Add to grid layout (after row 5)
cache_desktop_row = QWidget(general_tab)
cache_desktop_layout = QHBoxLayout(cache_desktop_row)
cache_desktop_layout.setContentsMargins(0, 0, 0, 0)
cache_desktop_layout.setSpacing(BUTTON_ROW_SPACING)
cache_desktop_layout.addWidget(self._cache_desktop_build)
cache_desktop_layout.addStretch(1)

grid.addWidget(QLabel("Cache desktop build"), 6, 0)
grid.addWidget(cache_desktop_row, 6, 1, 1, 2)

# Connect headless desktop toggle to enable/disable cache toggle
self._headless_desktop_enabled.toggled.connect(
    lambda checked: self._cache_desktop_build.setEnabled(checked)
)
```

**Additional UI Methods Required:**
- `_load_selected()`: Load cache_desktop_build from environment
- Update save logic to persist cache_desktop_build

**Risk Assessment:** LOW
- Straightforward UI addition
- Follows existing checkbox pattern
- Clear dependency on headless_desktop_enabled

---

### 3. Environment Serialization (`agents_runner/environments/serialize.py`)

**Current State:**
- `_environment_from_payload()`: Deserializes from JSON (line 87-293)
- `serialize_environment()`: Serializes to JSON (line 296-363)
- Handles backward compatibility with field migrations
- Version checking in place

**Required Changes:**

**Deserialization (line ~114):**
```python
headless_desktop_enabled = bool(payload.get("headless_desktop_enabled", False))
cache_desktop_build = bool(payload.get("cache_desktop_build", False))  # NEW
```

**Return statement (line ~279):**
```python
return Environment(
    # ... existing fields ...
    headless_desktop_enabled=headless_desktop_enabled,
    cache_desktop_build=cache_desktop_build,  # NEW
    # ... remaining fields ...
)
```

**Serialization (line ~342):**
```python
return {
    # ... existing fields ...
    "headless_desktop_enabled": bool(
        getattr(env, "headless_desktop_enabled", False)
    ),
    "cache_desktop_build": bool(
        getattr(env, "cache_desktop_build", False)
    ),  # NEW
    # ... remaining fields ...
}
```

**Risk Assessment:** LOW
- Simple field addition
- No migration logic needed (defaults to False)
- Backward compatible

---

### 4. Docker Image Building (NEW MODULE REQUIRED)

**Current State:**
- No existing image building infrastructure
- `agents_runner/docker/process.py` has image inspection/pull functions
- Base image: `PIXELARCH_EMERALD_IMAGE = "lunamidori5/pixelarch:emerald"`
- Desktop scripts: `agents_runner/preflights/desktop_install.sh`, `desktop_setup.sh`

**Required: New Module** `agents_runner/docker/image_builder.py`

**Key Functions:**

```python
from pathlib import Path
import hashlib
import json
import subprocess
from typing import Tuple

def compute_desktop_cache_key(base_image: str) -> str:
    """
    Compute cache key for desktop image.
    
    Includes:
    - Base image digest (from docker inspect)
    - Hash of desktop_install.sh
    - Hash of desktop_setup.sh
    - Hash of Dockerfile snippet
    
    Returns:
        Cache key string (e.g., "emerald-abc123def456")
    """
    pass

def get_base_image_digest(image: str) -> str:
    """Get the digest of base image using docker inspect."""
    pass

def hash_file_content(file_path: Path) -> str:
    """Compute SHA256 hash of file content."""
    pass

def build_desktop_image(
    base_image: str,
    cache_key: str,
    on_log: Callable[[str], None]
) -> Tuple[str, bool]:
    """
    Build or reuse cached desktop image.
    
    Args:
        base_image: Base PixelArch image
        cache_key: Computed cache key
        on_log: Logging callback
    
    Returns:
        Tuple of (image_tag, was_built)
        - image_tag: Full tag of desktop image
        - was_built: True if newly built, False if reused
    """
    pass

def has_cached_desktop_image(cache_key: str) -> bool:
    """Check if cached desktop image exists."""
    pass
```

**Dockerfile Template:**
```dockerfile
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

# Copy desktop scripts
COPY desktop_install.sh /tmp/desktop_install.sh
COPY desktop_setup.sh /tmp/desktop_setup.sh

# Run installation and setup
RUN bash /tmp/desktop_install.sh && \
    bash /tmp/desktop_setup.sh && \
    rm /tmp/desktop_install.sh /tmp/desktop_setup.sh

# Desktop is now ready, no need to install at runtime
```

**Risk Assessment:** MEDIUM
- New module creation required
- Docker build process needs testing
- Error handling for build failures critical
- Need to handle platform arguments (linux/amd64)

---

### 5. Desktop Scripts Analysis

**Scripts Identified:**
1. `desktop_install.sh` (71 lines)
   - Installs packages via yay
   - Validates binaries exist
   - Retries on failure
   
2. `desktop_setup.sh` (48 lines)
   - Creates directories
   - Discovers noVNC path
   - Saves configuration to /etc/default/novnc-path
   - Sets environment defaults in /etc/profile.d/

3. `desktop_run.sh` (89 lines)
   - Runtime startup script
   - Starts Xvnc, fluxbox, xterm, websockify
   - Creates task-specific directories

**Cache Strategy:**
- CACHE: `desktop_install.sh` + `desktop_setup.sh` (deterministic system setup)
- RUNTIME: `desktop_run.sh` (per-task execution)

**Risk Assessment:** LOW
- Scripts are idempotent
- Clear separation of concerns
- Already tested in runtime context

---

### 6. Docker Runner Integration (`agents_runner/docker/agent_worker.py`)

**Current State:**
- Line 232: `image = PIXELARCH_EMERALD_IMAGE` (hardcoded)
- Line 219-235: Image pull logic
- Line 242-297: Desktop preflight clause construction

**Required Changes:**

```python
# Around line 232
image = PIXELARCH_EMERALD_IMAGE

# NEW: Check if environment wants cached desktop image
if self._config.headless_desktop_enabled and env.cache_desktop_build:
    from agents_runner.docker.image_builder import (
        compute_desktop_cache_key,
        build_desktop_image,
        has_cached_desktop_image,
    )
    
    cache_key = compute_desktop_cache_key(image)
    desktop_image = f"agent-runner-desktop:{cache_key}"
    
    if has_cached_desktop_image(cache_key):
        self._on_log(f"[desktop-cache] reusing cached image: {desktop_image}")
        image = desktop_image
        desktop_preflight_required = False  # Skip install/setup
    else:
        self._on_log(f"[desktop-cache] building image: {desktop_image}")
        built_image, was_built = build_desktop_image(
            base_image=image,
            cache_key=cache_key,
            on_log=self._on_log,
        )
        if was_built:
            self._on_log(f"[desktop-cache] build complete: {built_image}")
            image = built_image
            desktop_preflight_required = False  # Skip install/setup
        else:
            self._on_log("[desktop-cache] build failed, falling back to runtime install")
            # Continue with original image and runtime install

# ... existing pull logic ...

# Modify preflight clause construction (line 268-297)
if desktop_enabled and desktop_preflight_required:
    # Existing runtime install/setup logic
    preflight_clause += (
        'echo "[desktop] starting headless desktop (noVNC)"; '
        # ... rest of existing logic ...
    )
elif desktop_enabled:
    # Cached image: only run desktop_run.sh
    preflight_clause += (
        'echo "[desktop-cache] starting pre-installed desktop"; '
        'bash /path/to/desktop_run.sh; '
    )
```

**Risk Assessment:** MEDIUM
- Modifies critical task startup path
- Needs careful error handling
- Fallback to runtime install if build fails
- Must preserve existing behavior when cache disabled

---

### 7. Cache Key Computation Strategy

**Components:**

1. **Base Image Digest:**
   ```bash
   docker inspect lunamidori5/pixelarch:emerald \
     --format '{{index .RepoDigests 0}}'
   ```
   Example: `sha256:abc123...`

2. **Desktop Install Script Hash:**
   ```python
   hashlib.sha256(Path("desktop_install.sh").read_bytes()).hexdigest()[:12]
   ```

3. **Desktop Setup Script Hash:**
   ```python
   hashlib.sha256(Path("desktop_setup.sh").read_bytes()).hexdigest()[:12]
   ```

4. **Dockerfile Hash:**
   ```python
   dockerfile_content = generate_dockerfile_content()
   hashlib.sha256(dockerfile_content.encode()).hexdigest()[:12]
   ```

**Cache Key Format:**
```
emerald-<base_digest_short>-<install_hash>-<setup_hash>-<dockerfile_hash>
```

Example: `emerald-abc123-def456-789012-345678`

**Risk Assessment:** LOW
- Deterministic computation
- Captures all relevant inputs
- Short enough for Docker tag limits

---

### 8. Task Configuration (`agents_runner/docker/config.py`)

**Current State:**
- `DockerRunnerConfig` dataclass (line 6-39)
- Contains `headless_desktop_enabled: bool = False`

**Required Changes:**
```python
@dataclass(frozen=True)
class DockerRunnerConfig:
    # ... existing fields ...
    headless_desktop_enabled: bool = False
    desktop_cache_enabled: bool = False  # NEW
    # ... remaining fields ...
```

**Risk Assessment:** LOW
- Simple field addition
- Frozen dataclass prevents accidental mutation

---

### 9. Task Creation (`agents_runner/ui/main_window_tasks_agent.py`)

**Current State:**
- Line 232: `image = PIXELARCH_EMERALD_IMAGE`
- Line 261: Desktop enabled determination
- Line 405+: `DockerRunnerConfig` creation

**Required Changes:**

```python
# Around line 261
headless_desktop_enabled = bool(force_headless_desktop or env_headless_desktop)
cache_desktop_build = bool(getattr(env, "cache_desktop_build", False)) if env else False

# Around line 405 (DockerRunnerConfig creation)
config = DockerRunnerConfig(
    # ... existing fields ...
    headless_desktop_enabled=headless_desktop_enabled,
    desktop_cache_enabled=cache_desktop_build and headless_desktop_enabled,  # NEW
    # ... remaining fields ...
)
```

**Risk Assessment:** LOW
- Straightforward field passing
- Clear logic: cache only when desktop enabled

---

## Implementation Plan

### Phase 1: Data Model and Serialization (2-3 hours)

**Files to Modify:**
1. `agents_runner/environments/model.py`
   - Add `cache_desktop_build: bool = False`
   - No version bump needed (backward compatible)

2. `agents_runner/environments/serialize.py`
   - Add field to deserialization
   - Add field to serialization
   - Test backward compatibility

3. `agents_runner/docker/config.py`
   - Add `desktop_cache_enabled: bool = False`

**Testing:**
- Load existing environments (field defaults to False)
- Save environment with cache enabled
- Reload and verify persistence

**Risk:** LOW

---

### Phase 2: UI Implementation (3-4 hours)

**Files to Modify:**
1. `agents_runner/ui/pages/environments.py`
   - Add checkbox widget (~line 193)
   - Add to grid layout (~line 198)
   - Connect headless toggle to enable/disable
   - Load/save in `_load_selected()` and save handlers
   - Add tooltip with clear explanation

**Testing:**
- Toggle headless desktop on/off (cache toggle follows)
- Save environment with cache enabled
- Reload environment editor
- Verify tooltip displays correctly

**Risk:** LOW

---

### Phase 3: Image Builder Module (6-8 hours)

**New File:**
1. `agents_runner/docker/image_builder.py` (~300 lines)
   - `compute_desktop_cache_key()`
   - `get_base_image_digest()`
   - `hash_file_content()`
   - `build_desktop_image()`
   - `has_cached_desktop_image()`
   - `cleanup_old_desktop_images()` (optional)

**Key Implementation Details:**

```python
def compute_desktop_cache_key(base_image: str) -> str:
    """
    Compute deterministic cache key for desktop image.
    
    Components:
    1. Base image digest (or tag if digest unavailable)
    2. desktop_install.sh content hash
    3. desktop_setup.sh content hash
    4. Dockerfile template hash
    """
    preflights_dir = Path(__file__).parent.parent / "preflights"
    
    # Get base image digest
    try:
        digest = get_base_image_digest(base_image)
        base_part = digest.split(":")[1][:12]  # First 12 chars of digest
    except Exception:
        # Fallback to tag name
        base_part = base_image.split(":")[-1]
    
    # Hash desktop scripts
    install_hash = hash_file_content(preflights_dir / "desktop_install.sh")[:8]
    setup_hash = hash_file_content(preflights_dir / "desktop_setup.sh")[:8]
    
    # Hash Dockerfile template
    dockerfile = generate_dockerfile_template()
    dockerfile_hash = hashlib.sha256(dockerfile.encode()).hexdigest()[:8]
    
    return f"{base_part}-{install_hash}-{setup_hash}-{dockerfile_hash}"

def build_desktop_image(
    base_image: str,
    cache_key: str,
    on_log: Callable[[str], None],
) -> Tuple[str, bool]:
    """
    Build desktop image using Docker build.
    
    Returns:
        (image_tag, was_built)
    """
    image_tag = f"agent-runner-desktop:{cache_key}"
    
    # Check if already exists
    if has_cached_desktop_image(cache_key):
        return (image_tag, False)
    
    # Create build context
    build_dir = Path.home() / ".midoriai" / "agents-runner" / "docker-builds" / cache_key
    build_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy scripts to build context
    preflights_dir = Path(__file__).parent.parent / "preflights"
    shutil.copy(preflights_dir / "desktop_install.sh", build_dir)
    shutil.copy(preflights_dir / "desktop_setup.sh", build_dir)
    
    # Generate Dockerfile
    dockerfile_content = generate_dockerfile_template(base_image)
    (build_dir / "Dockerfile").write_text(dockerfile_content)
    
    # Build image
    on_log(f"[desktop-cache] building {image_tag}...")
    on_log("[desktop-cache] this may take 2-5 minutes...")
    
    try:
        # Use docker buildx for better platform handling
        from agents_runner.docker_platform import docker_platform_args_for_pixelarch
        platform_args = docker_platform_args_for_pixelarch()
        
        cmd = [
            "docker", "build",
            *platform_args,
            "-t", image_tag,
            str(build_dir),
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600.0,  # 10 minute timeout
        )
        
        if result.returncode != 0:
            on_log(f"[desktop-cache] build failed: {result.stderr}")
            return (base_image, False)
        
        on_log(f"[desktop-cache] build succeeded: {image_tag}")
        return (image_tag, True)
        
    except subprocess.TimeoutExpired:
        on_log("[desktop-cache] build timeout (10 minutes)")
        return (base_image, False)
    except Exception as e:
        on_log(f"[desktop-cache] build error: {e}")
        return (base_image, False)
    finally:
        # Cleanup build directory
        try:
            shutil.rmtree(build_dir)
        except Exception:
            pass
```

**Dockerfile Template:**
```dockerfile
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

# Install desktop components
COPY desktop_install.sh /tmp/desktop_install.sh
RUN bash /tmp/desktop_install.sh && rm /tmp/desktop_install.sh

# Setup desktop configuration
COPY desktop_setup.sh /tmp/desktop_setup.sh
RUN bash /tmp/desktop_setup.sh && rm /tmp/desktop_setup.sh

# Desktop is ready for use
```

**Testing:**
- Compute cache key multiple times (verify deterministic)
- Build image successfully
- Verify image exists with `docker images`
- Inspect image to verify desktop packages installed
- Test fallback when build fails
- Test with different platform arguments

**Risk:** MEDIUM-HIGH
- New module with complex Docker integration
- Build failures must degrade gracefully
- Platform-specific issues possible

---

### Phase 4: Docker Runner Integration (4-6 hours)

**Files to Modify:**
1. `agents_runner/docker/agent_worker.py`
   - Import image builder functions (~line 25)
   - Add cache check and build logic (~line 232)
   - Modify desktop preflight clause (~line 268)
   - Log cache reuse vs rebuild
   - Handle build failures gracefully

**Key Logic:**
```python
# Around line 232
image = PIXELARCH_EMERALD_IMAGE
use_cached_desktop = False

if self._config.headless_desktop_enabled and self._config.desktop_cache_enabled:
    from agents_runner.docker.image_builder import (
        compute_desktop_cache_key,
        build_desktop_image,
    )
    
    try:
        cache_key = compute_desktop_cache_key(image)
        desktop_image, was_built = build_desktop_image(
            base_image=image,
            cache_key=cache_key,
            on_log=self._on_log,
        )
        
        if desktop_image != image:
            # Successfully got/built cached image
            image = desktop_image
            use_cached_desktop = True
            
            if was_built:
                self._on_log(f"[desktop-cache] rebuilt desktop image: {cache_key}")
            else:
                self._on_log(f"[desktop-cache] reusing desktop image: {cache_key}")
        
    except Exception as e:
        self._on_log(f"[desktop-cache] cache failed, using runtime install: {e}")
        use_cached_desktop = False

# Later in desktop preflight section (~line 268)
if desktop_enabled:
    port_args.extend(["-p", "127.0.0.1::6080"])
    
    if use_cached_desktop:
        # Desktop already installed, just run startup script
        preflight_clause += (
            'echo "[desktop-cache] starting pre-installed desktop"; '
            'export DISPLAY=:1; '
            'export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"; '
            'export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/xdg-$(id -un)}"; '
            'mkdir -p "${XDG_RUNTIME_DIR}"; '
            'RUNTIME_BASE="/tmp/agents-runner-desktop/${AGENTS_RUNNER_TASK_ID:-task}"; '
            'mkdir -p "${RUNTIME_BASE}"/{run,log,out,config}; '
            # Source pre-configured noVNC path
            'source /etc/default/novnc-path; '
            # Start services (Xvnc, fluxbox, xterm, websockify)
            'Xvnc :1 -geometry 1280x800 -depth 24 -SecurityTypes None -localhost -rfbport 5901 >"${RUNTIME_BASE}/log/xvnc.log" 2>&1 & '
            'sleep 0.25; '
            '(fluxbox >"${RUNTIME_BASE}/log/fluxbox.log" 2>&1 &) || true; '
            '(xterm -geometry 80x24+10+10 >"${RUNTIME_BASE}/log/xterm.log" 2>&1 &) || true; '
            'websockify --web="${NOVNC_WEB}" 6080 127.0.0.1:5901 >"${RUNTIME_BASE}/log/novnc.log" 2>&1 & '
            'echo "[desktop-cache] ready"; '
        )
    else:
        # Existing runtime install logic
        preflight_clause += (
            'echo "[desktop] starting headless desktop (noVNC)"; '
            # ... existing logic ...
        )
```

**Testing:**
- Run task with cache disabled (existing behavior)
- Run task with cache enabled, no existing image (build)
- Run task with cache enabled, existing image (reuse)
- Verify startup time reduction
- Test build failure fallback
- Test with different environments

**Risk:** MEDIUM
- Modifies critical startup path
- Must preserve existing behavior
- Fallback logic must be robust

---

### Phase 5: Task Configuration Plumbing (2-3 hours)

**Files to Modify:**
1. `agents_runner/ui/main_window_tasks_agent.py`
   - Read cache_desktop_build from environment (~line 261)
   - Pass to DockerRunnerConfig (~line 405)

**Testing:**
- Create task with cache enabled environment
- Verify config has desktop_cache_enabled=True
- Create task with cache disabled environment
- Verify config has desktop_cache_enabled=False

**Risk:** LOW

---

### Phase 6: Testing and Polish (4-6 hours)

**Manual Testing:**
1. Environment CRUD:
   - Create environment with cache enabled
   - Edit environment to toggle cache
   - Save and reload
   - Delete environment

2. Task Execution:
   - First run with cache (should build)
   - Second run with cache (should reuse)
   - Modify desktop_install.sh (should rebuild)
   - Run without cache (should use runtime install)

3. Edge Cases:
   - Disable headless desktop (cache toggle should disable)
   - Enable cache, then disable headless (cache should not apply)
   - Build failure handling
   - Network issues during build

4. Performance:
   - Measure startup time without cache
   - Measure startup time with cache
   - Expected improvement: 30-60 seconds saved

**Logging Verification:**
- Clear messages for cache hit/miss
- Clear messages for build success/failure
- No sensitive information in logs

**UI/UX:**
- Tooltip explains feature clearly
- Toggle disabled when headless disabled
- No UI freeze during build

**Risk:** LOW-MEDIUM
- Comprehensive testing required
- Performance validation critical

---

## File Modifications Summary

### New Files (1):
1. `agents_runner/docker/image_builder.py` (~300 lines)
   - Cache key computation
   - Image building
   - Image inspection

### Modified Files (6):
1. `agents_runner/environments/model.py`
   - Add `cache_desktop_build` field

2. `agents_runner/environments/serialize.py`
   - Serialize/deserialize cache_desktop_build

3. `agents_runner/docker/config.py`
   - Add `desktop_cache_enabled` field

4. `agents_runner/ui/pages/environments.py`
   - Add cache toggle checkbox
   - Wire up enable/disable logic

5. `agents_runner/docker/agent_worker.py`
   - Integrate image builder
   - Conditional desktop preflight

6. `agents_runner/ui/main_window_tasks_agent.py`
   - Pass cache setting to config

**Total Lines Changed:** ~400-500 lines
**Total Time Estimate:** 21-30 hours

---

## Risk Assessment

### Overall Risk: MEDIUM

**Low Risk Components:**
- Environment model changes (simple field addition)
- Serialization (follows existing patterns)
- UI changes (straightforward checkbox)
- Task configuration plumbing (data passing)

**Medium Risk Components:**
- Image builder module (new Docker integration)
- Agent worker integration (modifies critical path)
- Build failure handling (must degrade gracefully)

**High Risk Components:**
- None identified

**Mitigation Strategies:**
1. Comprehensive fallback logic (always fall back to runtime install)
2. Clear error messages and logging
3. Timeout protection on Docker build (10 minutes max)
4. No changes to default behavior (feature is opt-in)
5. Thorough testing before deployment

---

## Performance Impact

**Expected Improvements:**
- **Without cache:** 45-90 seconds desktop setup per task
- **With cache (hit):** 2-5 seconds desktop startup per task
- **With cache (miss/build):** 5-10 minutes one-time build + fast subsequent runs

**Build Time Breakdown:**
- yay package sync: 10-30 seconds
- Package installation: 3-7 minutes
- Desktop setup: 5-10 seconds
- Docker image commit: 30-60 seconds

**Storage Impact:**
- Each cached image: ~500-800 MB (incremental over base)
- Cache key changes: New image built, old retained until manual cleanup
- Recommend: Document manual cleanup with `docker images | grep agent-runner-desktop`

---

## Security Considerations

**No New Security Concerns:**
1. Desktop scripts already run with elevated privileges (package installation)
2. Image building uses same scripts as runtime
3. No new network access required
4. Build context isolated to temp directory
5. No secrets or credentials involved

**Existing Security Posture Maintained:**
- Same PixelArch base image
- Same package sources (Arch Linux repos)
- Same script validation

---

## Backward Compatibility

**Fully Backward Compatible:**
1. `cache_desktop_build` defaults to False (existing behavior)
2. No version bump required in `ENVIRONMENT_VERSION`
3. Old environments load correctly (field absent = False)
4. New environments with cache=False identical to old
5. Feature is completely opt-in

**Migration Path:**
- No migration required
- Users opt-in by enabling toggle in environment editor

---

## Documentation Requirements

**User-Facing:**
1. Tooltip in UI (included in implementation)
2. Optional: README section on desktop caching
3. Optional: Performance comparison metrics

**Developer-Facing:**
1. Docstrings in `image_builder.py` (included)
2. Comments in modified files (included)
3. This audit report serves as implementation guide

---

## Alternative Approaches Considered

### Alternative 1: Global Cache (Single Cached Image)
**Pros:**
- Simpler implementation
- One image shared across all environments

**Cons:**
- No per-environment customization
- Forces all environments to use same desktop setup
- Breaks if user customizes desktop scripts per environment

**Decision:** REJECTED - Per-environment is more flexible

### Alternative 2: Manual Rebuild Button
**Pros:**
- User controls when rebuild happens
- Could be useful for debugging

**Cons:**
- Adds UI complexity
- Not requested in requirements
- Cache key auto-invalidation is cleaner

**Decision:** REJECTED - Cache key invalidation is sufficient

### Alternative 3: Docker Compose for Image Management
**Pros:**
- Standard tool for multi-image setups
- Built-in caching

**Cons:**
- Adds dependency
- Overkill for single image
- Users may not have docker-compose installed

**Decision:** REJECTED - Direct docker build is simpler

---

## Implementation Checklist

### Phase 1: Data Model ✓
- [ ] Add `cache_desktop_build` to Environment dataclass
- [ ] Update `_environment_from_payload()` in serialize.py
- [ ] Update `serialize_environment()` in serialize.py
- [ ] Add `desktop_cache_enabled` to DockerRunnerConfig
- [ ] Test backward compatibility

### Phase 2: UI ✓
- [ ] Add `_cache_desktop_build` checkbox widget
- [ ] Add to grid layout in environments.py
- [ ] Connect headless toggle to enable/disable cache
- [ ] Update `_load_selected()` to load field
- [ ] Update save logic to persist field
- [ ] Add tooltip with clear explanation
- [ ] Test UI interaction

### Phase 3: Image Builder ✓
- [ ] Create `image_builder.py` module
- [ ] Implement `compute_desktop_cache_key()`
- [ ] Implement `get_base_image_digest()`
- [ ] Implement `hash_file_content()`
- [ ] Implement `build_desktop_image()`
- [ ] Implement `has_cached_desktop_image()`
- [ ] Create Dockerfile template
- [ ] Test cache key determinism
- [ ] Test image building
- [ ] Test failure handling

### Phase 4: Docker Runner Integration ✓
- [ ] Import image builder in agent_worker.py
- [ ] Add cache check logic before image selection
- [ ] Modify desktop preflight clause
- [ ] Add logging for cache hit/miss/build
- [ ] Test fallback on build failure
- [ ] Test with cached image
- [ ] Test startup time improvement

### Phase 5: Task Configuration ✓
- [ ] Read cache_desktop_build in main_window_tasks_agent.py
- [ ] Pass to DockerRunnerConfig
- [ ] Test config propagation

### Phase 6: Testing ✓
- [ ] Environment CRUD tests
- [ ] Task execution tests (cache hit/miss)
- [ ] Edge case tests
- [ ] Performance validation
- [ ] Logging verification
- [ ] UI/UX validation

---

## Conclusion

**Recommendation:** PROCEED WITH IMPLEMENTATION

The codebase is well-architected for this feature. The implementation plan is straightforward with clear separation of concerns. Risk is manageable through comprehensive fallback logic and testing.

**Key Success Factors:**
1. Graceful degradation (always fall back to runtime install)
2. Clear logging (users understand what's happening)
3. Deterministic cache keys (rebuilds only when necessary)
4. Thorough testing (edge cases covered)

**Expected Outcome:**
- 30-60 second startup time improvement for desktop-enabled tasks
- Zero impact on non-desktop tasks
- Zero impact when cache disabled
- Fully backward compatible
- User-friendly with clear UI feedback

---

## Appendix: Code Examples

### Example Cache Key Computation

```python
# Base image: lunamidori5/pixelarch:emerald
# Digest: sha256:abc123def456...

# desktop_install.sh hash: 789012345678
# desktop_setup.sh hash: abcdef123456
# Dockerfile hash: fedcba654321

# Result: "emerald-abc123-789012-abcdef-fedcba"
```

### Example Log Output

**First Run (Build):**
```
[desktop-cache] computing cache key for lunamidori5/pixelarch:emerald
[desktop-cache] cache key: emerald-abc123-789012-abcdef-fedcba
[desktop-cache] no cached image found
[desktop-cache] building agent-runner-desktop:emerald-abc123-789012-abcdef-fedcba...
[desktop-cache] this may take 2-5 minutes...
[desktop-install] Installing desktop environment packages...
[desktop-install] All packages installed and validated successfully
[desktop-setup] Desktop environment setup complete
[desktop-cache] build complete: agent-runner-desktop:emerald-abc123-789012-abcdef-fedcba
[desktop-cache] starting pre-installed desktop
[desktop-cache] ready
```

**Second Run (Reuse):**
```
[desktop-cache] computing cache key for lunamidori5/pixelarch:emerald
[desktop-cache] cache key: emerald-abc123-789012-abcdef-fedcba
[desktop-cache] reusing cached image: agent-runner-desktop:emerald-abc123-789012-abcdef-fedcba
[desktop-cache] starting pre-installed desktop
[desktop-cache] ready
```

**Build Failure:**
```
[desktop-cache] computing cache key for lunamidori5/pixelarch:emerald
[desktop-cache] cache key: emerald-abc123-789012-abcdef-fedcba
[desktop-cache] building agent-runner-desktop:emerald-abc123-789012-abcdef-fedcba...
[desktop-cache] build failed: Step 3/5 failed
[desktop-cache] falling back to runtime install
[desktop] starting headless desktop (noVNC)
[desktop] ready
```

---

**End of Audit Report**
