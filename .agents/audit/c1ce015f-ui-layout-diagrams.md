# Part 4 UI Layout Diagrams

**Audit ID:** c1ce015f  
**Component:** Preflight Tab Visual Layouts

---

## Single-Editor Layout (Container Caching OFF)

```
┌─────────────────────────────────────────────────────────────────┐
│ Preflight Tab                                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ☐ Enable environment preflight                                │
│                                                                 │
│  Preflight script                                               │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ #!/usr/bin/env bash                                       │ │
│  │ set -euo pipefail                                         │ │
│  │                                                           │ │
│  │ # Runs inside the container before the agent command.    │ │
│  │ # Runs after Settings preflight (if enabled).            │ │
│  │                                                           │ │
│  │                                                           │ │
│  │                                                           │ │
│  │                                                           │ │
│  │                                                           │ │
│  │                                                           │ │
│  │                                                           │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Widget Hierarchy:**
```
QWidget (preflight_tab)
└── QVBoxLayout
    └── QStackedWidget (_preflight_stack) [Index 0]
        └── QWidget (_preflight_single_container)
            └── QVBoxLayout
                ├── QCheckBox (_preflight_enabled)
                ├── QLabel ("Preflight script")
                └── QPlainTextEdit (_preflight_script) [stretch=1]
```

---

## Dual-Editor Layout (Container Caching ON)

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ Preflight Tab                                                                           │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│  ┌────────────────────────────────────┬──────────────────────────────────────────────┐ │
│  │ GlassCard                          │ │ GlassCard                                  │ │
│  │                                    │ │                                            │ │
│  │ ☐ Enable cached preflight          │ │ ☐ Enable run preflight                   │ │
│  │                                    │ │                                            │ │
│  │ Cached preflight                   │ │ Run preflight                              │ │
│  │ ┌────────────────────────────────┐ │ │ ┌────────────────────────────────────────┐ │ │
│  │ │ #!/usr/bin/env bash            │ │ │ │ #!/usr/bin/env bash                  │ │ │
│  │ │ set -euo pipefail              │ │ │ │ set -euo pipefail                    │ │ │
│  │ │                                │ │ │ │                                      │ │ │
│  │ │ # Runs at Docker image BUILD   │ │ │ │ # Runs at task START time            │ │ │
│  │ │ # time (cached).               │ │ │ │ # (every run).                       │ │ │
│  │ │ # Install dependencies here    │ │ │ │ # Runs after Settings preflight.     │ │ │
│  │ │ # for faster task startup.     │ │ │ │                                      │ │ │
│  │ │                                │ │ │ │                                      │ │ │
│  │ │                                │ │ │ │                                      │ │ │
│  │ │                                │ │ │ │                                      │ │ │
│  │ │                                │ │ │ │                                      │ │ │
│  │ │                                │ │ │ │                                      │ │ │
│  │ │                                │ │ │ │                                      │ │ │
│  │ │                                │ │ │ │                                      │ │ │
│  │ └────────────────────────────────┘ │ │ └────────────────────────────────────────┘ │ │
│  │                                    │ │                                            │ │
│  └────────────────────────────────────┴──────────────────────────────────────────────┘ │
│                                        ↑                                                │
│                                 Draggable divider                                       │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

**Widget Hierarchy:**
```
QWidget (preflight_tab)
└── QVBoxLayout
    └── QStackedWidget (_preflight_stack) [Index 1]
        └── QWidget (_preflight_dual_container)
            └── QVBoxLayout
                └── QSplitter (Qt.Horizontal) [stretch=1]
                    ├── GlassCard (left_panel) [stretchFactor=1]
                    │   └── QVBoxLayout
                    │       ├── QCheckBox (_cached_preflight_enabled)
                    │       ├── QLabel ("Cached preflight", bold)
                    │       └── QPlainTextEdit (_cached_preflight_script) [stretch=1]
                    │
                    └── GlassCard (right_panel) [stretchFactor=1]
                        └── QVBoxLayout
                            ├── QCheckBox (_run_preflight_enabled)
                            ├── QLabel ("Run preflight", bold)
                            └── QPlainTextEdit (_run_preflight_script) [stretch=1]
```

---

## Layout Switching Behavior

```
┌──────────────────────────────────────────────────────────────────┐
│ General Tab                                                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Container caching: ☑ Enable container caching                  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ├─ Checked → Show dual-editor layout
                              └─ Unchecked → Show single-editor layout

┌──────────────────────────────────────────────────────────────────┐
│ Preflight Tab (QStackedWidget)                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Index 0: _preflight_single_container (caching OFF)             │
│  Index 1: _preflight_dual_container (caching ON)                │
│                                                                  │
│  Current index determined by:                                   │
│    container_caching_enabled state                              │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Save Operation (Container Caching ON)

```
User Input:
  LEFT editor:  _cached_preflight_script.toPlainText()
  RIGHT editor: _run_preflight_script.toPlainText()

Save Logic:
  ├─ cached_preflight_script = LEFT editor content (if enabled)
  └─ preflight_script = RIGHT editor content (if enabled)

Environment Model:
  ├─ cached_preflight_script: str = "..." (LEFT)
  └─ preflight_script: str = "..." (RIGHT)
```

### Save Operation (Container Caching OFF)

```
User Input:
  SINGLE editor: _preflight_script.toPlainText()

Save Logic:
  ├─ cached_preflight_script = "" (empty, caching disabled)
  └─ preflight_script = SINGLE editor content (if enabled)

Environment Model:
  ├─ cached_preflight_script: str = "" (empty)
  └─ preflight_script: str = "..." (SINGLE)
```

### Load Operation

```
Environment Model:
  ├─ container_caching_enabled: bool
  ├─ cached_preflight_script: str
  ├─ preflight_enabled: bool
  └─ preflight_script: str

Display Logic:
  IF container_caching_enabled:
    ├─ Show Index 1 (dual-editor)
    ├─ LEFT editor ← cached_preflight_script
    └─ RIGHT editor ← preflight_script
  ELSE:
    ├─ Show Index 0 (single-editor)
    └─ SINGLE editor ← preflight_script
```

---

## Migration Behavior (Optional)

When user toggles container caching checkbox:

### OFF → ON (Enable Caching)

```
Before:
  _preflight_script: "echo 'setup'"

After Toggle:
  _cached_preflight_script: "" (empty, user fills manually)
  _run_preflight_script: "echo 'setup'" (migrated from single)
```

### ON → OFF (Disable Caching)

```
Before:
  _cached_preflight_script: "pip install foo"
  _run_preflight_script: "echo 'ready'"

After Toggle:
  _preflight_script: "echo 'ready'" (migrated from run)
  
Note: Cached script is preserved in model but not shown in UI
```

---

## Visual State Matrix

| Container Caching | Visible Layout | LEFT Editor      | RIGHT Editor     |
|-------------------|----------------|------------------|------------------|
| OFF               | Single         | (not visible)    | (not visible)    |
| ON                | Dual           | Cached preflight | Run preflight    |

| Checkbox State              | Editor Enabled |
|-----------------------------|----------------|
| ☑ Enable cached preflight   | LEFT = enabled |
| ☐ Enable cached preflight   | LEFT = disabled|
| ☑ Enable run preflight      | RIGHT = enabled|
| ☐ Enable run preflight      | RIGHT = disabled|
| ☑ Enable environment preflight | SINGLE = enabled |
| ☐ Enable environment preflight | SINGLE = disabled |

---

## Styling Details

### GlassCard Panels

```python
left_layout.setContentsMargins(12, 12, 12, 12)  # Compact padding
left_layout.setSpacing(8)  # Tight spacing for compact look
```

### Labels

```python
cached_label = QLabel("Cached preflight")
cached_label.setStyleSheet("font-weight: 600;")  # Bold for visibility
```

### Splitter

```python
splitter.setStretchFactor(0, 1)  # Left: 50%
splitter.setStretchFactor(1, 1)  # Right: 50%
```

Equal split (1:1 ratio) gives balanced layout for side-by-side editing.

---

## Accessibility Notes

- Both editors have clear labels above them
- Checkboxes have descriptive tooltips
- Placeholder text explains purpose of each script
- Draggable divider allows user preference for panel sizing
- Tab key navigation works across editors (setTabChangesFocus)

---

## Implementation References

- **Splitter pattern:** `agents_runner/ui/pages/artifacts_tab.py:60-162`
- **GlassCard usage:** Throughout codebase for consistent styling
- **QStackedWidget:** Standard Qt pattern for layout switching
- **Constants:** `agents_runner/ui/constants.py` (TAB_CONTENT_MARGINS, etc.)
