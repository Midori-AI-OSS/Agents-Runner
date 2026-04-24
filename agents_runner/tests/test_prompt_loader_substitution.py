from __future__ import annotations

from agents_runner.prompts.loader import clear_cache
from agents_runner.prompts.loader import load_prompt


def test_load_prompt_pr_attribution_footer_substitutes_required_keys() -> None:
    clear_cache()

    rendered = load_prompt(
        "pr_attribution_footer",
        agent_used="Agent Name",
        agents_runner_url="https://example.com/runner",
        midori_ai_url="https://example.com/mono",
        marker="<!-- marker -->",
    )

    assert "https://example.com/runner" in rendered
    assert "https://example.com/mono" in rendered
    assert "Agent Used: Agent Name" in rendered
    assert "<!-- marker -->" in rendered
    assert "{agents_runner_url}" not in rendered
    assert "{midori_ai_url}" not in rendered
    assert "{agent_used}" not in rendered
    assert "{marker}" not in rendered


def test_load_prompt_pr_attribution_footer_missing_key_fails_open() -> None:
    clear_cache()

    rendered = load_prompt(
        "pr_attribution_footer",
        agent_used="Agent Name",
        midori_ai_url="https://example.com/mono",
        marker="<!-- marker -->",
    )

    # Missing one key causes format() to fail and return the raw prompt template.
    assert "{agents_runner_url}" in rendered
    assert "{midori_ai_url}" in rendered
    assert "{agent_used}" in rendered
    assert "{marker}" in rendered
