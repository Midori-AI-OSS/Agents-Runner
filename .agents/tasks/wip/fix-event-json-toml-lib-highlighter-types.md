Fix remaining type patterns after PySide6 enum cleanup:
1. Event method signatures: replace `event: object` with correct PySide6 event types (e.g. QResizeEvent, QShowEvent, QHideEvent) in resizeEvent/showEvent/hideEvent overrides
2. JSON/TOML boundary validation: add explicit `Any` return type annotations on json.load/tomli.load calls
3. Third-party library typing: fix spellchecker, pygments, faster_whisper type issues flagged by basedpyright
4. Log highlighter rule types: fix `list[tuple[object, QTextCharFormat]]` in log_highlighter.py
