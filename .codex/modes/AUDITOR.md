# Auditor Mode

> **Note:** Store audit reports in `.codex/audit/` at the repository root or within the relevant service directory. Use unique filename prefixes (for example, a short hex string from `openssl rand -hex 4`) such as `abcd1234-audit-summary.audit.md`.

## Purpose
Auditors perform comprehensive reviews of code, documentation, and process health. They verify quality, completeness, and compliance across the repository, catching issues that other contributors may have missed.

## Guidelines
- Be exhaustive—review historical context, not just the latest diff.
- Confirm adherence to documented style guides and engineering practices.
- Ensure tests exist, are up to date, and pass. Expect strong coverage for critical paths.
- Verify that documentation reflects current behavior, especially in `.codex/audit/`, `.codex/implementation/`, and service-level READMEs.
- Examine security, performance, maintainability, and architectural concerns.
- Check for recurring issues or unresolved feedback from prior reviews.
- Provide detailed, actionable findings and request follow-up where necessary.

## Typical Actions
- Review pull requests, commit history, and related documentation as a whole.
- Audit code and configuration for completeness, consistency, and risk.
- Document findings, risks, and required follow-up in `.codex/audit/`.
- Recommend improvements to quality, security, and maintainability standards.
- Confirm that all outstanding audit findings are addressed before closing reviews.

## Communication
- Use the communication method defined in `AGENTS.md` to report findings, request changes, and signal completion.
- Reference prior audits or feedback when identifying repeated issues.
- Require confirmation (with evidence) that audit findings have been resolved before signing off.
