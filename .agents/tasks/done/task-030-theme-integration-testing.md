# Task 030: Theme Integration Testing

## Parent Task
task-024-organize-theme-implementations (master)

## Description
Verify all themes work correctly after refactoring. Test theme switching, animations, and visual correctness for each agent.

## Specific Actions
- Test each theme individually:
  - Launch app with --agent codex
  - Launch app with --agent claude
  - Launch app with --agent gemini
  - Launch app with --agent copilot
- Verify visual output for each theme:
  - **Codex:** Two-band gradient (dark blue top, dark green bottom), diagonal boundary ~15°, soft color blob overlays, smooth color cycling
  - **Claude:** Beige/cream background, animated tree branches from edges, branches fade in over 1.8s, segments last 90s, multi-layer pen depth effect
  - **Gemini:** Dark background, four color orbs (Blue/Red/Yellow/Green), orbs bounce off edges, smooth motion with radial gradients
  - **Copilot:** Dark GitHub background, multiple panes of typing code from actual repo files, typing mistakes/backspacing, monospace font, panes scroll upward
  - Check for any visual artifacts or glitches
- Test theme switching behavior:
  - Change agent selection in settings (if applicable)
  - Verify theme updates correctly
  - Check for any state management issues
- Verify performance (compare to baseline):
  - Monitor CPU usage during animation (expected: <5% idle, <15% active)
  - Check for memory leaks over time (expected: ~50-100MB resident)
  - Verify frame rate remains stable (target: 60 FPS)
  - Run each theme for 60 seconds and compare to pre-refactor metrics
- Test edge cases:
  - Resize window during animation
  - Minimize/restore window
  - Switch between themes multiple times
- Check console for errors:
  - No import errors
  - No missing method errors
  - No state-related errors
- Run integration test if it exists:
  - Follow test instructions in `.agents/modes/TESTER.md`
  - Document any test failures

## Code Location
- Test target: All theme modules in `agents_runner/ui/themes/`
- Test driver: `main.py` and `agents_runner/ui/graphics.py`

## Technical Context
- Each theme has unique animation behavior
- State must persist correctly during theme switches
- Performance should be unchanged from before refactor
- No visual regressions allowed

## Dependencies
- Task 029 (graphics cleanup) must be complete
- All theme extraction tasks (025-028) must be complete

## Acceptance Criteria
- All four themes render correctly
- Codex: Two-band gradient with blobs
- Claude: Animated tree branches
- Gemini: Four color orbs bouncing
- Copilot: Typed code animation
- Animations are smooth and performant
- No console errors during normal operation
- Window resize and minimize work correctly
- CPU usage remains low (< 5% idle)
- No memory leaks detected
- Theme switching works if supported
- Visual output matches pre-refactor behavior
- Code runs without errors: `uv run main.py --agent [codex|claude|gemini|copilot]`
