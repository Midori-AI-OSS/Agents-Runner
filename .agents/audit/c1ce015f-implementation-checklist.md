# Part 4 Implementation Checklist

**Audit ID:** c1ce015f  
**Related:** c1ce015f-part4-preflight-ui-analysis.audit.md

Quick reference checklist for implementing Part 4 Preflight tab UI changes.

---

## Pre-Implementation

- [x] Backend fields exist (`cached_preflight_script` in Environment model)
- [x] Serialization works (serialize.py)
- [x] Docker integration complete (env_image_builder.py)
- [x] Side-by-side layout pattern identified (artifacts_tab.py)

---

## Implementation Steps

### 1. Add New Imports

**File:** `agents_runner/ui/pages/environments.py`

Add to existing imports:
```python
from PySide6.QtWidgets import QStackedWidget
from PySide6.QtWidgets import QSplitter
```

### 2. Create New Widget Instances

**File:** `agents_runner/ui/pages/environments.py` (in `__init__` after line 294)

```python
# New widgets for dual-editor mode
self._cached_preflight_enabled = QCheckBox()
self._cached_preflight_script = QPlainTextEdit()
self._run_preflight_enabled = QCheckBox()
self._run_preflight_script = QPlainTextEdit()

# Containers for layout switching
self._preflight_single_container = QWidget()
self._preflight_dual_container = QWidget()
self._preflight_stack = QStackedWidget()
```

### 3. Fix Single-Editor Label

**File:** `agents_runner/ui/pages/environments.py` (line 288)

**Before:**
```python
self._preflight_enabled = QCheckBox(
    "Enable environment preflight bash"
)
```

**After:**
```python
self._preflight_enabled = QCheckBox(
    "Enable environment preflight"
)
```

### 4. Build Single-Editor Container

**File:** `agents_runner/ui/pages/environments.py` (replace lines 306-312)

Move existing layout into container widget.

### 5. Build Dual-Editor Container

**File:** `agents_runner/ui/pages/environments.py` (after single container)

Create side-by-side layout with:
- QSplitter(Qt.Horizontal)
- Left GlassCard: "Cached preflight"
- Right GlassCard: "Run preflight"

### 6. Create Stacked Widget

**File:** `agents_runner/ui/pages/environments.py` (replace preflight_tab)

```python
preflight_tab = QWidget()
preflight_tab_layout = QVBoxLayout(preflight_tab)
preflight_tab_layout.setSpacing(TAB_CONTENT_SPACING)
preflight_tab_layout.setContentsMargins(*TAB_CONTENT_MARGINS)

self._preflight_stack.addWidget(self._preflight_single_container)  # Index 0
self._preflight_stack.addWidget(self._preflight_dual_container)    # Index 1

preflight_tab_layout.addWidget(self._preflight_stack, 1)
```

### 7. Connect Layout Toggle

**File:** `agents_runner/ui/pages/environments.py` (in `__init__` after line 183)

```python
self._container_caching_enabled.stateChanged.connect(
    self._on_container_caching_toggled
)
```

### 8. Implement Toggle Handler

**File:** `agents_runner/ui/pages/environments.py` (new method)

```python
def _on_container_caching_toggled(self, state: int) -> None:
    """Switch preflight tab layout based on container caching state."""
    is_enabled = state == Qt.CheckState.Checked.value
    self._preflight_stack.setCurrentIndex(1 if is_enabled else 0)
    
    # Optional: Migrate data between editors
    # (See full implementation in analysis doc)
```

### 9. Update Load Operation

**File:** `agents_runner/ui/pages/environments.py` (after line 489)

Add:
```python
# Load cached preflight script
cached_script = str(getattr(env, "cached_preflight_script", "") or "")
has_cached = bool(cached_script.strip())
self._cached_preflight_enabled.setChecked(has_cached)
self._cached_preflight_script.setEnabled(has_cached)
self._cached_preflight_script.setPlainText(cached_script)

# Load run preflight (mirrors existing preflight)
self._run_preflight_enabled.setChecked(bool(env.preflight_enabled))
self._run_preflight_script.setEnabled(bool(env.preflight_enabled))
self._run_preflight_script.setPlainText(env.preflight_script or "")

# Set layout state
container_caching = bool(getattr(env, "container_caching_enabled", False))
self._preflight_stack.setCurrentIndex(1 if container_caching else 0)
```

### 10. Update Save Operation

**File:** `agents_runner/ui/pages/environments_actions.py` (lines 247-269)

Replace:
```python
cached_preflight_script="",  # Will be added in Part 4
```

With:
```python
container_caching_enabled = bool(self._container_caching_enabled.isChecked())

if container_caching_enabled:
    cached_preflight_script = (
        str(self._cached_preflight_script.toPlainText() or "")
        if self._cached_preflight_enabled.isChecked()
        else ""
    )
    preflight_enabled = bool(self._run_preflight_enabled.isChecked())
    preflight_script = str(self._run_preflight_script.toPlainText() or "")
else:
    cached_preflight_script = ""
    preflight_enabled = bool(self._preflight_enabled.isChecked())
    preflight_script = str(self._preflight_script.toPlainText() or "")

# Then use these variables in Environment()
```

### 11. Update Draft Method

**File:** `agents_runner/ui/pages/environments_actions.py` (line 336)

Same logic as save operation.

---

## Verification Checklist

After implementation, test these scenarios:

### Visual Tests
- [ ] Container caching OFF: Single editor visible
- [ ] Container caching ON: Dual editors visible
- [ ] Left label reads "Cached preflight"
- [ ] Right label reads "Run preflight"
- [ ] Vertical divider exists and is draggable
- [ ] Both editors resize with window
- [ ] Checkbox label says "Enable environment preflight" (no "bash")

### Functional Tests
- [ ] Toggle container caching: Layout switches immediately
- [ ] Save with caching OFF: `preflight_script` populated
- [ ] Save with caching ON: Both scripts populated
- [ ] Load environment: Correct layout shown
- [ ] Load environment: Scripts appear in correct editors
- [ ] Checkbox states control editor enabled/disabled
- [ ] Tab changes don't cause issues

### Edge Cases
- [ ] Empty scripts handled correctly
- [ ] Toggle caching multiple times: No data loss
- [ ] Switch between environments: Layout updates correctly
- [ ] New environment: Starts with correct layout

---

## Quick Reference

### Key Files
- `agents_runner/ui/pages/environments.py` (main changes)
- `agents_runner/ui/pages/environments_actions.py` (save logic)

### Key Patterns
- Splitter: `artifacts_tab.py:60-162`
- GlassCard styling: Used throughout codebase
- Tab content margins: `TAB_CONTENT_MARGINS` constant

### Labels (Exact Text)
- Checkbox: "Enable environment preflight"
- Left editor: "Cached preflight"
- Right editor: "Run preflight"

---

## Estimated Effort

- Code changes: 2-3 hours
- Testing: 1 hour
- Total: 3-4 hours

**Complexity:** Medium (UI restructuring, data migration logic)
