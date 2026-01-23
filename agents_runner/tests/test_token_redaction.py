from __future__ import annotations

from agents_runner.security.token_redaction import redact_tokens


def test_redact_tokens_replaces_github_tokens() -> None:
    text = "ok ghp_abcdefghijklmnopqrstuvwxyz123456 and gho_abcdefghijklmnopqrstuvwx123456"
    redacted = redact_tokens(text)
    assert "ghp_" not in redacted
    assert "gho_" not in redacted
    assert "[REDACTED]" in redacted


def test_redact_tokens_noop_on_empty() -> None:
    assert redact_tokens("") == ""
