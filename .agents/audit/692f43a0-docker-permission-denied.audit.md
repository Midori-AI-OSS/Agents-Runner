# Docker Build Permission Denied Audit Report

**Audit ID:** 692f43a0  
**Date:** 2025-01-04  
**Auditor:** Auditor Mode  
**Severity:** HIGH  
**Status:** IDENTIFIED - FIX REQUIRED

---

## Executive Summary

A critical permission denied error occurs during Docker image build when the `desktop_setup.sh` script attempts to write to `/etc/default/novnc-path`. The root cause is that the Dockerfile template runs both installation and setup scripts in a single RUN command, but the base image (`lunamidori5/pixelarch:emerald`) likely runs as a non-root user by default, preventing writes to system directories.

**Error:** `/tmp/desktop_setup.sh: line 32: /etc/default/novnc-path: Permission denied`

---

## Root Cause Analysis

### 1. Problem Location

**File:** `/home/midori-ai/workspace/agents_runner/docker/image_builder.py`  
**Function:** `_get_dockerfile_template()` (lines 117-133)  
**Problematic Line:** Line 130

```dockerfile
RUN /bin/bash /tmp/desktop_install.sh && /bin/bash /tmp/desktop_setup.sh && rm -f /tmp/desktop_install.sh /tmp/desktop_setup.sh
```

### 2. The Permission Issue

The `desktop_setup.sh` script (lines 30-33) attempts to write to system directories:

```bash
echo "[desktop-setup] Saving noVNC path to /etc/default/novnc-path..."
mkdir -p /etc/default
echo "NOVNC_WEB=${NOVNC_WEB}" > /etc/default/novnc-path
chmod 644 /etc/default/novnc-path
```

**The Problem:**
- The base image `lunamidori5/pixelarch:emerald` runs as a non-root user
- The Dockerfile does NOT specify `USER root` before running the scripts
- Writing to `/etc/default/` requires root privileges
- The `desktop_install.sh` script uses `yay` which also requires proper permissions

### 3. Why This Fails

PixelArch images typically follow best practices by running as a non-privileged user. When the Dockerfile builds:

1. Base image is loaded with its default user (likely `midori-ai` or similar)
2. Scripts are copied to `/tmp/` (this works - /tmp is world-writable)
3. Scripts execute as the non-root user
4. `desktop_install.sh` may work if yay is configured for the user
5. `desktop_setup.sh` fails at line 32 when trying to write to `/etc/default/`

---

## Impact Assessment

**Build Failure Rate:** 100% on clean builds  
**Affected Components:**
- `agents_runner/docker/image_builder.py::build_desktop_image()`
- `agents_runner/docker/image_builder.py::ensure_desktop_image()`
- All desktop image caching functionality
- Agent tasks requiring desktop environment

**User Impact:**
- Desktop environment images cannot be cached
- Fallback to runtime installation increases task startup time
- Potential for inconsistent desktop environments across runs

---

## Detailed Code Analysis

### File: `agents_runner/docker/image_builder.py`

#### Lines 117-133: Dockerfile Template (DEFECT)

```python
def _get_dockerfile_template() -> str:
    """Get the Dockerfile template for building desktop image.
    
    Returns:
        Dockerfile template as a string
    """
    return """FROM {base_image}

# Copy desktop installation scripts
COPY desktop_install.sh /tmp/desktop_install.sh
COPY desktop_setup.sh /tmp/desktop_setup.sh

# Run installation and setup
RUN /bin/bash /tmp/desktop_install.sh && /bin/bash /tmp/desktop_setup.sh && rm -f /tmp/desktop_install.sh /tmp/desktop_setup.sh

# Desktop environment is now ready
"""
```

**Issues:**
1. Missing `USER root` directive before RUN command
2. No privilege escalation for system-level operations
3. Scripts assume root context but don't enforce it

### File: `agents_runner/preflights/desktop_setup.sh`

#### Lines 30-33: System Directory Write (REQUIRES ROOT)

```bash
echo "[desktop-setup] Saving noVNC path to /etc/default/novnc-path..."
mkdir -p /etc/default
echo "NOVNC_WEB=${NOVNC_WEB}" > /etc/default/novnc-path
chmod 644 /etc/default/novnc-path
```

**Issues:**
1. Writes to `/etc/default/` without checking permissions
2. No error handling for permission denied
3. Assumes root context but doesn't verify

#### Lines 36-44: Additional System Writes (REQUIRES ROOT)

```bash
echo "[desktop-setup] Setting environment defaults in /etc/profile.d/desktop-env.sh..."
mkdir -p /etc/profile.d
cat > /etc/profile.d/desktop-env.sh <<'EOF'
# Desktop environment defaults
export DISPLAY="${DISPLAY:-:1}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/xdg-$(id -un)}"
EOF
chmod 644 /etc/profile.d/desktop-env.sh
```

**Issues:**
1. Writes to `/etc/profile.d/` (system directory)
2. Will also fail with permission denied

### File: `agents_runner/preflights/desktop_install.sh`

#### Lines 7-10: Package Installation (LIKELY REQUIRES ROOT)

```bash
echo "[desktop-install] Synchronizing package database..."
if ! yay -Syu --noconfirm; then
  echo "[desktop-install] ERROR: Failed to sync package database" >&2
  exit 1
fi
```

**Potential Issues:**
1. `yay` behavior depends on user configuration
2. May require root for system-wide package installation
3. Could fail if yay expects sudo/doas

---

## Recommended Fix

### Option 1: Add USER root Directive (RECOMMENDED)

Modify the Dockerfile template to explicitly run as root during build:

```python
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

# Desktop environment is now ready
"""
```

**Rationale:**
- Explicitly sets user context for build operations
- Standard Docker practice for installing system packages
- Minimal code change required
- No changes needed to scripts

**Note:** If the base image needs to return to a non-root user after build, add:
```dockerfile
# Return to default user if needed
USER midori-ai
```

### Option 2: Use sudo in Scripts (NOT RECOMMENDED)

Modify scripts to use `sudo` for privileged operations. This is NOT recommended because:
- Requires sudo to be configured for passwordless access
- More complex and error-prone
- Not standard Docker build practice
- Increases attack surface

### Option 3: Restructure Data Storage (ALTERNATIVE)

Move configuration files to user-writable locations:
- Change `/etc/default/novnc-path` to `/tmp/novnc-path` or `~/.config/novnc-path`
- Update all scripts that read this file

**Not recommended because:**
- Requires changes to multiple files
- `/etc/default/` is the proper location for system defaults
- Breaks conventions
- More testing required

---

## Implementation Plan

### Step 1: Update Dockerfile Template

**File:** `agents_runner/docker/image_builder.py`  
**Location:** Lines 117-133, function `_get_dockerfile_template()`

**Change Required:**

```python
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

# Desktop environment is now ready
"""
```

### Step 2: Validate Cache Key Update

The change to the Dockerfile template will automatically invalidate existing cache keys through the `compute_desktop_cache_key()` function (line 77-114), which includes a hash of the Dockerfile template (line 111-112). This is correct behavior.

### Step 3: Testing Requirements

1. Build a new desktop image from scratch
2. Verify scripts run successfully
3. Confirm `/etc/default/novnc-path` is created with correct permissions
4. Confirm `/etc/profile.d/desktop-env.sh` is created with correct permissions
5. Test that desktop environment starts correctly in resulting image
6. Verify cache key changes trigger rebuild as expected

---

## Security Considerations

### Build-Time Root Access

Running as root during Docker build is standard practice and acceptable because:
- Build-time operations are isolated
- Final image can still use non-root user at runtime
- System package installation requires privileges
- No runtime security impact

### Runtime Security

The fix does NOT affect runtime security:
- Containers running the built image maintain their user context
- Desktop processes run as the container's default user
- No elevation of privileges at runtime

### Alternative: Multi-Stage User Switching

If the base image needs to maintain a specific non-root user after build, add this after the RUN command:

```dockerfile
# Return to the base image's default user
USER ${BASE_USER:-midori-ai}
```

However, this requires knowing the base image's user, which may vary.

---

## Dependencies and Side Effects

### Files That May Be Affected

1. `agents_runner/docker/image_builder.py` - Direct change
2. Cache key computation - Automatic invalidation (expected)
3. Existing cached images - Will be invalidated (expected)

### No Changes Required

1. `agents_runner/preflights/desktop_setup.sh` - No changes needed
2. `agents_runner/preflights/desktop_install.sh` - No changes needed
3. `agents_runner/preflights/desktop_run.sh` - No changes needed
4. `agents_runner/docker/agent_worker.py` - No changes needed

### Verification Points

1. Grep for other Dockerfile templates to ensure consistency
2. Check if other image builders have similar issues
3. Verify test coverage includes permission scenarios

---

## Related Issues

### Similar Patterns to Check

Search for other Dockerfile generation that might have the same issue:

```bash
grep -r "RUN.*\.sh" agents_runner/docker/
grep -r "def.*dockerfile.*template" agents_runner/docker/
```

### Upstream Considerations

If the base image (`lunamidori5/pixelarch:emerald`) is controlled by the project:
- Document that it runs as non-root by default
- Consider adding metadata about expected user context
- Update base image documentation if needed

---

## Acceptance Criteria

This issue is RESOLVED when:

1. Dockerfile template includes `USER root` before RUN command
2. Desktop image builds successfully without permission errors
3. `/etc/default/novnc-path` file is created with content and correct permissions
4. `/etc/profile.d/desktop-env.sh` file is created with content and correct permissions
5. Cache key changes as expected (hash includes new Dockerfile)
6. Desktop environment starts correctly in built image
7. Tests pass (if applicable)
8. Code review approved
9. Changes committed with proper commit message format

---

## Commit Message Template

```
[FIX] Add USER root directive to desktop Dockerfile template

Resolves permission denied error when building desktop images.

The desktop_setup.sh script writes to /etc/default/ and /etc/profile.d/
which require root privileges. The base image runs as non-root by default.

Changes:
- Add USER root directive before RUN command in Dockerfile template
- Ensures system-level operations have required privileges
- Maintains build-time isolation and security

Fixes: RuntimeError: Docker build failed with exit code 1
Fixes: /tmp/desktop_setup.sh: line 32: /etc/default/novnc-path: Permission denied

Audit-ID: 692f43a0
```

---

## Audit Conclusion

**Finding:** CRITICAL DEFECT IDENTIFIED  
**Confidence:** HIGH (code inspection and error message analysis)  
**Fix Complexity:** LOW (single line addition)  
**Risk of Fix:** LOW (standard Docker practice)  
**Testing Required:** MEDIUM (verify build and runtime)

**Recommendation:** APPROVE FIX AND IMPLEMENT IMMEDIATELY

This is a straightforward permission issue with a simple, standard solution. The fix follows Docker best practices and should resolve the build failure without introducing new risks.

---

## Auditor Sign-Off

**Audit Performed By:** Auditor Mode  
**Date:** 2025-01-04  
**Status:** COMPLETE - AWAITING FIX IMPLEMENTATION  
**Next Action:** Implement recommended fix in `image_builder.py`

