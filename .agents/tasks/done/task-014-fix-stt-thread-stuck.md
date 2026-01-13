# Task 014: Fix STT Thread Stuck Issue

## Problem
Based on findings from task-013, fix the root cause of the STT thread getting stuck on the 2nd run.

## Location
- `agents_runner/ui/pages/new_task.py`
- `agents_runner/stt/mic_recorder.py` (if recorder blocking is the issue)
- `agents_runner/stt/qt_worker.py` (if worker not finishing is the issue)

## Dependencies
- task-013 must be completed first to identify root cause

## Acceptance Criteria
- [ ] Review findings from task-013
- [ ] Implement fix based on root cause identified
- [ ] Test mic button multiple times in succession (at least 5 times)
- [ ] Verify thread cleanup happens correctly after each recording
- [ ] Verify `_stt_thread` is properly reset to `None` after each use
- [ ] No blocking behavior in FfmpegPulseRecorder.stop()

## Notes
- Do not start this task until task-013 is complete
- Fix should be minimal and targeted to the specific root cause
