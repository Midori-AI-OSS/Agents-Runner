# UI Copy & Tooltip Polish Audit

**Audit ID:** 95cd3ae9  
**Date:** 2025-01-08  
**Scope:** User-facing UI text (labels, tooltips, placeholders) in Agents Runner application  
**Goal:** Identify opportunities to improve UI polish by:
1. Moving parenthetical explanations from labels to tooltips
2. Removing user instruction phrasing ("click here", "users can", etc.)
3. Shortening long labels with tooltip support

---

## Executive Summary

**Total Issues Found:** 8  
- **HIGH Priority:** 3 issues (parenthetical explanations in visible labels)
- **MEDIUM Priority:** 3 issues (long checkbox labels that could be shortened)
- **LOW Priority:** 2 issues (placeholder text improvements)

**Estimated LOC Changes:** ~35 lines

**Current Tooltip Infrastructure:** ✅ GOOD
- `HelpIcon` widget exists and is properly implemented (`agents_runner/widgets/help_icon.py`)
- Currently used in 2 locations (Settings and Environments page headers)
- Standard Qt `.setToolTip()` is used extensively and consistently

---

## Findings by Priority

### HIGH PRIORITY (Visible Label Polish)

#### Issue #1: Parenthetical explanation in placeholder
**File:** `agents_runner/ui/pages/environments.py:150`  
**Current:**
```python
self._max_agents_running.setPlaceholderText("-1 (unlimited)")
```
**Problem:** Parenthetical explanation `(unlimited)` clutters the placeholder  
**Recommended:**
```python
self._max_agents_running.setPlaceholderText("-1")
# Tooltip already exists and is good (lines 151-154)
```
**Lines to change:** 1

---

#### Issue #2: Parenthetical explanation in first-run setup
**File:** `agents_runner/ui/dialogs/first_run_setup.py:100`  
**Current:**
```python
instructions_label = QLabel(
    "Setup will open one terminal at a time. Complete each agent's setup "
    "before moving to the next.\n"
    "(You can configure individual agents later in Settings)"
)
```
**Problem:** Parenthetical note in visible UI text  
**Recommended:**
```python
instructions_label = QLabel(
    "Setup will open one terminal at a time. Complete each agent's setup "
    "before moving to the next."
)
instructions_label.setToolTip(
    "You can configure individual agents later in Settings → Agent CLI section."
)
```
**Lines to change:** 5 (add tooltip, remove parenthetical)

---

#### Issue #3: Parenthetical explanations in tooltips
**File:** `agents_runner/ui/pages/task_details.py:189,197,215`  
**Current:**
```python
self._btn_freeze.setToolTip("Freeze (pause container)")
self._btn_unfreeze.setToolTip("Unfreeze (unpause container)")
self._btn_kill.setToolTip("Kill container (force stop)")
```
**Problem:** Parenthetical clarifications are awkward in tooltips  
**Recommended:**
```python
self._btn_freeze.setToolTip("Freeze: Pause the container")
self._btn_unfreeze.setToolTip("Unfreeze: Resume the container")
self._btn_kill.setToolTip("Kill: Force stop the container immediately")
```
**Lines to change:** 3

---

### MEDIUM PRIORITY (Long Labels → Shorter + Tooltip)

#### Issue #4: Long checkbox label
**File:** `agents_runner/ui/pages/settings.py:133-134`  
**Current:**
```python
self._headless_desktop_enabled = QCheckBox(
    "Force headless desktop (noVNC) for all environments"
)
```
**Problem:** Label includes implementation detail `(noVNC)`  
**Recommended:**
```python
self._headless_desktop_enabled = QCheckBox(
    "Force headless desktop for all environments"
)
# Tooltip already exists (lines 136-138), add noVNC mention there if needed
```
**Lines to change:** 1

---

#### Issue #5: Long checkbox label
**File:** `agents_runner/ui/pages/environments.py:163-164`  
**Current:**
```python
self._headless_desktop_enabled = QCheckBox(
    "Enable headless desktop (noVNC) for this environment"
)
```
**Problem:** Label includes implementation detail `(noVNC)`  
**Recommended:**
```python
self._headless_desktop_enabled = QCheckBox(
    "Enable headless desktop"
)
# Tooltip already exists (lines 166-169), consider adding:
# "When enabled, agent runs will include a browser-accessible desktop via noVNC.\n..."
```
**Lines to change:** 1

---

#### Issue #6: Long checkbox label with conditional phrase
**File:** `agents_runner/ui/pages/environments.py:237-238`  
**Current:**
```python
self._gh_use_host_cli = QCheckBox(
    "Use host `gh` for clone/PR (if installed)", general_tab
)
```
**Problem:** Conditional `(if installed)` clutters the label  
**Recommended:**
```python
self._gh_use_host_cli = QCheckBox(
    "Use host `gh` CLI", general_tab
)
# Update tooltip (line 240-242) to:
# "Use the host system's `gh` CLI for cloning and PR creation (if installed).\n"
# "When disabled or unavailable, cloning uses `git` and PR creation is skipped."
```
**Lines to change:** 3

---

### LOW PRIORITY (Placeholder Text Improvements)

#### Issue #7: Very long placeholder text
**File:** `agents_runner/ui/pages/new_task.py:134-136`  
**Current:**
```python
self._command.setPlaceholderText(
    "Args for the Agent CLI (e.g. --sandbox danger-full-access or --add-dir …), or a full container command (e.g. bash)"
)
```
**Problem:** Extremely long placeholder with multiple examples  
**Note:** This field is currently hidden (line 138: `self._command.setVisible(False)`), so LOW priority  
**Recommended (if made visible):**
```python
self._command.setPlaceholderText("Agent CLI args or container command")
self._command.setToolTip(
    "Agent CLI arguments (e.g., --sandbox danger-full-access)\n"
    "or a full container command (e.g., bash)"
)
```
**Lines to change:** 4

---

#### Issue #8: Placeholder with one-per-line note
**File:** `agents_runner/ui/pages/environments.py:280`  
**Current:**
```python
self._env_vars.setPlaceholderText("# KEY=VALUE (one per line)\n")
```
**Problem:** Minor - parenthetical in placeholder  
**Recommended:**
```python
self._env_vars.setPlaceholderText("# KEY=VALUE\n")
self._env_vars.setToolTip("Enter environment variables (one per line)")
```
**Lines to change:** 2

---

## Good Patterns Found (No Changes Needed)

### ✅ Excellent HelpIcon usage
- `agents_runner/ui/pages/environments.py:77-79` (Storage location info)
- `agents_runner/ui/pages/settings.py:56-59` (Storage location info)

### ✅ Good tooltip usage patterns
- Multi-line tooltips with clear structure
- Contextual information provided
- Settings page has comprehensive tooltips for all checkboxes

### ✅ Clean button labels
- All dashboard buttons are concise ("Load more", "Clean finished tasks")
- Action buttons are clear ("Run Agent", "Run Interactive", "Get Agent Help")

---

## No Issues Found For

### User Instruction Phrasing
**Searched for:** "click", "user can", "this way"  
**Result:** ✅ No problematic phrasing found in UI text  
(Only found in placeholder text for config paths like `~/.codex`, which is appropriate)

### Tooltip Consistency
**Result:** ✅ Tooltips are used consistently across the application  
- All settings checkboxes have tooltips
- All environment checkboxes have tooltips  
- Button tooltips are present where needed

---

## Recommendations Summary

### Immediate (HIGH Priority)
1. Remove `(unlimited)` from max agents placeholder → 1 LOC
2. Move first-run setup parenthetical to tooltip → 5 LOC
3. Improve container action button tooltips → 3 LOC

### Next Phase (MEDIUM Priority)  
4. Shorten "Force headless desktop (noVNC)" → 1 LOC
5. Shorten "Enable headless desktop (noVNC)" → 1 LOC
6. Shorten "Use host `gh` for clone/PR (if installed)" → 3 LOC

### Optional (LOW Priority)
7. Improve hidden command field placeholder → 4 LOC (only if field becomes visible)
8. Add tooltip to env vars field → 2 LOC

---

## Implementation Notes

1. **HelpIcon widget is ready to use** - Consider adding more instances for:
   - Agent chain display in New Task page
   - GitHub management mode selector in Environments

2. **Tooltip patterns to follow:**
   - Multi-line for complex features
   - Start with action/state description
   - Add "Tip:" prefix for usage suggestions
   - Keep under 200 characters when possible

3. **Testing checklist after changes:**
   - Verify tooltips appear on hover
   - Check word wrap in long tooltips
   - Ensure labels fit in their containers at default window size
   - Test with different Qt themes/scales

---

## Files Modified (if all recommendations implemented)

```
agents_runner/ui/pages/environments.py          - 6 changes
agents_runner/ui/pages/settings.py              - 2 changes  
agents_runner/ui/pages/task_details.py          - 3 changes
agents_runner/ui/dialogs/first_run_setup.py     - 1 change
agents_runner/ui/pages/new_task.py              - 2 changes (LOW priority)
```

**Total:** 14 changes across 5 files  
**HIGH+MEDIUM only:** 9 changes across 4 files

---

## Code Quality Assessment

**Current State:** GOOD ✅

The UI copy is generally well-polished with only minor improvements needed. The application already:
- Uses tooltips extensively and appropriately
- Has a reusable `HelpIcon` widget for persistent help
- Avoids user instruction anti-patterns ("click here", etc.)
- Maintains consistent terminology

The issues found are cosmetic polish items rather than fundamental problems.

---

**Audit completed:** 2025-01-08  
**Auditor:** Auditor Mode (AUDITOR.md)  
**Status:** COMPLETE - Ready for review and implementation
