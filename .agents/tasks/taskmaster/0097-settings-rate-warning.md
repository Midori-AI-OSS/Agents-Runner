# Settings Red Warning for High-Polling Environments

**Scope:** `agents_runner/ui/pages/settings_form.py` (SettingsFormMixin) or the settings page that renders `github_poll_interval_s` / `github_polling_enabled`.
**Dependencies:** none (UI-only)
**Prerequisite gap:** `github_poll_interval_s` currently has NO UI widget anywhere in the settings form. It exists only as a default/coercion value in `main_window_settings.py` (line 383-385) and is consumed by the coordinator (`_poll_interval_s()` at line 1014). The settings form renders `github_polling_enabled` (checkbox, row 3) and `github_poll_startup_delay_s` (QLineEdit, row 6), but never exposes the polling interval for user editing. This task MUST first add a `github_poll_interval_s` widget (slider or QLineEdit with validator) to the Github Config pane before any warning label can be placed near it.

## Outcome
When more than 10 polling-enabled environments exist AND the global polling interval is less than 2 minutes, the settings page shows an informative red-text warning with a tooltip mentioning global rate-limit pace impact.

## Acceptance Criteria

1. **Add `github_poll_interval_s` widget (prerequisite):**
    - Add a `QLineEdit` with `QIntValidator(5, 3600)` or a `QSpinBox` (range 5–3600, suffix "s") to the Github Config pane in `settings_form.py`, placed near the existing `_github_polling_enabled` checkbox and `_github_poll_startup_delay_s` field (around row 5–7 in the grid).
    - Label: `"Polling interval (s)"`.
    - Bind to the existing `github_poll_interval_s` settings key (already loaded/coerced in `main_window_settings.py:383-385` and consumed by the coordinator). Wire into the auto-save collection logic so changes persist.
    - Add the corresponding hint attribute in `agents_runner/ui/_mixin_hints.py`.

2. **Detection logic:**
    - Count environments where `github_polling_enabled == True` AND `resolve_environment_github_repo(env) is not None` (i.e., environments that actually have a GitHub repo).
    - If count > 10 AND `github_poll_interval_s < 120` → warning active.

3. **UI widget:**
    - A red `QLabel` (styled with `color: #ef4444; font-weight: 600;`) placed immediately below the new polling interval widget.
    - Text: `"Warning: {N} polling-enabled environments with interval <2 min may exceed GitHub rate limits at the current pace."` where `{N}` is the actual count.
    - Tooltip on the label: `"Each poll cycle sends multiple API requests per environment. At this pace, the global account-wide rate limit (5,000 req/hr) could be exhausted. Increase the interval or reduce polling-enabled environments to stay within safe limits."`

4. **Reactivity:**
    - The warning updates in real time as the user changes the interval (via the new widget) or toggles polling-enabled checkboxes on the Environments page.
    - When the condition is no longer met (count drops to <=10 or interval >= 120), the label hides.

5. **Placement:**
    - Wire this into the existing settings form's Github Config pane (`github_config` page in `settings_form.py`). Place the interval widget and warning label alongside the existing `github_polling_enabled` checkbox and `github_poll_startup_delay_s` field.
    - Do not create a new settings page or pane.

6. **No new config keys** (the interval key already exists; the warning is purely derived).

## Implementation Notes
- **The interval widget is the primary work item for this task.** Without it, the warning has no anchor point and no user-editable interval to react to.
- Use `QSignalBlocker` if needed to avoid feedback loops when hiding/showing the warning label.
- The tooltip content is fixed; no need for i18n or external template files.
- Environment count must react to changes on the Environments page (polling toggles). Coordinate with the environments form's checkbox signals.
- The settings form likely auto-saves on changes; the interval widget should follow the same pattern as the existing `_github_poll_startup_delay_s` QLineEdit.
