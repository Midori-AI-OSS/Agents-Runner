# Task: Implement secret redaction utility

## Description
Create a utility module that can redact sensitive information from log lines and text content before including them in diagnostics bundles.

## Requirements
1. Create a `redaction.py` module in the diagnostics package
2. Implement functions to detect and redact:
   - Authorization headers (e.g., `Authorization: Bearer ...`)
   - Bearer tokens in any format
   - Cookie values
   - Access tokens, refresh tokens, API keys
   - Common secret patterns (e.g., `token=`, `api_key=`, `secret=`)
3. Provide a function that takes a string (log line or file content) and returns the redacted version
4. Replace sensitive values with `[REDACTED]` or similar placeholder

## Acceptance Criteria
- [ ] Module can identify and redact authorization headers
- [ ] Module can identify and redact bearer tokens
- [ ] Module can identify and redact cookie values
- [ ] Module can identify and redact access/refresh tokens and API keys
- [ ] Redacted content maintains line structure (don't remove lines, just redact sensitive parts)
- [ ] Code includes comprehensive type hints
- [ ] Redaction patterns are case-insensitive where appropriate

## Related Tasks
- Depends on: None
- Blocks: c9e5d431, d0f6e542

## Notes
- Use regex patterns for detection
- Consider patterns like: `(?i)(authorization|bearer|token|api[_-]?key|secret)[:\s=]+[^\s]+`
- Keep patterns maintainable and well-documented
- Create module at: `agents_runner/diagnostics/redaction.py`
- Example function signature: `def redact_secrets(text: str) -> str:`
- Patterns to detect:
  - `Authorization: Bearer [token]`
  - `Cookie: [values]`
  - `token=`, `api_key=`, `secret=`, `password=`
  - GitHub tokens (ghp_, gho_, ghs_, etc.)
