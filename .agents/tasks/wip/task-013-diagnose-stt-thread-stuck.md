# Task 013: Diagnose STT Thread Not Finishing

## Problem
Clicking the mic button in the `New Task` menu works the 1st time, but sometimes gets stuck on the 2nd run. The STT thread may not reach `finished` or `_stt_thread` is left non-`None`, or `FfmpegPulseRecorder.stop(...)` blocks.

## Location
- `agents_runner/ui/pages/new_task.py`
- `agents_runner/stt/mic_recorder.py` (FfmpegPulseRecorder)
- `agents_runner/stt/qt_worker.py` (SttWorker)

## Acceptance Criteria
- [ ] Reproduce the issue: use mic button twice in succession and observe if it gets stuck
- [ ] Add debug logging to track STT thread lifecycle (start, finished signal, cleanup)
- [ ] Add debug logging to FfmpegPulseRecorder.stop() to identify blocking behavior
- [ ] Identify root cause: thread not finishing, finished signal not firing, or recorder blocking
- [ ] Document findings in task file for follow-up fix task

## Notes
- Current flow: `_on_voice_toggled` → `_start_stt_recording` → creates thread/worker → `thread.finished.connect(self._on_stt_finished)` → sets `_stt_thread = None`
- Thread guard at line 623: checks if `_stt_thread is not None` and rejects new recording
- This is a diagnostic task; fix will be created based on findings
