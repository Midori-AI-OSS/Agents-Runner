# Help Button and Tooltip Implementation Analysis

**Audit ID:** e687066f  
**Date:** 2025-01-07  
**Scope:** Help button/icon and tooltip system in agents_runner UI

---

## Executive Summary

The agents_runner UI implements a **HelpIcon** widget that displays an info symbol (ⓘ) with standard hover tooltips. Contrary to what the term "help button" might suggest, these are **not clickable buttons** but rather **static labels with Qt's native hover tooltips**. The implementation is minimal, consistent, and currently used in only 2 UI pages.

---

## 1. Help Button Implementation Location

### Primary Implementation

**File:** `agents_runner/widgets/help_icon.py`

The `HelpIcon` class is a custom widget that extends `QLabel`:

```python
class HelpIcon(QLabel):
    """A small help icon that displays a tooltip on hover."""
```

**Key characteristics:**
- Inherits from `QLabel` (not `QPushButton` or `QToolButton`)
- Displays the Unicode info symbol: ⓘ
- Size: Fixed 20x20 pixels
- Cursor: `Qt.WhatsThisCursor` (question mark cursor)
- Text interaction: Disabled (`Qt.NoTextInteraction`)
- Alignment: Centered

### Widget Export

**File:** `agents_runner/widgets/__init__.py`

```python
from .help_icon import HelpIcon

__all__ = [
    # ... other widgets ...
    "HelpIcon",
]
```

---

## 2. How Tooltips Are Triggered

### Current Mechanism: Standard Hover Tooltips

The HelpIcon uses **Qt's native tooltip system** via `setToolTip()`:

```python
def __init__(self, tooltip_text: str, parent=None) -> None:
    super().__init__(parent)
    self.setText("ⓘ")
    self.setToolTip(tooltip_text)  # <-- Native Qt tooltip
    # ... styling ...
```

**Trigger behavior:**
- **Hover-activated:** Tooltip appears when mouse hovers over the icon
- **No click required:** The icon is not clickable
- **No custom event handling:** No `mousePressEvent`, `enterEvent`, or `leaveEvent` overrides
- **Qt managed:** Tooltip timing and display are handled by Qt's event system

### Comparison with Standard Widget Tooltips

The codebase uses `setToolTip()` extensively on various widgets:

**Other tooltip usage locations:**
- `agents_runner/ui/pages/task_details.py` - Container control buttons (freeze, unfreeze, stop, kill)
- `agents_runner/ui/pages/environments.py` - Form fields (max agents, desktop settings, GitHub options)
- `agents_runner/ui/pages/environments_agents.py` - Agent chain controls (up/down buttons, CLI flags)
- `agents_runner/ui/pages/environments_prompts.py` - Prompt unlock button
- `agents_runner/ui/pages/settings.py` - Settings checkboxes and fields
- `agents_runner/ui/pages/new_task.py` - Base branch dropdown, agent chain label
- `agents_runner/ui/pages/dashboard.py` - Filter and cleanup buttons
- `agents_runner/ui/pages/dashboard_row.py` - Task discard button
- `agents_runner/widgets/agent_chain_status.py` - Status indicator labels

**Key finding:** The HelpIcon uses the exact same tooltip mechanism as all other widgets in the application.

---

## 3. UI Components with Help Icon Tooltips

### Current Usage: 2 Pages

#### A. Settings Page
**File:** `agents_runner/ui/pages/settings.py` (lines 56-58)

```python
storage_help = HelpIcon(
    "Settings are saved locally in:\n~/.midoriai/agents-runner/state.json"
)
```

**Location:** Header section, next to "Settings" title  
**Purpose:** Inform users about settings storage location

#### B. Environments Page
**File:** `agents_runner/ui/pages/environments.py` (lines 77-79)

```python
storage_help = HelpIcon(
    "Environments are saved locally in:\n~/.midoriai/agents-runner/state.json"
)
```

**Location:** Header section, next to "Environments" title  
**Purpose:** Inform users about environments storage location

### Layout Pattern

Both instances follow the same pattern:

```python
header_layout.addWidget(title)           # Page title
header_layout.addWidget(storage_help)    # HelpIcon
header_layout.addStretch(1)              # Spacer
header_layout.addWidget(back, 0, Qt.AlignRight)  # Back button
```

The HelpIcon is positioned immediately after the page title in the header.

---

## 4. Converting to Standard Hover Tooltips

### Current State Analysis

**Important discovery:** The HelpIcon **already implements standard hover tooltips**. There is no click-based or button-based tooltip mechanism to convert from.

### If Converting FROM HelpIcon TO Direct Widget Tooltips

If the goal is to remove the separate HelpIcon widget and apply tooltips directly to the page titles, here's what would change:

#### Required Changes

**For Settings Page** (`agents_runner/ui/pages/settings.py`):

```python
# REMOVE:
from agents_runner.widgets import HelpIcon

storage_help = HelpIcon(
    "Settings are saved locally in:\n~/.midoriai/agents-runner/state.json"
)
header_layout.addWidget(storage_help)

# REPLACE WITH:
title.setToolTip(
    "Settings are saved locally in:\n~/.midoriai/agents-runner/state.json"
)
```

**For Environments Page** (`agents_runner/ui/pages/environments.py`):

```python
# REMOVE:
from agents_runner.widgets import HelpIcon

storage_help = HelpIcon(
    "Environments are saved locally in:\n~/.midoriai/agents-runner/state.json"
)
header_layout.addWidget(storage_help)

# REPLACE WITH:
title.setToolTip(
    "Environments are saved locally in:\n~/.midoriai/agents-runner/state.json"
)
```

#### Impact Assessment

**Benefits of removing HelpIcon:**
- Fewer widgets in layout (simpler hierarchy)
- Less visual clutter (no separate ⓘ symbol)
- One less widget class to maintain
- Consistent with how tooltips are used elsewhere in the app

**Drawbacks of removing HelpIcon:**
- Less discoverable (users may not hover over title text expecting a tooltip)
- No visual affordance indicating help is available
- Current ⓘ icon with WhatsThisCursor provides clear "this has help" signal

**Files affected:**
1. `agents_runner/ui/pages/settings.py` (remove import and usage)
2. `agents_runner/ui/pages/environments.py` (remove import and usage)
3. `agents_runner/widgets/help_icon.py` (can be deleted if no longer needed)
4. `agents_runner/widgets/__init__.py` (remove export if widget deleted)

### If Converting FROM Click-Based TO Hover-Based

**This conversion is not applicable** because the current implementation is already hover-based.

---

## 5. Tooltip Styling and Configuration

### Current Styling

The HelpIcon widget has custom styling:

```python
self.setStyleSheet(
    "color: rgba(237, 239, 245, 160);"  # Secondary text color
    "font-size: 14px;"
    "padding: 0px 4px;"
)
```

### Global Tooltip Styling

**Investigation result:** The application does **not** define global QToolTip styles in the stylesheet system.

**Checked files:**
- `agents_runner/style/sheet.py` - Main stylesheet builder
- `agents_runner/style/template_base.py` - Base template (no QToolTip styles)
- `agents_runner/style/template_tasks.py` - Tasks template (no QToolTip styles)

**Finding:** Tooltips use Qt's default styling, which respects the system theme. The app could add custom QToolTip styling if desired:

```css
QToolTip {
    background-color: rgba(18, 20, 28, 245);
    color: rgba(237, 239, 245, 255);
    border: 1px solid rgba(56, 189, 248, 120);
    padding: 8px;
    font-size: 13px;
}
```

---

## 6. Related Tooltip Usage Patterns

### Standard Widget Tooltips (Extensive Use)

The codebase makes heavy use of `setToolTip()` on standard Qt widgets:

**Pattern 1: Form field guidance**
```python
self._max_agents_running.setToolTip(
    "Maximum agents running at the same time for this environment. Set to -1 for no limit.\n"
    "Tip: For local-folder workspaces, set this to 1 to avoid agents fighting over setup/files."
)
```

**Pattern 2: Button descriptions**
```python
self._btn_freeze.setToolTip("Freeze (pause container)")
```

**Pattern 3: Dynamic tooltips**
```python
# In new_task.py
self._run_interactive.setToolTip(tooltip)  # Updated based on workspace state
self._run_agent.setToolTip(tooltip)
```

**Pattern 4: Status indicators**
```python
# In agent_chain_status.py
label.setToolTip(tooltip)  # Status icons with explanatory text
```

### Widget-Internal Tooltips

The `AgentChainStatusWidget` creates status indicator labels with tooltips:

```python
def _add_indicator(self, icon: str, tooltip: str, color: str) -> None:
    label = QLabel(icon)
    label.setToolTip(tooltip)
    label.setStyleSheet(f"color: {color}; font-weight: 600;")
    self._status_layout.addWidget(label)
```

---

## 7. Architecture Notes

### Design Philosophy

The HelpIcon follows a **visual affordance** design pattern:
- Dedicated help indicator (ⓘ) signals that help is available
- Special cursor (`WhatsThisCursor`) reinforces the help semantics
- Fixed size prevents layout shifts
- Non-interactive (no click handler) keeps it simple

### Consistency

The implementation is **consistent** with the broader codebase:
- Uses Qt's standard tooltip system (same as all other widgets)
- Follows naming conventions (`HelpIcon` matches `GlassCard`, `StatusGlyph`, etc.)
- Properly exported in `widgets/__init__.py`
- Includes docstrings with usage examples

---

## 8. Recommendations

### If Goal: Remove Separate Help Icons

**Recommendation:** Consider keeping the HelpIcon for discoverability reasons, but if removal is desired:

1. Move tooltip text directly to page title labels
2. Consider adding a visual indicator (e.g., title underline on hover) to signal tooltip presence
3. Update both Settings and Environments pages
4. Remove/deprecate `HelpIcon` class
5. Test that users can still discover the storage location information

### If Goal: Enhance Help System

**Recommendations:**
1. Add global QToolTip styling for visual consistency
2. Consider using HelpIcon more widely for complex form fields
3. Document tooltip usage patterns in `.agents/implementation/`
4. Standardize tooltip text formatting (currently uses `\n` for line breaks)

### If Goal: Convert Click-to-Hover

**Status:** Already implemented. No action needed.

---

## 9. Code Quality Assessment

### Strengths
- Clean, minimal implementation
- Proper type hints
- Good documentation (docstring with usage example)
- Follows Qt best practices
- No over-engineering

### Areas for Improvement
- Limited usage (only 2 instances)
- No global tooltip styling defined
- Could benefit from more comprehensive usage across the UI
- Tooltip text formatting is inconsistent across the codebase (some use `\n`, some are single-line)

---

## 10. Testing Considerations

### Manual Testing Required
If modifying the tooltip system, test:
1. Tooltip appearance on hover (timing, positioning)
2. Tooltip disappearance on mouse leave
3. Tooltip text readability (multi-line formatting)
4. Cursor change feedback (WhatsThisCursor behavior)
5. Keyboard accessibility (tooltips should appear on focus for accessibility)

### Current Test Coverage
**Status:** No automated tests found for HelpIcon or tooltip functionality.

---

## Appendix A: File Reference

### Files Implementing Help/Tooltip Functionality

| File | Purpose | Lines |
|------|---------|-------|
| `agents_runner/widgets/help_icon.py` | HelpIcon widget definition | 48 total |
| `agents_runner/widgets/__init__.py` | Widget exports | Export line 6 |
| `agents_runner/ui/pages/settings.py` | HelpIcon usage | 56-58, 66 |
| `agents_runner/ui/pages/environments.py` | HelpIcon usage | 77-79, 87 |

### Files Using Standard Tooltips (10+ instances each)

- `agents_runner/ui/pages/environments.py` (7 tooltip calls)
- `agents_runner/ui/pages/settings.py` (6 tooltip calls)
- `agents_runner/ui/pages/task_details.py` (4 button tooltips)
- `agents_runner/ui/pages/new_task.py` (4 tooltip calls)
- `agents_runner/ui/pages/environments_agents.py` (3 tooltip calls)
- `agents_runner/widgets/agent_chain_status.py` (dynamic tooltips)

### Style System Files

- `agents_runner/style/sheet.py` - Stylesheet builder
- `agents_runner/style/template_base.py` - Base CSS template
- `agents_runner/style/template_tasks.py` - Task-specific CSS
- `agents_runner/style/palette.py` - Color definitions
- `agents_runner/style/metrics.py` - Font and spacing

---

## Appendix B: Qt Tooltip Behavior Reference

### Default Tooltip Behavior
- **Trigger:** Mouse hover after ~700ms delay
- **Display:** Appears near cursor, auto-positioned to stay on screen
- **Duration:** Remains visible while hovering, disappears on mouse leave
- **Multi-line:** Supports `\n` line breaks
- **Rich text:** Supports basic HTML if text starts with `<`
- **Accessibility:** Automatically announced by screen readers

### Customization Options
- `QApplication.setEffectEnabled(Qt.UI_AnimateTooltip)` - Animation control
- `QToolTip.showText(pos, text, widget)` - Manual tooltip display
- `QToolTip.hideText()` - Manual tooltip dismissal
- CSS styling via `QToolTip { ... }` selector

---

## Conclusion

The agents_runner UI implements help information through a **HelpIcon widget with standard hover tooltips**. The implementation is already using Qt's native hover-based tooltip system, not a click-based mechanism. The HelpIcon provides visual affordance with an info symbol (ⓘ) and special cursor, but uses the same underlying tooltip technology as every other widget in the application.

Converting to "standard hover tooltips" would mean **removing the separate HelpIcon widget** and applying tooltips directly to other UI elements (like page titles), which would reduce visual discoverability of the help information. The current implementation provides clear signaling that help is available, at the cost of an additional widget in the layout.
