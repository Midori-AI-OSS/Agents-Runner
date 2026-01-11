# Task: Create diagnostics bundle dialog

## Description
Build a Qt dialog that explains the diagnostics process and provides options to create a bundle or open the diagnostics folder.

## Requirements
1. Create a dialog widget in `agents_runner/widgets/`
2. Dialog should include:
   - Title: "Report an Issue"
   - Explanatory text: "This will create a diagnostics bundle you can attach to an issue."
   - Primary button: "Create diagnostics bundle"
   - Secondary button: "Open diagnostics folder"
   - Close/Cancel button
3. When "Create diagnostics bundle" is clicked:
   - Show progress indicator
   - Call bundle builder to create diagnostics bundle
   - Show success message with bundle location
   - Offer to open the bundles folder
4. When "Open diagnostics folder" is clicked:
   - Open the diagnostics bundles directory in file manager
5. Apply project styling (sharp corners)

## Acceptance Criteria
- [ ] Dialog displays clear explanation to user
- [ ] "Create diagnostics bundle" button creates a bundle
- [ ] Progress is shown during bundle creation
- [ ] Success message shows bundle location
- [ ] "Open diagnostics folder" button opens the folder in file manager
- [ ] UI follows sharp corners design constraint
- [ ] Error handling for bundle creation failures
- [ ] Type hints used throughout

## Related Tasks
- Depends on: c9e5d431, e1f7f653
- Blocks: None

## Notes
- Use QDialog as base class
- Use QProgressDialog or similar for bundle creation progress
- Use `QDesktopServices.openUrl()` to open folder in file manager
- Follow styling patterns from `agents_runner/style/`
- Create dialog at: `agents_runner/ui/dialogs/diagnostics_dialog.py`
- Dialog class name: `DiagnosticsDialog`
- Reference example: `agents_runner/ui/dialogs/cooldown_modal.py` for dialog structure
- Sharp corners: Use `border-radius: 0px` consistently (see `agents_runner/style/template_base.py`)
- Color palette: Import from `agents_runner/style/palette.py` (TEXT_PRIMARY, TEXT_PLACEHOLDER, etc.)
- Use GlassCard widget: `from agents_runner.widgets import GlassCard` for consistent styling
- Opening folder example (see `agents_runner/ui/main_window_task_review.py`):
  ```python
  from PySide6.QtGui import QDesktopServices
  from PySide6.QtCore import QUrl
  QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))
  ```
