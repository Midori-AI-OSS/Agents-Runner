# Task: Implement settings collector with secret filtering

## Description
Create a module that collects current application settings for inclusion in diagnostics bundles, with automatic filtering of any secret values.

## Requirements
1. Create a settings collector module
2. Gather current application configuration:
   - User preferences
   - Application settings
   - Environment configuration (non-secret)
3. Apply filtering to exclude known secret settings:
   - API keys
   - Tokens
   - Passwords
   - Connection strings with credentials
4. Return settings as a structured dictionary or JSON
5. Use redaction utility for additional safety

## Acceptance Criteria
- [ ] Collector gathers current application settings
- [ ] Known secret settings are excluded
- [ ] Additional redaction applied using redaction utility
- [ ] Output is structured (dict or JSON)
- [ ] Safe to include in diagnostics bundles
- [ ] Code has type hints
- [ ] Clear documentation of what is/isn't included

## Related Tasks
- Depends on: b8d4c320
- Blocks: c9e5d431

## Notes
- Review existing settings/config modules in the project
- Create an allowlist of safe settings rather than trying to blocklist secrets
- Consider settings from: user config files, command-line args, environment variables
- Document the filtering strategy in code comments
- Create module at: `agents_runner/diagnostics/settings_collector.py`
- Settings structure to collect from:
  - `MainWindow._settings_data` dict in `agents_runner/ui/main_window.py`
  - Fields like: "use", "shell", "preflight_enabled", "host_workdir", "active_environment_id"
  - DO NOT include: Any token/key fields from `~/.codex`, `~/.copilot`, etc.
- Safe settings to include:
  - Application preferences (shell type, preflight enabled/disabled)
  - UI settings (window size, active environment)
  - Feature flags
- Settings to EXCLUDE or redact:
  - API keys, tokens, passwords
  - GitHub tokens or credentials
  - Any path containing "token", "key", "secret", "password"
- Return as JSON-serializable dict
