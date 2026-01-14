# Task 020-2: Implement time-based phase calculation functions

## Parent Task
task-020-background-codex-cloud-bands

## Description
Create smooth oscillation functions for animating split ratio and color blending phases.

## Specific Actions
- Create method to calculate split_ratio oscillating between 0.3 and 0.6 (30/70 to 60/40)
  - Use sine/cosine or similar smooth function
  - Make period very slow (e.g., 30-60 seconds for full cycle)
- Create method to calculate color blend phase (0.0 to 1.0) for top band
  - Use sine/cosine or similar smooth function
  - Make period very slow (e.g., 20-40 seconds)
- Create method to calculate color blend phase for bottom band
  - Similar to top band but with different period for variety
- Add subtle randomness/jitter:
  - Use small Perlin-noise-like values or gentle random walk
  - Keep amplitude very small to avoid jarring motion
- Implement using continuous time (e.g., `time.time()` or QTime) to avoid frame-dependent stutter

## Code Location
`agents_runner/ui/graphics.py` - Add helper methods to `GlassRoot` class

## Technical Context
- Use `time.time()` for continuous time (already imported at line 5)
- Example formula: `0.45 + 0.15 * math.sin(time.time() / 30.0)` for split_ratio
- Suggested periods:
  - split_ratio: 45 seconds (0.3 to 0.6 range, center at 0.45)
  - color_blend_top: 35 seconds (0.0 to 1.0)
  - color_blend_bottom: 40 seconds (0.0 to 1.0, different from top)
- For jitter: use `math.sin(time.time() * 0.1) * 0.01` for subtle randomness
- Store start time in `__init__()` if relative timing needed

## Implementation Notes
- Create private methods: `_calc_split_ratio()`, `_calc_top_phase()`, `_calc_bottom_phase()`
- Use sine/cosine for smooth oscillation (avoid sawtooth or linear ramps)
- Keep jitter amplitude very small (< 2% of range)
- Test by printing values over 60+ seconds to verify smooth motion

## Dependencies
- Task 020-1 (timer infrastructure)

## Acceptance Criteria
- Functions return smooth, continuous values
- Motion is very slow and subtle
- No visible "ticking" or discrete jumps
- Values stay within expected ranges (0.3-0.6 for split, 0.0-1.0 for blend)
- Full cycle times: split 45s, top 35s, bottom 40s
