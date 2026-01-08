# Part 3: Container Caching Implementation Checklist

**Audit ID:** 3af660d3  
**Date:** 2025-01-24  
**Status:** Ready for Implementation

Use this checklist to track implementation progress. Update status as work completes.

---

## Pre-Implementation Review

- [ ] All audit documents reviewed by team
- [ ] Open questions answered (see INDEX.md)
- [ ] Implementation approach approved
- [ ] Timeline (4 weeks) confirmed
- [ ] Assigned to: ___________________

---

## Week 1: Foundation (Model & Config)

### Day 1-2: Model Changes

**File:** `agents_runner/environments/model.py`

- [ ] Add field: `cache_container_build: bool = False`
- [ ] Add field: `cached_preflight_script: str = ""`
- [ ] Add field: `run_preflight_script: str = ""`
- [ ] Keep deprecated fields: `preflight_enabled`, `preflight_script`
- [ ] Test: Environment instantiation works
- [ ] Code review completed

**File:** `agents_runner/docker/config.py`

- [ ] Add field: `container_cache_enabled: bool = False`
- [ ] Add field: `cached_preflight_script: str | None = None`
- [ ] Add field: `run_preflight_script: str | None = None`
- [ ] Add field: `container_run_preflight_path: str = "/tmp/..."`
- [ ] Keep deprecated field: `environment_preflight_script`
- [ ] Test: DockerRunnerConfig instantiation works
- [ ] Code review completed

### Day 3-4: Serialization & Migration

**File:** `agents_runner/environments/serialize.py`

- [ ] Update `_load_environment_v1()`: Load new fields
- [ ] Add migration logic: `preflight_script` → `run_preflight_script`
- [ ] Add warning: Container caching ON but no cached preflight
- [ ] Update `_save_environment()`: Save new fields
- [ ] Test: Load old environment file (backward compat)
- [ ] Test: Save new environment with split preflight
- [ ] Test: Round-trip (save → load → verify)
- [ ] Test: Migration warning appears when appropriate
- [ ] Code review completed

### Day 5: Environment Image Builder Skeleton

**File:** `agents_runner/docker/env_image_builder.py` (NEW)

- [ ] Create file with module docstring
- [ ] Import dependencies (hashlib, subprocess, etc.)
- [ ] Define `compute_env_cache_key()` function
- [ ] Define `_get_env_dockerfile_template()` function
- [ ] Write unit tests for cache key computation
- [ ] Test: Cache key changes when script changes
- [ ] Test: Cache key changes when dockerfile changes
- [ ] Test: Cache key includes base image key
- [ ] Code review completed

---

## Week 2: Core Logic (Image Building & Workers)

### Day 1-2: Environment Image Builder Implementation

**File:** `agents_runner/docker/env_image_builder.py` (continued)

- [ ] Implement `build_env_image()` function
  - [ ] Create temp directory for build context
  - [ ] Write cached_preflight.sh to temp dir
  - [ ] Write Dockerfile to temp dir
  - [ ] Run docker build with streaming logs
  - [ ] Handle timeout (600s)
  - [ ] Handle build failures
- [ ] Implement `ensure_env_image()` function
  - [ ] Determine base layer (desktop or pixelarch)
  - [ ] Compute env cache key
  - [ ] Check if image exists
  - [ ] Build if missing
  - [ ] Handle errors gracefully (fallback to base)
- [ ] Test: Build env image from pixelarch
- [ ] Test: Build env image from desktop image
- [ ] Test: Cache hit detection works
- [ ] Test: Build failure falls back gracefully
- [ ] Test: Streaming logs appear
- [ ] Code review completed

### Day 3: Agent Worker Updates

**File:** `agents_runner/docker/agent_worker.py`

- [ ] Add container caching logic after desktop caching (~line 257)
  - [ ] Extract `container_cached` and `cached_preflight` from config
  - [ ] Call `ensure_env_image()` if enabled
  - [ ] Update `runtime_image` to env image
  - [ ] Handle errors (log and fallback)
  - [ ] Log cache HIT/MISS
- [ ] Update preflight_clause building (~line 382-397)
  - [ ] Add run_preflight_tmp_path handling
  - [ ] Write run preflight script to temp file
  - [ ] Mount run preflight as read-only
  - [ ] Add to preflight_clause
  - [ ] Keep backward compatibility with old environment_preflight
- [ ] Test: Container caching OFF (no change)
- [ ] Test: Container caching ON, desktop OFF
- [ ] Test: Container caching ON, desktop ON (layered)
- [ ] Test: Fallback on build failure
- [ ] Test: Backward compatibility with old preflight
- [ ] Code review completed

### Day 4: Preflight Worker Updates

**File:** `agents_runner/docker/preflight_worker.py`

- [ ] Add container caching logic (similar to agent_worker)
- [ ] Update preflight_clause building (similar to agent_worker)
- [ ] Test: Preflight container caching works
- [ ] Test: Backward compatibility
- [ ] Code review completed

### Day 5: Integration Testing

- [ ] Test: supervisor.py passes config correctly
- [ ] Test: Config fields flow through entire stack
- [ ] Test: Logs show correct image being used
- [ ] Test: Cache invalidation triggers rebuild
- [ ] Integration tests pass
- [ ] Week 2 milestone review

---

## Week 3: UI (Checkbox & Split Editor)

### Day 1: Container Caching Checkbox

**File:** `agents_runner/ui/pages/environments.py`

- [ ] Add `_cache_container_build` checkbox widget (~line 178)
  - [ ] Set text: "Enable container caching"
  - [ ] Set tooltip (explain two-stage preflight)
  - [ ] Initially unchecked (default OFF)
- [ ] Update layout (~line 207-210)
  - [ ] Add checkbox to headless_desktop_layout
  - [ ] Adjust spacing
- [ ] Update `_on_env_loaded()` (~line 422)
  - [ ] Load `cache_container_build` field
  - [ ] Set checkbox state
- [ ] Update `_gather_environment_for_save()` (~line 250)
  - [ ] Get checkbox state
  - [ ] Set `cache_container_build` field
- [ ] Test: Checkbox appears in UI
- [ ] Test: State persists (save → load)
- [ ] Test: Independent of desktop checkbox
- [ ] Code review completed

### Day 2-3: Split Preflight Editor

**File:** `agents_runner/ui/pages/environments.py` (Preflight tab)

- [ ] Add preflight mode selector
  - [ ] Radio button: "Single preflight (legacy)"
  - [ ] Radio button: "Split preflight (container caching)"
  - [ ] Connect toggled signal to handler
- [ ] Create tabbed editor widget
  - [ ] Tab 1: Single Preflight (legacy)
  - [ ] Tab 2: Cached Preflight (build time)
  - [ ] Tab 3: Run Preflight (runtime)
  - [ ] Add placeholder text to each
- [ ] Add warning label
  - [ ] Explain cached preflight runs as ROOT
  - [ ] Style with orange color
- [ ] Implement mode change handler
  - [ ] Enable/disable appropriate editors
  - [ ] Show/hide tabs
- [ ] Update load method
  - [ ] Detect mode based on fields
  - [ ] Load into appropriate editors
- [ ] Update save method
  - [ ] Save from active editor
  - [ ] Clear inactive fields
- [ ] Test: Mode selector works
- [ ] Test: Editors enable/disable correctly
- [ ] Test: Data loads into correct editor
- [ ] Test: Data saves from correct editor
- [ ] Code review completed

### Day 4: Task Agent Window Updates

**File:** `agents_runner/ui/main_window_tasks_agent.py`

- [ ] Extract container caching config (~line 266)
  - [ ] Get `cache_container_build` from env
  - [ ] Get `cached_preflight_script` from env
  - [ ] Get `run_preflight_script` from env
  - [ ] Keep legacy `preflight_script` for backward compat
- [ ] Update DockerRunnerConfig building (~line 422)
  - [ ] Pass `container_cache_enabled`
  - [ ] Pass `cached_preflight_script` (or None)
  - [ ] Pass `run_preflight_script` (or None)
  - [ ] Keep `environment_preflight_script` for backward compat
- [ ] Test: Config built correctly
- [ ] Test: Fields passed to supervisor
- [ ] Code review completed

### Day 5: Actions & Bridges

**File:** `agents_runner/ui/pages/environments_actions.py`

- [ ] Update action handlers if needed
- [ ] Test: Actions trigger correctly

**File:** `agents_runner/ui/bridges.py`

- [ ] Verify signal connections work
- [ ] Test: Signals emit correctly

**Week 3 Integration:**
- [ ] Test: UI → Config → Worker flow works
- [ ] Test: Checkbox state triggers caching
- [ ] Test: Split preflight saves correctly
- [ ] Week 3 milestone review

---

## Week 4: Polish (Helper & Validation)

### Day 1-2: Preflight Analyzer Utility

**File:** `agents_runner/utils/preflight_analyzer.py` (NEW)

- [ ] Create file with module docstring
- [ ] Define `ScriptLine` dataclass
- [ ] Implement `analyze_preflight_script()` function
- [ ] Implement pattern detection helpers:
  - [ ] `_is_package_install()`
  - [ ] `_is_download_binary()`
  - [ ] `_is_system_config()`
  - [ ] `_is_static_directory()`
  - [ ] `_is_env_var_export()`
  - [ ] `_uses_task_variable()`
  - [ ] `_is_temp_directory()`
- [ ] Write unit tests for each pattern
- [ ] Test: Correctly categorizes package installs
- [ ] Test: Correctly categorizes exports
- [ ] Test: Correctly categorizes temp dirs
- [ ] Test: Handles ambiguous lines safely
- [ ] Code review completed

### Day 2-3: Auto-Split Helper Dialog

**File:** `agents_runner/ui/pages/environments.py` (Preflight tab)

- [ ] Add "Auto-split Helper" button
- [ ] Implement `_show_split_helper_dialog()` method
  - [ ] Read single preflight script
  - [ ] Call `analyze_preflight_script()`
  - [ ] Show suggestions in dialog
  - [ ] Allow user to review/adjust
  - [ ] Populate cached and run editors
- [ ] Test: Dialog opens correctly
- [ ] Test: Suggestions appear
- [ ] Test: User can adjust categorization
- [ ] Test: Editors populate on confirm
- [ ] Code review completed

### Day 3: Preflight Validator

**File:** `agents_runner/utils/preflight_validator.py` (NEW)

- [ ] Create file with module docstring
- [ ] Implement `validate_cached_preflight()` function
  - [ ] Warn about task variables in cached preflight
  - [ ] Warn about dynamic paths in cached preflight
- [ ] Implement `validate_run_preflight()` function
  - [ ] Warn about package installs in run preflight
  - [ ] Suggest moving to cached preflight
- [ ] Add validation to save action
  - [ ] Call validators on save
  - [ ] Show warnings in dialog
  - [ ] Allow user to proceed or cancel
- [ ] Test: Validation detects issues
- [ ] Test: Warnings appear
- [ ] Test: User can proceed despite warnings
- [ ] Code review completed

### Day 4: Manual Testing

**Test Case 1: Container caching OFF**
- [ ] Setup: Disable container caching
- [ ] Run: Start task
- [ ] Verify: Single preflight runs at task start
- [ ] Verify: No env images built
- [ ] Verify: Behavior matches baseline

**Test Case 2: Container caching ON, desktop OFF**
- [ ] Setup: Enable container caching, disable desktop
- [ ] Setup: Split preflight script
- [ ] Run: Start task (first time)
- [ ] Verify: Env image builds from pixelarch
- [ ] Verify: Cached preflight runs at build time
- [ ] Verify: Run preflight runs at task start
- [ ] Run: Start task (second time)
- [ ] Verify: Cache HIT, no rebuild
- [ ] Verify: Faster startup

**Test Case 3: Container caching ON, desktop ON**
- [ ] Setup: Enable both caching toggles
- [ ] Run: Start task (first time)
- [ ] Verify: Desktop image builds first
- [ ] Verify: Env image builds FROM desktop image
- [ ] Verify: Layered correctly (inspect layers)
- [ ] Run: Start task (second time)
- [ ] Verify: Both caches hit
- [ ] Verify: Very fast startup

**Test Case 4: Cache invalidation**
- [ ] Setup: Task with cached images
- [ ] Action: Change cached_preflight_script
- [ ] Run: Start task
- [ ] Verify: Env image rebuilds
- [ ] Action: Change desktop scripts
- [ ] Run: Start task
- [ ] Verify: Both images rebuild
- [ ] Action: Change run_preflight_script
- [ ] Run: Start task
- [ ] Verify: NO rebuild (runtime only)

**Test Case 5: Migration**
- [ ] Setup: Load environment with old single preflight
- [ ] Verify: Loads without errors
- [ ] Verify: Single preflight → run_preflight
- [ ] Action: Enable container caching
- [ ] Verify: Warning shown (need to split)
- [ ] Action: Split script using auto-helper
- [ ] Verify: Cached and run preflights populated
- [ ] Run: Start task
- [ ] Verify: Caching works

**Test Case 6: Error handling**
- [ ] Setup: Invalid cached preflight script (syntax error)
- [ ] Run: Start task
- [ ] Verify: Build fails
- [ ] Verify: Error shown in logs
- [ ] Verify: Falls back to runtime execution
- [ ] Verify: Task completes (slower but works)

### Day 5: Documentation & Review

- [ ] Write user-facing documentation:
  - [ ] Feature guide: What is container caching
  - [ ] Migration guide: How to split preflight
  - [ ] Best practices: What goes where
- [ ] Write developer documentation:
  - [ ] Architecture diagram
  - [ ] Cache key computation
  - [ ] Error handling strategy
- [ ] Update ARCHITECTURE.md (if exists)
- [ ] Update README.md (if needed)
- [ ] Final code review
- [ ] Performance benchmarking
- [ ] Week 4 milestone review

---

## Post-Implementation

### Deployment

- [ ] Create release notes
- [ ] Update version number
- [ ] Tag release in git
- [ ] Build and test release candidate
- [ ] Deploy to production

### Monitoring

- [ ] Monitor cache hit rates
- [ ] Monitor build times
- [ ] Monitor disk usage
- [ ] Monitor error rates
- [ ] Collect user feedback

### Maintenance

- [ ] Address user-reported issues
- [ ] Document common pitfalls
- [ ] Update FAQ
- [ ] Plan future enhancements

---

## Success Validation

### Functional Requirements
- [ ] Container caching toggle works independently
- [ ] Both toggles can be enabled simultaneously
- [ ] Cached preflight runs at build time
- [ ] Run preflight runs at task start
- [ ] Cache invalidation works correctly
- [ ] Build failures fall back gracefully
- [ ] Old environments migrate without data loss
- [ ] UI clearly explains split preflight

### Performance Requirements
- [ ] First build completes within 150 seconds
- [ ] Subsequent runs start within 5 seconds
- [ ] Cache hit detection is instant
- [ ] Break-even point is 2-3 runs

### Quality Requirements
- [ ] No regressions in existing functionality
- [ ] Error messages are clear and actionable
- [ ] Logs show which image layer is being used
- [ ] Validation catches common mistakes
- [ ] Documentation covers all use cases

---

## Sign-Off

- [ ] Implementation complete
- [ ] All tests passing
- [ ] Documentation complete
- [ ] Code reviewed and approved
- [ ] Performance validated
- [ ] Ready for deployment

**Implementer:** ___________________  
**Reviewer:** ___________________  
**Date:** ___________________  

---

**END OF CHECKLIST**
