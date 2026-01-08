# Part 4 Preflight Tab UI Analysis

**Audit ID:** c1ce015f  
**Component:** Environment Preflight Tab UI  
**Status:** Analysis Complete  
**Date:** 2025-01-08

---

## Executive Summary

This audit analyzes the current Preflight tab implementation and provides a comprehensive plan for implementing Part 4: Dynamic preflight editor UI that switches between single-editor and dual-editor layouts based on container caching state.

### Key Requirements

1. **When container caching is OFF:**
   - Show ONE preflight editor (existing runtime preflight)
   - Fix label: Use `Enable environment preflight` (remove word "bash")

2. **When container caching is ON:**
   - Show TWO editors side-by-side with vertical divider
   - LEFT: `Cached preflight` (runs at image build time)
   - RIGHT: `Run preflight` (runs at task start each run)
   - Labels MUST be exactly: `Cached preflight` and `Run preflight`
   - Existing runtime preflight moves to RIGHT editor
   - Both editors must resize to fill available window space

3. **General:**
   - Remove any `bash` wording from labels in this area

---

## Current Implementation

### File: `agents_runner/ui/pages/environments.py`

#### Current Preflight Tab Structure (Lines 287-312)

```python
self._preflight_enabled = QCheckBox(
    "Enable environment preflight bash"  # LINE 288 - NEEDS FIX
)
self._preflight_enabled.setToolTip(
    "Runs after Settings preflight script.\n"
    "Use for environment-specific setup tasks."
)
self._preflight_script = QPlainTextEdit()
self._preflight_script.setPlaceholderText(
    "#!/usr/bin/env bash\n"
    "set -euo pipefail\n"
    "\n"
    "# Runs inside the container before the agent command.\n"
    "# Runs after Settings preflight (if enabled).\n"
)
self._preflight_script.setTabChangesFocus(True)
self._preflight_enabled.toggled.connect(self._preflight_script.setEnabled)
self._preflight_script.setEnabled(False)

preflight_tab = QWidget()
preflight_layout = QVBoxLayout(preflight_tab)
preflight_layout.setSpacing(TAB_CONTENT_SPACING)
preflight_layout.setContentsMargins(*TAB_CONTENT_MARGINS)
preflight_layout.addWidget(self._preflight_enabled)
preflight_layout.addWidget(QLabel("Preflight script"))  # LINE 311 - DYNAMIC LABEL NEEDED
preflight_layout.addWidget(self._preflight_script, 1)
```

#### Current Load Operation (Lines 487-489)

```python
self._preflight_enabled.setChecked(bool(env.preflight_enabled))
self._preflight_script.setEnabled(bool(env.preflight_enabled))
self._preflight_script.setPlainText(env.preflight_script or "")
```

#### Current Save Operation (environments_actions.py:257-258)

```python
preflight_enabled=bool(self._preflight_enabled.isChecked()),
preflight_script=str(self._preflight_script.toPlainText() or ""),
cached_preflight_script="",  # LINE 256 - PLACEHOLDER
```

### Container Caching Checkbox

Located at line 185-193 in environments.py:

```python
self._container_caching_enabled = QCheckBox(
    "Enable container caching"
)
self._container_caching_enabled.setToolTip(
    "When enabled, environment preflight scripts are executed at Docker build time.\n"
    "This creates a cached image with pre-installed dependencies, speeding up task startup.\n\n"
    "The cached preflight script is configured in the Preflight tab.\n"
    "Image is automatically rebuilt when the cached preflight script changes."
)
```

This checkbox state drives the dynamic UI in the Preflight tab.

---

## Data Model Status

### Environment Model (agents_runner/environments/model.py:80)

```python
@dataclass
class Environment:
    # ... other fields ...
    container_caching_enabled: bool = False  # Line 79
    cached_preflight_script: str = ""        # Line 80 - EXISTS!
    preflight_enabled: bool = False          # Line 81
    preflight_script: str = ""               # Line 82
```

**Status:** ✅ Field already exists in model, serialization, and Docker integration.

### Existing Integration Points

1. **Serialization:** `agents_runner/environments/serialize.py:117` - reads/writes cached_preflight_script
2. **Docker Config:** `agents_runner/docker/config.py:21` - includes cached_preflight_script field
3. **Task Creation:** `agents_runner/ui/main_window_tasks_agent.py:268-269` - reads field from environment
4. **Image Builder:** `agents_runner/docker/env_image_builder.py` - builds cached images with script

---

## Side-by-Side Layout Pattern

### Reference: artifacts_tab.py (Lines 60-162)

The codebase uses `QSplitter` for side-by-side layouts with resizable dividers:

```python
splitter = QSplitter(Qt.Horizontal)
splitter.setChildrenCollapsible(False)

left_panel = GlassCard()
left_layout = QVBoxLayout(left_panel)
left_layout.setContentsMargins(18, 16, 18, 16)
left_layout.setSpacing(10)
# ... add widgets to left_layout ...

right_panel = GlassCard()
right_layout = QVBoxLayout(right_panel)
right_layout.setContentsMargins(18, 16, 18, 16)
right_layout.setSpacing(12)
# ... add widgets to right_layout ...

splitter.addWidget(left_panel)
splitter.addWidget(right_panel)
splitter.setStretchFactor(0, 1)  # Left panel: stretch factor 1
splitter.setStretchFactor(1, 2)  # Right panel: stretch factor 2

layout.addWidget(splitter, 1)  # Add with stretch factor
```

**Key Pattern Details:**
- Use `Qt.Horizontal` for vertical divider (side-by-side)
- `setChildrenCollapsible(False)` prevents panels from collapsing
- Each panel is a `GlassCard` for consistent styling
- Use `setStretchFactor` to control initial size ratio
- Add splitter with stretch factor 1 to fill available space

---

## Implementation Plan

### Phase 1: Add New UI Widgets

Create new instance variables in `EnvironmentsPage.__init__`:

```python
# New widgets for dual-editor mode
self._cached_preflight_enabled = QCheckBox("Enable cached preflight")
self._cached_preflight_script = QPlainTextEdit()
self._run_preflight_enabled = QCheckBox("Enable run preflight")
self._run_preflight_script = QPlainTextEdit()

# Container for dynamic layout switching
self._preflight_single_container = QWidget()
self._preflight_dual_container = QWidget()
```

### Phase 2: Build Single-Editor Layout

Replace current simple layout with a container widget:

```python
# Single editor mode (container caching OFF)
single_layout = QVBoxLayout(self._preflight_single_container)
single_layout.setSpacing(TAB_CONTENT_SPACING)
single_layout.setContentsMargins(0, 0, 0, 0)

# Fix label: remove "bash"
self._preflight_enabled.setText("Enable environment preflight")

single_layout.addWidget(self._preflight_enabled)
single_layout.addWidget(QLabel("Preflight script"))
single_layout.addWidget(self._preflight_script, 1)
```

### Phase 3: Build Dual-Editor Layout

Create side-by-side layout with QSplitter:

```python
# Dual editor mode (container caching ON)
dual_layout = QVBoxLayout(self._preflight_dual_container)
dual_layout.setSpacing(TAB_CONTENT_SPACING)
dual_layout.setContentsMargins(0, 0, 0, 0)

splitter = QSplitter(Qt.Horizontal)
splitter.setChildrenCollapsible(False)

# LEFT: Cached preflight editor
left_panel = GlassCard()
left_layout = QVBoxLayout(left_panel)
left_layout.setContentsMargins(12, 12, 12, 12)
left_layout.setSpacing(8)

self._cached_preflight_enabled.setText("Enable cached preflight")
self._cached_preflight_enabled.setToolTip(
    "Runs at Docker image build time.\n"
    "Install dependencies and perform setup that can be cached.\n"
    "Image is automatically rebuilt when this script changes."
)

cached_label = QLabel("Cached preflight")
cached_label.setStyleSheet("font-weight: 600;")

self._cached_preflight_script.setPlaceholderText(
    "#!/usr/bin/env bash\n"
    "set -euo pipefail\n"
    "\n"
    "# Runs at Docker image BUILD time (cached).\n"
    "# Install dependencies here for faster task startup.\n"
)
self._cached_preflight_script.setTabChangesFocus(True)
self._cached_preflight_enabled.toggled.connect(
    self._cached_preflight_script.setEnabled
)

left_layout.addWidget(self._cached_preflight_enabled)
left_layout.addWidget(cached_label)
left_layout.addWidget(self._cached_preflight_script, 1)

# RIGHT: Run preflight editor
right_panel = GlassCard()
right_layout = QVBoxLayout(right_panel)
right_layout.setContentsMargins(12, 12, 12, 12)
right_layout.setSpacing(8)

self._run_preflight_enabled.setText("Enable run preflight")
self._run_preflight_enabled.setToolTip(
    "Runs at task START time (each run).\n"
    "Use for per-task setup or dynamic configuration.\n"
    "Runs after Settings preflight (if enabled)."
)

run_label = QLabel("Run preflight")
run_label.setStyleSheet("font-weight: 600;")

self._run_preflight_script.setPlaceholderText(
    "#!/usr/bin/env bash\n"
    "set -euo pipefail\n"
    "\n"
    "# Runs at task START time (every run).\n"
    "# Runs after Settings preflight.\n"
)
self._run_preflight_script.setTabChangesFocus(True)
self._run_preflight_enabled.toggled.connect(
    self._run_preflight_script.setEnabled
)

right_layout.addWidget(self._run_preflight_enabled)
right_layout.addWidget(run_label)
right_layout.addWidget(self._run_preflight_script, 1)

splitter.addWidget(left_panel)
splitter.addWidget(right_panel)
splitter.setStretchFactor(0, 1)  # Equal sizing
splitter.setStretchFactor(1, 1)

dual_layout.addWidget(splitter, 1)
```

### Phase 4: Create Stacked Layout for Tab

Replace the simple preflight tab with a stacked layout:

```python
preflight_tab = QWidget()
preflight_tab_layout = QVBoxLayout(preflight_tab)
preflight_tab_layout.setSpacing(TAB_CONTENT_SPACING)
preflight_tab_layout.setContentsMargins(*TAB_CONTENT_MARGINS)

# Create stacked widget to switch between layouts
self._preflight_stack = QStackedWidget()
self._preflight_stack.addWidget(self._preflight_single_container)  # Index 0
self._preflight_stack.addWidget(self._preflight_dual_container)    # Index 1

preflight_tab_layout.addWidget(self._preflight_stack, 1)
```

### Phase 5: Connect Container Caching Checkbox

Add signal connection in `__init__`:

```python
# Connect container caching toggle to layout switch
self._container_caching_enabled.stateChanged.connect(
    self._on_container_caching_toggled
)
```

Implement the handler:

```python
def _on_container_caching_toggled(self, state: int) -> None:
    """Switch preflight tab layout based on container caching state.
    
    When OFF: Show single editor (existing runtime preflight)
    When ON: Show dual editors (cached + run preflight)
    """
    is_enabled = state == Qt.CheckState.Checked.value
    
    if is_enabled:
        # Show dual-editor layout
        self._preflight_stack.setCurrentIndex(1)
        
        # Migrate existing runtime preflight to run preflight
        if self._preflight_enabled.isChecked():
            self._run_preflight_enabled.setChecked(True)
            if self._preflight_script.toPlainText().strip():
                self._run_preflight_script.setPlainText(
                    self._preflight_script.toPlainText()
                )
    else:
        # Show single-editor layout
        self._preflight_stack.setCurrentIndex(0)
        
        # Migrate run preflight back to runtime preflight
        if self._run_preflight_enabled.isChecked():
            self._preflight_enabled.setChecked(True)
            if self._run_preflight_script.toPlainText().strip():
                self._preflight_script.setPlainText(
                    self._run_preflight_script.toPlainText()
                )
```

### Phase 6: Update Load Operation

Modify `_load_selected` method (after line 489):

```python
# Existing load (keep for single-editor mode)
self._preflight_enabled.setChecked(bool(env.preflight_enabled))
self._preflight_script.setEnabled(bool(env.preflight_enabled))
self._preflight_script.setPlainText(env.preflight_script or "")

# New: Load cached preflight script (for dual-editor mode)
cached_script = str(getattr(env, "cached_preflight_script", "") or "")
has_cached = bool(cached_script.strip())
self._cached_preflight_enabled.setChecked(has_cached)
self._cached_preflight_script.setEnabled(has_cached)
self._cached_preflight_script.setPlainText(cached_script)

# New: Load run preflight (same as existing preflight)
self._run_preflight_enabled.setChecked(bool(env.preflight_enabled))
self._run_preflight_script.setEnabled(bool(env.preflight_enabled))
self._run_preflight_script.setPlainText(env.preflight_script or "")

# Set initial layout based on container caching state
container_caching = bool(getattr(env, "container_caching_enabled", False))
self._preflight_stack.setCurrentIndex(1 if container_caching else 0)
```

### Phase 7: Update Save Operation

Modify `try_autosave` in environments_actions.py (around line 256):

```python
# Determine which editors to read based on container caching state
container_caching_enabled = bool(self._container_caching_enabled.isChecked())

if container_caching_enabled:
    # Read from dual-editor layout
    cached_preflight_script = (
        str(self._cached_preflight_script.toPlainText() or "")
        if self._cached_preflight_enabled.isChecked()
        else ""
    )
    preflight_enabled = bool(self._run_preflight_enabled.isChecked())
    preflight_script = str(self._run_preflight_script.toPlainText() or "")
else:
    # Read from single-editor layout
    cached_preflight_script = ""
    preflight_enabled = bool(self._preflight_enabled.isChecked())
    preflight_script = str(self._preflight_script.toPlainText() or "")

env = Environment(
    # ... other fields ...
    container_caching_enabled=container_caching_enabled,
    cached_preflight_script=cached_preflight_script,  # FIX LINE 256
    preflight_enabled=preflight_enabled,
    preflight_script=preflight_script,
    # ... rest of fields ...
)
```

---

## Files Requiring Modification

### Primary Files

1. **agents_runner/ui/pages/environments.py**
   - Lines 287-312: Rebuild preflight tab with dynamic layout
   - Line 288: Fix checkbox label (remove "bash")
   - After line 489: Update `_load_selected` method
   - Add new method: `_on_container_caching_toggled`
   - Imports: Add `QStackedWidget`, `QSplitter`

2. **agents_runner/ui/pages/environments_actions.py**
   - Lines 247-269: Update `try_autosave` method
   - Line 256: Replace placeholder with actual cached_preflight_script logic
   - Lines 331-336: Update `_draft_environment_from_form` (similar logic)

### Testing Checklist

After implementation, verify:

1. ✅ Label says "Enable environment preflight" (not "bash")
2. ✅ Container caching OFF: Single editor visible
3. ✅ Container caching ON: Dual editors visible with vertical divider
4. ✅ Left editor labeled "Cached preflight"
5. ✅ Right editor labeled "Run preflight"
6. ✅ Splitter divider is draggable
7. ✅ Both editors resize to fill window
8. ✅ Toggling container caching switches layout
9. ✅ Existing preflight script migrates to run preflight when enabled
10. ✅ Cached preflight saves to `cached_preflight_script` field
11. ✅ Run preflight saves to `preflight_script` field
12. ✅ Load operation restores both scripts correctly
13. ✅ Checkbox states control editor enabled/disabled state

---

## Risk Assessment

### Low Risk
- Label text changes
- Layout switching logic
- Data field already exists in model

### Medium Risk
- Migration logic between single/dual editors (user data loss potential)
- Tab layout rebuild may affect existing styling

### Mitigation
- Test migration logic thoroughly with various states
- Preview changes visually before committing
- Keep migration logic reversible (both directions)
- Use existing `GlassCard` pattern to maintain styling consistency

---

## References

- **Part 3 Implementation:** `.agents/audit/3af660d3-part3-implementation-reference.md`
- **Environment Model:** `agents_runner/environments/model.py:80`
- **Side-by-Side Pattern:** `agents_runner/ui/pages/artifacts_tab.py:60-162`
- **UI Constants:** `agents_runner/ui/constants.py`

---

## Audit Notes

- All backend infrastructure for `cached_preflight_script` is already in place
- No database migration needed
- UI is the only missing piece
- Pattern for side-by-side layouts is well-established in codebase
- Implementation is straightforward with clear pattern to follow

**Status:** Ready for implementation.
