# Part 4 Preflight Tab UI - Audit Summary

**Audit ID:** c1ce015f  
**Date:** 2025-01-08  
**Status:** Analysis Complete, Ready for Implementation

---

## Overview

This audit provides a complete analysis and implementation plan for Part 4 of the container caching feature: Dynamic Preflight Tab UI that switches between single-editor and dual-editor layouts based on container caching state.

---

## Audit Documents

| Document | Purpose |
|----------|---------|
| `c1ce015f-part4-preflight-ui-analysis.audit.md` | Comprehensive analysis with detailed implementation plan |
| `c1ce015f-implementation-checklist.md` | Step-by-step implementation checklist |
| `c1ce015f-ui-layout-diagrams.md` | Visual diagrams and layout specifications |
| `c1ce015f-summary.md` | This document |

---

## Key Findings

### ✅ Good News

1. **Backend Complete:** The `cached_preflight_script` field already exists in:
   - Environment model (model.py:80)
   - Serialization layer (serialize.py:117)
   - Docker integration (env_image_builder.py)
   - Task creation (main_window_tasks_agent.py:268)

2. **Clear Pattern:** Side-by-side layouts with QSplitter are well-established in the codebase (see artifacts_tab.py)

3. **Simple Scope:** Only UI changes needed, no backend modifications required

### ⚠️ Issues Found

1. **Line 288:** Checkbox label includes word "bash" - needs removal
2. **Line 256:** Placeholder comment for cached_preflight_script - needs actual logic
3. **Line 311:** Static label "Preflight script" - needs to be context-aware (but will be replaced)

---

## Requirements Summary

### When Container Caching is OFF

```
┌─────────────────────────────────┐
│ ☐ Enable environment preflight  │  ← Fixed label (no "bash")
│                                 │
│ Preflight script                │
│ ┌─────────────────────────────┐ │
│ │                             │ │
│ │  [Single Editor]            │ │
│ │                             │ │
│ └─────────────────────────────┘ │
└─────────────────────────────────┘
```

### When Container Caching is ON

```
┌───────────────────────────────────────────────────────┐
│ ┌─────────────────────┬─────────────────────────────┐ │
│ │ ☐ Enable cached     │ ☐ Enable run preflight      │ │
│ │   preflight         │                             │ │
│ │                     │                             │ │
│ │ Cached preflight    │ Run preflight               │ │
│ │ ┌─────────────────┐ │ ┌─────────────────────────┐ │ │
│ │ │                 │ │ │                         │ │ │
│ │ │ [Left Editor]   │ │ │ [Right Editor]          │ │ │
│ │ │                 │ │ │                         │ │ │
│ │ └─────────────────┘ │ └─────────────────────────┘ │ │
│ └─────────────────────┴─────────────────────────────┘ │
└───────────────────────────────────────────────────────┘
```

---

## Implementation Approach

### Strategy: QStackedWidget

Use `QStackedWidget` to switch between two pre-built layouts:
- **Index 0:** Single-editor container (caching OFF)
- **Index 1:** Dual-editor container (caching ON)

### Why This Works

1. **Clean separation:** Each layout is independent
2. **Easy switching:** One line: `self._preflight_stack.setCurrentIndex(0 or 1)`
3. **No layout destruction:** Both layouts exist simultaneously
4. **Established pattern:** QStackedWidget is standard Qt for dynamic UIs

---

## Files to Modify

| File | Changes | LOC Estimate |
|------|---------|--------------|
| `agents_runner/ui/pages/environments.py` | Add imports, rebuild preflight tab, add toggle handler, update load logic | ~150 lines |
| `agents_runner/ui/pages/environments_actions.py` | Update save logic for cached_preflight_script | ~20 lines |

**Total Estimated LOC:** ~170 lines

---

## Critical Implementation Details

### 1. Exact Label Text (Requirements)

```python
# Single-editor mode
"Enable environment preflight"  # NOT "Enable environment preflight bash"

# Dual-editor mode (LEFT)
"Cached preflight"

# Dual-editor mode (RIGHT)
"Run preflight"
```

### 2. Layout Switching Signal

```python
self._container_caching_enabled.stateChanged.connect(
    self._on_container_caching_toggled
)
```

### 3. Data Mapping

| Container Caching | Cached Script Source | Runtime Script Source |
|-------------------|---------------------|----------------------|
| OFF | ❌ Empty string | ✅ `_preflight_script` |
| ON  | ✅ `_cached_preflight_script` | ✅ `_run_preflight_script` |

### 4. Save Logic Structure

```python
container_caching_enabled = bool(self._container_caching_enabled.isChecked())

if container_caching_enabled:
    # Read from dual-editor layout
    cached_preflight_script = self._cached_preflight_script.toPlainText() if enabled
    preflight_script = self._run_preflight_script.toPlainText() if enabled
else:
    # Read from single-editor layout
    cached_preflight_script = ""
    preflight_script = self._preflight_script.toPlainText() if enabled
```

---

## Testing Strategy

### Visual Verification

1. Start app with container caching OFF
   - Verify: Single editor visible
   - Verify: Label says "Enable environment preflight" (no "bash")

2. Enable container caching
   - Verify: Layout switches to dual-editor
   - Verify: Left panel labeled "Cached preflight"
   - Verify: Right panel labeled "Run preflight"
   - Verify: Vertical divider is draggable

3. Disable container caching
   - Verify: Layout switches back to single-editor

### Functional Verification

1. Save with caching OFF
   - Verify: `preflight_script` field populated
   - Verify: `cached_preflight_script` field empty

2. Save with caching ON
   - Verify: Both fields populated correctly
   - Verify: Left editor → `cached_preflight_script`
   - Verify: Right editor → `preflight_script`

3. Load environment
   - Verify: Correct layout shown based on `container_caching_enabled`
   - Verify: Scripts appear in correct editors
   - Verify: Checkbox states match saved state

### Edge Cases

1. Empty scripts
2. Toggle caching multiple times
3. Switch between environments
4. New environment creation
5. Window resize (editors should resize)

---

## Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Data loss during migration | High | Low | Test thoroughly, make migration logic bidirectional |
| Layout styling inconsistency | Medium | Low | Use existing GlassCard pattern |
| Performance issues | Low | Very Low | QStackedWidget is lightweight |
| User confusion | Medium | Medium | Clear labels, tooltips, and placeholder text |

---

## Dependencies

### Required Imports
- `QStackedWidget` (PySide6.QtWidgets)
- `QSplitter` (PySide6.QtWidgets)

### Required Widgets
- `GlassCard` (already imported)

### Required Constants
- `TAB_CONTENT_MARGINS` (already imported)
- `TAB_CONTENT_SPACING` (already imported)

---

## Success Criteria

- [x] Backend fields exist and are integrated
- [ ] Label text matches requirements exactly
- [ ] Single-editor layout works correctly
- [ ] Dual-editor layout works correctly
- [ ] Layout switching is instant and smooth
- [ ] Splitter divider is draggable
- [ ] Data saves to correct fields
- [ ] Data loads to correct editors
- [ ] No visual glitches or styling issues
- [ ] All edge cases handled

---

## Next Steps

1. **Review:** Implementer should read all audit documents
2. **Plan:** Review implementation checklist step-by-step
3. **Implement:** Follow checklist in order
4. **Test:** Execute full testing strategy
5. **Verify:** Check all success criteria

---

## Timeline Estimate

| Phase | Duration |
|-------|----------|
| Setup & imports | 15 min |
| Single-editor container | 30 min |
| Dual-editor container | 60 min |
| Toggle logic | 30 min |
| Load/save updates | 45 min |
| Testing & fixes | 60 min |
| **Total** | **3.5-4 hours** |

---

## References

### Internal Documentation
- Part 3 Implementation: `.agents/audit/3af660d3-part3-implementation-reference.md`
- Environment Model: `.agents/implementation/environments.md`

### Code References
- Side-by-side pattern: `agents_runner/ui/pages/artifacts_tab.py:60-162`
- Environment model: `agents_runner/environments/model.py:80`
- Docker integration: `agents_runner/docker/env_image_builder.py`

---

## Audit Conclusion

**Status:** ✅ Ready for Implementation

All prerequisites are in place:
- Backend infrastructure exists
- Clear implementation pattern identified
- Detailed plan documented
- Testing strategy defined

The implementation is straightforward UI work with low risk. The only significant consideration is ensuring data migration logic works correctly when users toggle container caching on and off.

**Recommendation:** Proceed with implementation following the checklist in `c1ce015f-implementation-checklist.md`.

---

**Auditor:** GitHub Copilot (Auditor Mode)  
**Date:** 2025-01-08
