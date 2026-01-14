# Task 020-7: Test and validate visual output

## Parent Task
task-020-background-codex-cloud-bands

## Description
Verify that the animated background meets all visual specifications and quality standards.

## Specific Actions
- Launch application with `agent_cli=codex`
- Observe animation for several minutes:
  - Verify transitions are slow and subtle (no visible "ticking")
  - Confirm split ratio drifts between approximately 30/70 and 60/40
  - Confirm top band cycles between LightBlue (#ADD8E6) and DarkOrange (#FF8C00)
  - Confirm bottom band cycles between two dark grays
  - Verify boundary is soft and "airy" (not a crisp line)
- Check for visual artifacts:
  - No banding in gradients
  - No flickering or stuttering
  - Smooth motion throughout
- Test at different window sizes:
  - Resize window and verify background scales properly
  - Check that boundary position remains proportional

## Code Location
Testing in running application

## Technical Context
- Launch command: `uv run main.py` (from AGENTS.md line 9)
- Agent selection: set via theme selection in UI (check settings/preferences)
- Current window resize handler: `resizeEvent()` at line 244 (should work with new background)
- Verification tools: visual inspection, no automated tests required per AGENTS.md

## Implementation Notes
- Launch with: `uv run main.py`
- Select Codex agent/theme in UI
- Observe for 3-5 minutes minimum to see full cycle
- Checklist:
  - [ ] Split ratio visibly drifts (count seconds, verify ~45s period)
  - [ ] Top band color cycles blue → orange → blue
  - [ ] Bottom band subtle gray variation visible
  - [ ] Boundary is soft/feathered (not crisp line)
  - [ ] No stutter or frame drops
  - [ ] No gradient banding artifacts
- Test window resizing:
  - [ ] Resize to minimum (check boundary scales)
  - [ ] Resize to maximum (check boundary scales)
  - [ ] Rapid resize (check for visual glitches)
- Verify colors match hex spec:
  - LightBlue: #ADD8E6 (RGB 173, 216, 230)
  - DarkOrange: #FF8C00 (RGB 255, 140, 0)

## Dependencies
- Task 020-6 (integration complete)

## Acceptance Criteria
- All visual specifications from original task are met
- Animation is smooth and continuous
- Boundary blend is visibly soft
- Colors match specification (verify with color picker tool if needed)
- Split ratio range is correct (30/70 to 60/40)
- No visual glitches observed
- Full cycle time approximately 45 seconds for split ratio
