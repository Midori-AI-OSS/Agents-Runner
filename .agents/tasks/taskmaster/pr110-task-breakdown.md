# PR #110 Task Breakdown - Summary

Created: 2025-01-13

## Source
User request to break down PR #110 comments into small, actionable tasks for coders.

## Skipped
JSON to TOML migration (marked as too hard and program is stable as-is)

## Tasks Created

### Issue 1: Template Detection Persistence (1 task)
- **task-012-template-detection-clone-persistence.md** - Record and persist midoriai_template_likelihood in cloned environments

### Issue 2: Mic Button Stuck on 2nd Run (2 tasks)
- **task-013-diagnose-stt-thread-stuck.md** - Diagnose why STT thread doesn't finish on 2nd run
- **task-014-fix-stt-thread-stuck.md** - Fix the root cause (depends on task-013)

### Issue 3: Interactive Finish Files Clutter (1 task)
- **task-015-encrypt-interactive-finish-files.md** - Encrypt finish files as artifacts and delete plaintext

### Issue 4: Directory Clutter - General (2 tasks)
- **task-016-cleanup-txt-files-edge-cases.md** - Handle TXT file cleanup edge cases (early-exit, crash)
- **task-017-cleanup-audio-edge-cases.md** - Handle audio file cleanup edge cases (early-exit, crash)

### Issue 5: Git Identity Not Set (1 task)
- **task-018-force-git-identity-agents.md** - Force git identity to "Midori AI Agent <contact-us@midori-ai.xyz>"

## Total Tasks: 7

## Notes
- Tasks 013 and 014 are sequential (diagnostic then fix)
- All other tasks are independent and can be worked in parallel
- Each task has clear acceptance criteria and location pointers
- Tasks follow verification-first approach (confirm behavior before changing)
