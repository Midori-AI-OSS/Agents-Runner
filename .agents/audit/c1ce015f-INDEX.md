# Part 4 Preflight Tab UI - Audit Index

**Audit ID:** c1ce015f  
**Component:** Environment Preflight Tab Dynamic UI  
**Date:** 2025-01-08

---

## Quick Navigation

| Document | Purpose | When to Read |
|----------|---------|--------------|
| **c1ce015f-summary.md** | High-level overview and status | Start here |
| **c1ce015f-part4-preflight-ui-analysis.audit.md** | Comprehensive technical analysis | Before implementation |
| **c1ce015f-implementation-checklist.md** | Step-by-step implementation guide | During implementation |
| **c1ce015f-ui-layout-diagrams.md** | Visual layouts and diagrams | Reference during UI work |
| **c1ce015f-INDEX.md** | This document | Navigation |

---

## Recommended Reading Order

### For Implementers

1. **Start:** `c1ce015f-summary.md` (5 min read)
   - Get overview and confirm readiness
   
2. **Deep dive:** `c1ce015f-part4-preflight-ui-analysis.audit.md` (15 min read)
   - Understand current state and full plan
   
3. **Implementation:** `c1ce015f-implementation-checklist.md` (reference)
   - Follow step-by-step during coding
   
4. **Visual reference:** `c1ce015f-ui-layout-diagrams.md` (reference)
   - Check layouts and data flow as needed

### For Reviewers

1. **Start:** `c1ce015f-summary.md`
   - Understand scope and approach
   
2. **Verify:** `c1ce015f-part4-preflight-ui-analysis.audit.md`
   - Check analysis completeness
   
3. **Validate:** `c1ce015f-implementation-checklist.md`
   - Ensure all steps are covered

### For QA/Testers

1. **Context:** `c1ce015f-summary.md`
   - Understand what was built
   
2. **Test plan:** `c1ce015f-summary.md` (Testing Strategy section)
   - Execute verification steps
   
3. **Visual reference:** `c1ce015f-ui-layout-diagrams.md`
   - Compare expected vs actual layouts

---

## Document Summaries

### c1ce015f-summary.md
**Length:** 8,800 characters  
**Purpose:** Executive summary of audit findings and implementation plan  
**Key Sections:**
- Requirements summary
- Implementation approach
- Files to modify
- Testing strategy
- Success criteria

### c1ce015f-part4-preflight-ui-analysis.audit.md
**Length:** 16,140 characters  
**Purpose:** Comprehensive technical analysis and detailed implementation plan  
**Key Sections:**
- Current implementation analysis (with line numbers)
- Data model status verification
- Side-by-side layout pattern reference
- Phase-by-phase implementation plan (7 phases)
- Risk assessment
- Testing checklist

### c1ce015f-implementation-checklist.md
**Length:** 6,593 characters  
**Purpose:** Quick-reference step-by-step implementation guide  
**Key Sections:**
- Pre-implementation checklist
- 11 numbered implementation steps with code snippets
- Verification checklist (visual, functional, edge cases)
- Quick reference (key files, patterns, labels)
- Estimated effort (3-4 hours)

### c1ce015f-ui-layout-diagrams.md
**Length:** 10,973 characters  
**Purpose:** Visual representations of layouts and data flow  
**Key Sections:**
- Single-editor layout (ASCII art + hierarchy)
- Dual-editor layout (ASCII art + hierarchy)
- Layout switching behavior
- Data flow diagrams
- Migration behavior
- Visual state matrix
- Styling details

---

## Key Requirements (Quick Reference)

### Labels Must Be Exactly

```
Single mode:  "Enable environment preflight"  (NOT "bash")
Dual mode:    "Cached preflight" (left)
              "Run preflight" (right)
```

### Files to Modify

1. `agents_runner/ui/pages/environments.py` (~150 LOC)
2. `agents_runner/ui/pages/environments_actions.py` (~20 LOC)

### Implementation Pattern

```
QStackedWidget
├─ Index 0: Single-editor container (caching OFF)
└─ Index 1: Dual-editor container (caching ON)
            └─ QSplitter (Qt.Horizontal)
               ├─ GlassCard: Cached preflight
               └─ GlassCard: Run preflight
```

---

## Status Tracking

### Analysis Phase
- [x] Current implementation examined
- [x] Backend status verified (✅ complete)
- [x] Layout patterns identified
- [x] Implementation plan created
- [x] Testing strategy defined

### Implementation Phase
- [ ] Imports added
- [ ] Widget instances created
- [ ] Single-editor container built
- [ ] Dual-editor container built
- [ ] Toggle handler implemented
- [ ] Load operation updated
- [ ] Save operation updated

### Testing Phase
- [ ] Visual tests passed
- [ ] Functional tests passed
- [ ] Edge cases verified
- [ ] User acceptance complete

---

## Context & Background

### Why This Audit Exists

Part 4 completes the container caching feature by implementing the UI for managing two types of preflight scripts:
1. **Cached preflight** - Runs at image build time (cached)
2. **Run preflight** - Runs at task start time (every run)

When container caching is disabled, only the runtime preflight is needed (single editor). When enabled, both are needed (dual editors).

### Related Work

- **Part 2:** Desktop caching implementation (completed)
- **Part 3:** Container caching backend (completed)
- **Part 4:** Preflight tab UI (this audit)

### Dependencies

Backend is complete. This is purely a UI implementation that connects existing backend fields to the user interface.

---

## Common Questions

**Q: Why use QStackedWidget instead of show/hide?**  
A: QStackedWidget provides cleaner code separation, easier layout management, and is the standard Qt pattern for this use case.

**Q: What happens to existing environments when upgraded?**  
A: No migration needed. The `cached_preflight_script` field already exists with empty string default. Existing environments will load with container caching OFF, showing the single editor.

**Q: Can users have different scripts in each editor?**  
A: Yes. When container caching is ON, users can have different scripts for build-time and run-time execution.

**Q: What if a user toggles caching on and off repeatedly?**  
A: The implementation includes optional migration logic to preserve data. The UI will switch layouts instantly without data loss.

**Q: How does this affect Docker image caching?**  
A: When `cached_preflight_script` changes, the image cache key changes, triggering automatic rebuild. This is already implemented in the backend.

---

## Code References

### Key Files
- Environment model: `agents_runner/environments/model.py`
- UI page: `agents_runner/ui/pages/environments.py`
- Save logic: `agents_runner/ui/pages/environments_actions.py`
- Splitter pattern: `agents_runner/ui/pages/artifacts_tab.py`

### Key Classes
- `Environment` (line 69, model.py)
- `EnvironmentsPage` (line 53, environments.py)
- `_EnvironmentsPageActionsMixin` (line 24, environments_actions.py)

### Key Methods
- `_load_selected()` - Load environment data into UI
- `try_autosave()` - Save UI data to environment
- `_on_container_caching_toggled()` - Handle layout switching (NEW)

---

## Success Metrics

Implementation is complete when:
1. All items in checklist are checked
2. All visual tests pass
3. All functional tests pass
4. No regressions in existing functionality
5. Code follows project style guidelines
6. Documentation is updated (if needed)

---

## Maintenance Notes

### Future Considerations

If additional preflight stages are needed in the future:
1. Add new field to Environment model
2. Add new editor to dual-editor layout
3. Consider 3-way split or tabs if more than 2

### Migration Path

If script field names change:
1. Update Environment model
2. Update serialization layer
3. Update UI load/save logic
4. Add migration in serialize.py if needed

---

## Audit Metadata

- **Auditor:** GitHub Copilot (Auditor Mode)
- **Audit ID:** c1ce015f
- **Date:** 2025-01-08
- **Repository:** agents-runner
- **Component:** UI / Environment Configuration
- **Files Analyzed:** 8
- **Documents Created:** 4
- **Estimated Implementation Time:** 3-4 hours
- **Risk Level:** Low-Medium
- **Complexity:** Medium (UI restructuring)

---

## Change Log

| Date | Change | Notes |
|------|--------|-------|
| 2025-01-08 | Initial audit | Complete analysis and documentation |

---

For questions or clarifications, refer to the detailed analysis document:  
`c1ce015f-part4-preflight-ui-analysis.audit.md`
