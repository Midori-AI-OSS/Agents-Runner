# Task 016: Cleanup TXT Files Edge Cases

## Problem
TXT files clutter the `~/.midoriai/agents-runner/` directory. Need to handle edge cases like early-exit or crash before cleanup occurs.

## Location
- All locations that create TXT files in `~/.midoriai/agents-runner/`
- Likely cleanup code in finalization modules

## Acceptance Criteria
- [ ] Audit all code that creates TXT files in `~/.midoriai/agents-runner/`
- [ ] Identify existing cleanup mechanisms
- [ ] Identify edge cases where cleanup doesn't happen (early exit, crash, exception)
- [ ] Add try-finally or context manager patterns to ensure cleanup even on exception
- [ ] Add startup cleanup: on app start, remove stale TXT files older than 24 hours
- [ ] Test normal flow: verify cleanup still works
- [ ] Test exception flow: trigger early exit and verify cleanup still happens
- [ ] Test startup cleanup: create old TXT files, restart app, verify removal

## Notes
- Audio recordings already have cleanup after STT (per user note)
- Focus on TXT files other than audio-related ones
- Startup cleanup should be conservative (24+ hours old) to avoid deleting active files
