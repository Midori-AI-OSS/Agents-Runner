# Tor Functionality Removal Audit

**Audit ID:** f43b227f  
**Date:** 2025-01-27  
**Auditor:** Auditor Mode  
**Objective:** Identify all Tor-related functionality in the codebase for complete removal

---

## Executive Summary

This audit identifies all locations where Tor proxy functionality exists in the Agents Runner application. The Tor feature allows routing agent traffic through Tor for anonymous routing. The functionality is implemented across:

- **7 Python source files** (logic implementation)
- **3 data model files** (persistence layer)
- **1 configuration file** (Docker runner config)
- **0 dependencies** (no Tor-specific dependencies in pyproject.toml)
- **0 documentation files** (no Tor mentions in README.md)

---

## Findings

### 1. UI Components - Settings Page

**File:** `agents_runner/ui/pages/settings.py`

**Lines to Remove:**
- **Lines 132-136:** Tor checkbox widget definition
  ```python
  self._tor_enabled = QCheckBox("Enable Tor proxy (anonymous routing)")
  self._tor_enabled.setToolTip(
      "When enabled, routes all agent traffic through Tor for anonymous routing.\n"
      "This overrides the per-environment Tor setting."
  )
  ```

- **Line 174:** Tor checkbox added to grid layout
  ```python
  grid.addWidget(self._tor_enabled, 8, 0, 1, 4)
  ```

- **Line 246:** Tor setting loaded from state
  ```python
  self._tor_enabled.setChecked(bool(settings.get("tor_enabled") or False))
  ```

- **Line 272:** Tor setting saved to state
  ```python
  "tor_enabled": bool(self._tor_enabled.isChecked()),
  ```

**Impact:** Settings page displays global Tor proxy toggle

---

### 2. UI Components - Environments Page

**File:** `agents_runner/ui/pages/environments.py`

**Lines to Remove:**
- **Lines 167-171:** Tor checkbox widget definition
  ```python
  self._tor_enabled = QCheckBox("Enable Tor proxy (anonymous routing)")
  self._tor_enabled.setToolTip(
      "When enabled, routes all agent traffic through Tor for anonymous routing.\n"
      "Settings → Enable Tor proxy overrides this setting."
  )
  ```

- **Lines 197-202:** Tor row layout creation
  ```python
  tor_row = QWidget(general_tab)
  tor_layout = QHBoxLayout(tor_row)
  tor_layout.setContentsMargins(0, 0, 0, 0)
  tor_layout.setSpacing(BUTTON_ROW_SPACING)
  tor_layout.addWidget(self._tor_enabled)
  tor_layout.addStretch(1)
  ```

- **Lines 208-209:** Tor row added to grid
  ```python
  grid.addWidget(QLabel("Tor proxy"), 6, 0)
  grid.addWidget(tor_row, 6, 1, 1, 2)
  ```

- **Line 386:** Tor checkbox reset when no environment selected
  ```python
  self._tor_enabled.setChecked(False)
  ```

- **Line 413:** Tor setting loaded from environment
  ```python
  self._tor_enabled.setChecked(bool(getattr(env, "tor_enabled", False)))
  ```

**Impact:** Environment configuration page displays per-environment Tor toggle

---

### 3. UI Components - Environment Actions

**File:** `agents_runner/ui/pages/environments_actions.py`

**Lines to Remove:**
- **Line 148:** Default Tor setting when creating new environment
  ```python
  tor_enabled=False,
  ```

- **Line 240:** Tor setting saved from checkbox when saving environment
  ```python
  tor_enabled=bool(self._tor_enabled.isChecked()),
  ```

- **Line 311:** Tor setting saved from checkbox when updating environment
  ```python
  tor_enabled=bool(self._tor_enabled.isChecked()),
  ```

**Impact:** Environment creation and update logic includes Tor setting

---

### 4. Task Execution Logic

**File:** `agents_runner/ui/main_window_tasks_agent.py`

**Lines to Remove:**
- **Lines 186-188:** Tor setting resolution (global override + per-environment)
  ```python
  force_tor = bool(self._settings_data.get("tor_enabled") or False)
  env_tor = bool(getattr(env, "tor_enabled", False)) if env else False
  tor_enabled = bool(force_tor or env_tor)
  ```

- **Line 303:** Tor setting passed to Docker runner config
  ```python
  tor_enabled=tor_enabled,
  ```

**Impact:** Task launch logic resolves and applies Tor setting

---

### 5. Docker Container Execution

**File:** `agents_runner/docker/agent_worker.py`

**Lines to Remove:**
- **Lines 231-233:** Wrapping agent command with torsocks
  ```python
  # Wrap agent command with torsocks if Tor is enabled
  if tor_enabled:
      agent_cmd = f"torsocks {agent_cmd}"
  ```

- **Lines 272-283:** Tor daemon installation and startup in preflight
  ```python
  # Add Tor setup to preflight if enabled
  if tor_enabled:
      preflight_clause += (
          'echo "[tor] installing and starting Tor daemon"; '
          "if command -v yay >/dev/null 2>&1; then "
          "  yay -S --noconfirm --needed tor torsocks || true; "
          "fi; "
          "sudo tor & "
          "sleep 2; "
          'echo "[tor] Tor daemon started"; '
      )
      self._on_log("[tor] Tor proxy enabled for this task")
  ```

**Impact:** Docker container setup includes Tor installation and agent command wrapping

---

### 6. Docker Configuration Model

**File:** `agents_runner/docker/config.py`

**Lines to Remove:**
- **Line 19:** Tor enabled field in DockerRunnerConfig dataclass
  ```python
  tor_enabled: bool = False
  ```

**Impact:** Docker runner configuration includes Tor toggle field

---

### 7. Environment Data Model

**File:** `agents_runner/environments/model.py`

**Lines to Remove:**
- **Line 77:** Tor enabled field in Environment dataclass
  ```python
  tor_enabled: bool = False
  ```

**Impact:** Environment model includes Tor toggle field

---

### 8. Environment Serialization

**File:** `agents_runner/environments/serialize.py`

**Lines to Remove:**
- **Line 58:** Tor setting deserialized from JSON
  ```python
  tor_enabled = bool(payload.get("tor_enabled", False))
  ```

- **Line 198:** Tor setting passed to Environment constructor
  ```python
  tor_enabled=tor_enabled,
  ```

- **Line 264:** Tor setting serialized to JSON
  ```python
  "tor_enabled": bool(getattr(env, "tor_enabled", False)),
  ```

**Impact:** Environment persistence includes Tor setting

---

### 9. Task Persistence (No Changes Required)

**File:** `agents_runner/persistence.py`

**Finding:** This file handles task serialization but does NOT explicitly serialize/deserialize `tor_enabled`. The DockerRunnerConfig is serialized as a whole via `asdict()` (line 284), which would include the `tor_enabled` field, but there's no explicit handling.

**Lines Affected:**
- Lines 430-432: DockerRunnerConfig deserialization includes `headless_desktop_enabled` but no `tor_enabled`

**Action:** Monitor for potential issues with old task files containing `tor_enabled` in runner_config. Consider adding migration logic if needed.

---

## Dependencies

**File:** `pyproject.toml`

**Finding:** No Tor-related dependencies found. The application uses:
- `cryptography>=46.0.3`
- `pyside6>=6.10.1`

The Tor functionality relies on system packages (`tor`, `torsocks`) installed at runtime via `yay` in the container, not Python packages.

**Action:** No changes required to pyproject.toml

---

## Documentation

**File:** `README.md`

**Finding:** No mentions of Tor functionality in the README.

**Action:** No changes required to README.md

---

## Summary of Files Requiring Changes

### Critical Files (Functionality)
1. ✅ `agents_runner/ui/pages/settings.py` - 4 locations
2. ✅ `agents_runner/ui/pages/environments.py` - 5 locations
3. ✅ `agents_runner/ui/pages/environments_actions.py` - 3 locations
4. ✅ `agents_runner/ui/main_window_tasks_agent.py` - 2 locations
5. ✅ `agents_runner/docker/agent_worker.py` - 2 locations
6. ✅ `agents_runner/docker/config.py` - 1 location
7. ✅ `agents_runner/environments/model.py` - 1 location
8. ✅ `agents_runner/environments/serialize.py` - 3 locations

### Monitoring Required
- ⚠️ `agents_runner/persistence.py` - Monitor for backward compatibility issues with old task files

### No Changes Required
- ✅ `pyproject.toml` - No Tor dependencies
- ✅ `README.md` - No Tor documentation
- ✅ Other files - Only contain string matches in unrelated contexts

---

## Removal Checklist

- [ ] Remove Tor checkbox from Settings page UI
- [ ] Remove Tor checkbox from Environments page UI
- [ ] Remove Tor setting from environment create/update logic
- [ ] Remove Tor resolution logic from task launch
- [ ] Remove torsocks wrapper from agent command execution
- [ ] Remove Tor daemon installation from preflight script
- [ ] Remove `tor_enabled` field from DockerRunnerConfig
- [ ] Remove `tor_enabled` field from Environment model
- [ ] Remove Tor serialization/deserialization logic
- [ ] Test with existing state files containing `tor_enabled` settings
- [ ] Verify no runtime errors when loading old environments
- [ ] Update any internal documentation if needed

---

## Risk Assessment

**Risk Level:** LOW

**Rationale:**
- Tor functionality is cleanly isolated and not deeply integrated
- No external dependencies to remove
- Changes are localized to 8 files
- Backward compatibility concern is minimal (boolean field can be ignored)
- No database migrations required (JSON-based persistence)

**Mitigation:**
- Remove fields from data models (will be ignored when loading old data)
- Test loading existing state.json files after removal
- Verify existing tasks don't break if they have `tor_enabled` in runner_config

---

## Testing Recommendations

1. **Unit Testing:**
   - Verify Environment serialization/deserialization without `tor_enabled`
   - Verify DockerRunnerConfig initialization without `tor_enabled`
   - Verify settings page saves/loads without `tor_enabled`

2. **Integration Testing:**
   - Launch agent tasks and verify no Tor-related logic executes
   - Verify preflight scripts don't contain Tor installation
   - Verify agent commands aren't wrapped with torsocks
   - Load existing state files with `tor_enabled` settings

3. **UI Testing:**
   - Verify Settings page displays correctly without Tor checkbox
   - Verify Environments page displays correctly without Tor section
   - Verify environment creation/update works without Tor field

---

## Audit Conclusion

All Tor-related functionality has been identified and documented. The removal is straightforward with low risk. The functionality is cleanly isolated to 8 files with clear boundaries. No external dependencies need to be removed. Backward compatibility should be maintained by simply removing fields from data models (Python will ignore unknown JSON keys during deserialization).

**Status:** ✅ AUDIT COMPLETE - Ready for implementation

**Next Steps:** Proceed with systematic removal following the checklist above.
