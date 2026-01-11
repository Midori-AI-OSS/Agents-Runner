# Task: Add diagnostics documentation

## Description
Document the diagnostics and crash reporting system for users and developers.

## Requirements
1. Add user-facing documentation:
   - How to report an issue using the UI
   - Where diagnostics bundles are stored
   - What information is included in bundles
   - What information is redacted/excluded
2. Add developer documentation:
   - How the diagnostics system works
   - How to add breadcrumb logs
   - How to extend the system
   - Testing recommendations
3. Update relevant README or help documentation

## Acceptance Criteria
- [ ] User documentation explains how to create diagnostics bundles
- [ ] Documentation explains what data is included/excluded
- [ ] Developer documentation explains system architecture
- [ ] Documentation explains how to add breadcrumbs
- [ ] Documentation is clear and concise
- [ ] No emoticons or emoji (per AGENTS.md guidelines)

## Related Tasks
- Depends on: f2g8h764, h4i0j986
- Blocks: None

## Notes
- Update `.agents/` documentation if appropriate
- Consider adding a help section in the UI
- Document the redaction rules clearly for user trust
- Include example of diagnostics bundle contents structure
- Documentation locations:
  - User docs: Add to README.md or create docs/diagnostics.md
  - Developer docs: Create `.agents/implementation/diagnostics-system.md`
  - Architecture: Document in `.agents/implementation/` with module overview
- Key points to document:
  - How to trigger diagnostics bundle creation (UI button location)
  - What data is collected (version, OS, logs, task state, settings)
  - What data is redacted (tokens, keys, passwords, authorization headers)
  - Where bundles are saved (`~/.midoriai/diagnostics/bundles/`)
  - Where crash reports are saved (`~/.midoriai/diagnostics/crash_reports/`)
  - How to add breadcrumbs in code: `from agents_runner.diagnostics.breadcrumbs import add_breadcrumb`
- Follow AGENTS.md guidelines: No emoticons or emoji
- Keep documentation concise and technical
