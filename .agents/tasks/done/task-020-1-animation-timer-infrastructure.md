# Task 020-1: Add animation timer infrastructure

## Parent Task
task-020-background-codex-cloud-bands

## Description
Add a slow timer mechanism to GlassRoot for background animation updates.

## Specific Actions
- Add a QTimer to GlassRoot class
- Set update frequency to ~5-10 times per second (100-200ms intervals)
- Create instance variables to store phase parameters:
  - `split_ratio` (for band position)
  - `color_blend_phase_top` (for top band color)
  - `color_blend_phase_bottom` (for bottom band color)
  - `jitter_x`, `jitter_y` (for subtle randomness)
- Connect timer timeout signal to an update method (e.g., `_update_background_animation`)
- Start timer when GlassRoot is initialized

## Code Location
`agents_runner/ui/graphics.py` - `GlassRoot` class

## Technical Context
- Current state: `_animate_orbs = False` (orb animation disabled)
- Existing pattern: `_orb_timer` uses `QTimer` with 33ms interval
- Import needed: `QTimer` already imported from `PySide6.QtCore`
- Suggested timer frequency: 100ms (10 FPS) - balance between smoothness and CPU usage
- Phase vars should be float type for smooth interpolation

## Implementation Notes
- Initialize timer in `__init__()` after theme setup (line ~208)
- Use pattern: `timer.setInterval(100)` then `timer.timeout.connect()`
- Store phase vars as instance attributes (e.g., `self._codex_split_ratio = 0.45`)
- Start timer unconditionally for Codex (unlike `_animate_orbs` which is disabled)

## Dependencies
None - this is the foundation task

## Acceptance Criteria
- Timer is properly initialized and running
- Phase parameters are stored as instance variables
- Timer callback method exists and is connected
- No visual changes yet (just infrastructure)
- Timer uses exactly 100ms interval (not range)
