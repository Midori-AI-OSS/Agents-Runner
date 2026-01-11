# Task: Add Report an Issue UI action

## Description
Add a menu action or button in the main UI that users can click to report an issue and create a diagnostics bundle.

## Requirements
1. Add a new action to the UI (menu item, toolbar button, or both)
2. Label: "Report an Issue"
3. Connect the action to trigger the diagnostics dialog
4. Follow existing UI patterns in `agents_runner/widgets/` and styling in `agents_runner/style/`

## Acceptance Criteria
- [ ] UI includes a "Report an Issue" action
- [ ] Action is easily discoverable (in Help menu or similar)
- [ ] Action triggers the diagnostics bundle dialog
- [ ] UI follows sharp corners design constraint (no rounded borders)
- [ ] Code follows existing UI patterns in the project
- [ ] Type hints are used throughout

## Related Tasks
- Depends on: None
- Blocks: f2g8h764
- Related to: e1f7f653

## Notes
- Check `agents_runner/widgets/` for existing widget patterns
- Look at main window implementation to understand menu structure
- Keep UI code focused and minimal
- The UI does not currently have a traditional menu bar - consider adding a button to the main UI
- Check `agents_runner/ui/main_window.py` for initialization and layout structure
- Main window uses multiple mixins for functionality (see imports in main_window.py)
- Consider adding action to toolbar or creating a help/info section
- Or add to existing dialog/settings area (see `agents_runner/ui/dialogs/`)
- Follow dialog patterns in `agents_runner/ui/dialogs/cooldown_modal.py` for reference
- Sharp corners design: Use `border-radius: 0px` (see `agents_runner/style/template_base.py`)
