# Task 020-9: Performance optimization

## Parent Task
task-020-background-codex-cloud-bands

## Description
Profile and optimize the animated background to ensure minimal performance impact.

## Specific Actions
- Profile paint performance:
  - Measure time spent in `_paint_codex_background()`
  - Measure time spent in `_paint_band_boundary()`
  - Check overall paint event duration
  - Use QElapsedTimer or Python profiling tools
- Check CPU usage:
  - Monitor CPU usage during idle animation
  - Target < 5% CPU on modern hardware
  - Verify timer frequency is appropriate (not too frequent)
- Identify optimization opportunities:
  - Cache QColor objects if created repeatedly
  - Cache gradient objects if they can be reused
  - Consider reducing update frequency if needed (e.g., 5 Hz instead of 10 Hz)
  - Optimize any expensive calculations
- Implement optimizations:
  - Apply caching where beneficial
  - Reduce unnecessary repaints
  - Adjust timer frequency if needed
- Re-profile after optimizations to confirm improvements

## Code Location
`agents_runner/ui/graphics.py` - `GlassRoot` class

## Technical Context
- Profiling imports needed: `from PySide6.QtCore import QElapsedTimer`
- Current disabled animation uses 33ms timer (30 FPS) for orbs
- Suggested timer: 100ms (10 FPS) - reduces CPU by 66% vs 33ms
- CPU target: < 3% on modern hardware (more specific than generic < 5%)
- Memory: avoid per-frame allocations (cache QColor, QLinearGradient objects)

## Implementation Notes
- Profile paint performance:
  ```python
  timer = QElapsedTimer()
  timer.start()
  # ... paint code ...
  elapsed = timer.elapsed()  # milliseconds
  ```
- Measure in `_paint_codex_background()` and `_paint_band_boundary()`
- Check CPU with system monitor (htop/Task Manager) during idle animation
- Optimization checklist:
  - [ ] Cache top/bottom QColor objects if blend phase unchanged
  - [ ] Cache QLinearGradient if boundary position unchanged
  - [ ] Verify timer frequency (100ms recommended, could increase to 150ms if needed)
  - [ ] Profile color calculation overhead
  - [ ] Profile gradient creation overhead
- Potential optimizations:
  - Store last phase values, skip color recalc if change < 0.01
  - Store last gradient object, reuse if boundary_y unchanged
  - Reduce timer frequency to 150ms (6.67 FPS) if 100ms still too high
- Re-profile after each optimization to confirm improvement

## Dependencies
- Task 020-8 (readability testing complete)

## Acceptance Criteria
- Paint performance is smooth (no dropped frames)
- CPU usage is minimal during idle animation (< 3% target)
- No performance regression compared to previous background
- Animation remains smooth after optimizations
- Code is clean and maintainable
- Paint method execution time < 5ms consistently
- No memory leaks from per-frame allocations
