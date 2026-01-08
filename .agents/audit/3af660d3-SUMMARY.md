# Part 3: Container Caching - Analysis Summary

**Audit ID:** 3af660d3  
**Date:** 2025-01-24  
**Status:** COMPLETE

---

## Quick Reference

**Main Analysis:** `3af660d3-part3-container-caching-analysis.audit.md`  
**Code Snippets:** `3af660d3-part3-implementation-reference.md`

---

## Overview

This audit analyzes the codebase to implement Part 3: Enable container caching toggle with two-stage preflight system. The analysis provides:

1. Complete understanding of existing architecture (Part 2 desktop caching)
2. Detailed requirements for Part 3
3. Files requiring modification
4. New fields needed in model/config
5. Comprehensive implementation plan
6. Ready-to-use code snippets

---

## Key Findings

### Architecture

**Current State (Part 2):**
- Desktop caching builds `agent-runner-desktop:<key>` with pre-installed desktop
- Single preflight script runs at task start
- image_builder.py provides solid foundation

**Proposed State (Part 3):**
- NEW toggle: "Enable container caching" (independent of desktop)
- Split preflight into:
  - **Cached preflight:** Runs at image build time (packages, system config)
  - **Run preflight:** Runs at task start (dynamic config, per-task setup)
- Layered images:
  - Base → Desktop (if enabled) → Environment
  - Each layer cached independently

### Files to Modify

**Critical Path (7 files):**
1. `agents_runner/environments/model.py` - Add 3 fields
2. `agents_runner/docker/config.py` - Add 3 fields
3. `agents_runner/docker/agent_worker.py` - Add caching + preflight logic
4. `agents_runner/docker/preflight_worker.py` - Similar updates
5. `agents_runner/environments/serialize.py` - Load/save + migration
6. `agents_runner/ui/pages/environments.py` - Add checkbox + split editors
7. `agents_runner/ui/main_window_tasks_agent.py` - Update config building

**New Files (3 files):**
8. `agents_runner/docker/env_image_builder.py` - Core builder logic
9. `agents_runner/utils/preflight_analyzer.py` - Script splitting helper
10. `agents_runner/utils/preflight_validator.py` - Validation warnings

### New Fields

**Environment Model:**
```python
cache_container_build: bool = False
cached_preflight_script: str = ""
run_preflight_script: str = ""
```

**Docker Config:**
```python
container_cache_enabled: bool = False
cached_preflight_script: str | None = None
run_preflight_script: str | None = None
```

### Implementation Plan

**4-week schedule:**
- Week 1: Model/config changes + serialization
- Week 2: Core builder logic + worker updates
- Week 3: UI updates + split editor
- Week 4: Testing + polish

---

## How Container Caching Works

### Without Container Caching (Baseline)

```
Task Start → Run preflight script → Start agent
             (installs packages)
             45-90 seconds
```

### With Container Caching

```
First Time:
  Image Build → Run cached preflight → Bake into image
                (installs packages)
                60-150 seconds (one-time cost)

Every Task:
  Task Start → Run preflight script → Start agent
               (dynamic config only)
               2-3 seconds
```

### Layered Building

**Desktop OFF, Container ON:**
```
agent-runner-env:<key>
  FROM lunamidori5/pixelarch:emerald
  RUN cached_preflight.sh
```

**Desktop ON, Container ON:**
```
Step 1: agent-runner-desktop:<desktop_key>
  FROM lunamidori5/pixelarch:emerald
  RUN desktop_install.sh + desktop_setup.sh

Step 2: agent-runner-env:<env_key>
  FROM agent-runner-desktop:<desktop_key>
  RUN cached_preflight.sh
```

---

## Example: Splitting a Preflight Script

### Original (Single Preflight)

```bash
#!/bin/bash
# Install packages
yay -S --noconfirm python-requests nodejs
# Download tool
curl -O /usr/local/bin/tool https://example.com/tool
chmod +x /usr/local/bin/tool
# Set environment
export API_KEY=${TASK_API_KEY}
mkdir -p /tmp/workspace-${TASK_ID}
```

### Split: Cached Preflight (Build Time)

```bash
#!/bin/bash
# Install packages (slow, benefits from caching)
yay -S --noconfirm python-requests nodejs
# Download tool (slow, benefits from caching)
curl -O /usr/local/bin/tool https://example.com/tool
chmod +x /usr/local/bin/tool
```

### Split: Run Preflight (Runtime)

```bash
#!/bin/bash
# Set environment (dynamic, per-task)
export API_KEY=${TASK_API_KEY}
mkdir -p /tmp/workspace-${TASK_ID}
```

---

## Cache Key Design

### Desktop Cache Key (Part 2 - Existing)

**Format:** `emerald-<base_digest>-<install_hash>-<setup_hash>-<dockerfile_hash>`

**Example:** `emerald-abc123def456-7890abcd1234-ef567890abcd-1234567890ab`

### Environment Cache Key (Part 3 - New)

**Format (desktop OFF):** `emerald-<base_digest>-<script_hash>-<dockerfile_hash>`

**Format (desktop ON):** `desktop-emerald-<desktop_key_full>-<script_hash>-<dockerfile_hash>`

**Examples:**
- Desktop OFF: `emerald-abc123def456-xyz789012345-654321fedcba`
- Desktop ON: `desktop-emerald-abc123-def456-xyz789-012345-a1b2c3d4-e5f6g7h8`

**Components:**
1. Base image key (desktop key if desktop ON, else pixelarch digest)
2. SHA256 hash of cached_preflight_script (16 chars)
3. SHA256 hash of Dockerfile template (16 chars)

**Invalidation:**
- Changing cached_preflight_script → rebuild env image
- Changing desktop scripts → rebuild both layers
- Changing run_preflight_script → NO rebuild (runtime only)

---

## Migration Strategy

### Loading Old Environments

```python
# If old environment has single preflight_script:
if old_preflight_script and not run_preflight_script:
    run_preflight_script = old_preflight_script  # Auto-migrate
    
    if container_caching_enabled and not cached_preflight_script:
        # Warn: Need to split script
        logger.warning("Container caching enabled but no cached preflight")
```

### User Experience

When user enables container caching without splitting:
1. Show warning dialog explaining split requirement
2. Offer to open Preflight tab
3. Provide auto-split helper
4. Allow "Remind Me Later" or "Disable Container Caching"

---

## Performance Expectations

### Build Times (First Run)

| Configuration | Build Time | Notes |
|--------------|------------|-------|
| Desktop only | 45-90s | Part 2 baseline |
| Container only | 10-60s | Depends on preflight |
| Both layers | 60-150s | Desktop + container |

### Startup Times (Subsequent Runs)

| Configuration | Startup | Improvement |
|--------------|---------|-------------|
| No caching | 45-90s | Baseline |
| Desktop cache | ~5s | 9-18x faster |
| Container cache | ~2s | 22-45x faster |
| Both caches | ~3s | 15-30x faster |

**Break-even Point:** After 2-3 runs, time saved exceeds build cost

---

## Risk Mitigation

### High Risks

1. **Cache invalidation bugs**
   - Mitigation: Hash entire script content
   - Validation: Test script changes trigger rebuild

2. **Layered build failures**
   - Mitigation: Comprehensive error handling, fallback to runtime
   - Validation: Test partial build failures

3. **Migration data loss**
   - Mitigation: Keep old fields, explicit migration logic
   - Validation: Load old environment, verify preservation

### Medium Risks

4. **UI complexity**
   - Mitigation: Clear tooltips, auto-split helper, warnings
   - Validation: User testing with examples

5. **Performance regression**
   - Mitigation: Cache aggressively, only build once
   - Validation: Measure cold vs warm start times

---

## Testing Checklist

### Functional Tests

- [ ] Container caching OFF: Single preflight runs at task start
- [ ] Container caching ON, desktop OFF: Env image built from pixelarch
- [ ] Container caching ON, desktop ON: Layered build (desktop → env)
- [ ] Cache invalidation: Script changes trigger rebuild
- [ ] Migration: Old environments load correctly
- [ ] Error handling: Build failures fall back to runtime

### Integration Tests

- [ ] supervisor.py passes config fields correctly
- [ ] main_window_preflight.py bridge works
- [ ] bridges.py signal connections work
- [ ] serialize.py round-trip works

### Performance Tests

- [ ] First build completes within 150 seconds
- [ ] Subsequent runs start within 5 seconds
- [ ] Cache hit detection is instant

---

## Documentation Deliverables

### User-Facing

1. **Feature Guide: Container Caching**
   - What it is, when to use it
   - How to split preflight scripts
   - Examples

2. **Migration Guide: Single to Split Preflight**
   - Step-by-step instructions
   - Common patterns
   - Troubleshooting

### Developer-Facing

3. **Architecture: Layered Image Building**
   - Image hierarchy diagram
   - Cache key computation
   - Error handling

4. **API Reference: env_image_builder.py**
   - Function signatures
   - Usage examples

---

## Next Steps

1. **Review audit documents** with team/user
2. **Clarify open questions** (see main audit doc)
3. **Begin Week 1 implementation** (model/config changes)
4. **Set up testing infrastructure** for cache validation
5. **Create UI mockups** for split preflight editor

---

## Related Documents

- **Full Analysis:** `3af660d3-part3-container-caching-analysis.audit.md` (43KB)
- **Code Snippets:** `3af660d3-part3-implementation-reference.md` (32KB)
- **Part 2 Desktop Caching:** Already implemented in `image_builder.py`

---

## Questions for Review

1. Script editor: Plain text or syntax highlighting?
2. Auto-split: Conservative or aggressive?
3. Cache cleanup: Add "Clean cached images" button?
4. Validation: Block save or warn only?
5. Migration: Auto-migrate or require user action?

Recommendations provided in main audit document.

---

**END OF SUMMARY**
