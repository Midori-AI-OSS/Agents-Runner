# Task: Implement crash detection on startup

## Description
Add logic to detect if a crash report exists from a previous session and notify the user on application startup.

## Requirements
1. On application startup, check if any crash reports exist in the crash reports directory
2. If crash reports are found, show a notification to the user:
   - Small banner or dialog
   - Message: "A crash was detected. A crash report was saved."
   - Button: "Open crash report folder"
   - Option to dismiss/close
3. After showing notification, optionally mark crash reports as "seen" or move them to a subdirectory
4. Don't block application startup with this notification

## Acceptance Criteria
- [ ] Application checks for crash reports on startup
- [ ] If crash reports exist, user is notified
- [ ] Notification includes message and button to open folder
- [ ] "Open crash report folder" button opens the crash reports directory
- [ ] Notification doesn't block application from loading
- [ ] Crash reports are tracked to avoid repeated notifications
- [ ] UI follows project styling standards

## Related Tasks
- Depends on: g3h9i875
- Blocks: None

## Notes
- Consider using a non-modal banner or toast notification
- Store "last seen crash report timestamp" to avoid showing same crash repeatedly
- Use QDesktopServices to open folder
- Make notification dismissible
- Add check in `agents_runner/app.py:run_app()` after QApplication creation (around line ~84)
- After QtWebEngine initialization but before showing main window
- Use a simple QDialog or QMessageBox for notification, or create a custom banner widget
- Reference: `agents_runner/ui/dialogs/cooldown_modal.py` for dialog patterns
- Opening folder: Use `QDesktopServices.openUrl(QUrl.fromLocalFile(crash_reports_dir()))`
- Track seen crashes: Store timestamp in `~/.midoriai/diagnostics/.last_crash_notification` file
