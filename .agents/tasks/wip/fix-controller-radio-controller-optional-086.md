# Task: Fix pyright errors in agents_runner/ui/radio/controller.py

## File
File: `agents_runner/ui/radio/controller.py`
Lines: 145, 146

## Category
`radio-controller-optional`

## Errors
```
  Line 145: Object of type "None" cannot be called (reportOptionalCall)
  Line 146: Object of type "None" cannot be called (reportOptionalCall)
```

## Fix
`QAudioOutput` and `QMediaPlayer` are set to `None` on import failure (lines 28-29).
Add a guard before calling constructors at lines 145-146, e.g.:
```
if QAudioOutput is not None:
    self._audio_output = QAudioOutput(self)
if QMediaPlayer is not None:
    self._player = QMediaPlayer(self)
```
Or add `# pyright: ignore[reportOptionalCall]` on each line.

## Verification
```bash
uv run pyright agents_runner/ui/radio/controller.py
```
