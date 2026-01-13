# Task 017: Cleanup Audio Recording Edge Cases

## Problem
Audio recordings clutter the directory when early-exit or crash occurs before cleanup. Audio deletion after STT is already implemented; need to handle edge cases.

## Location
- `agents_runner/stt/mic_recorder.py`
- `agents_runner/ui/pages/new_task.py` (STT cleanup at lines 709-738)
- All locations that create audio recordings

## Acceptance Criteria
- [ ] Review existing audio cleanup code in `new_task.py:_on_stt_done` and `_on_stt_error`
- [ ] Identify edge cases where audio files are not cleaned up (crash, exception, thread not finishing)
- [ ] Add try-finally or context manager patterns to ensure cleanup even on exception
- [ ] Add startup cleanup: on app start, remove stale audio files older than 24 hours from `~/.midoriai/agents-runner/`
- [ ] Test normal flow: verify cleanup still works
- [ ] Test exception flow: force STT error and verify audio cleanup
- [ ] Test crash simulation: kill process during recording, restart app, verify stale audio removed

## Notes
- Existing cleanup is at new_task.py lines 709-738
- Focus on ensuring cleanup happens even in failure scenarios
- Startup cleanup should target known audio file patterns (e.g., `*.wav`, `*.mp3`, `mic-recording-*.wav`)
