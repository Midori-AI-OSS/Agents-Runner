from __future__ import annotations

import inspect

from agents_runner.gh.task_plan import _append_pr_attribution_footer  # pyright: ignore[reportPrivateUsage]
from agents_runner.gh.task_plan import commit_push_and_pr


def test_append_pr_attribution_footer_substitutes_placeholders() -> None:
    rendered = _append_pr_attribution_footer(
        "PR body",
        agent_cli="codex",
    )

    assert "<!-- midori-ai-agents-runner-pr-footer -->" in rendered
    assert "https://github.com/Midori-AI-OSS/Agents-Runner" in rendered
    assert "https://github.com/Midori-AI-OSS/Midori-AI" in rendered
    assert "Agent Used:" in rendered
    assert "{marker}" not in rendered
    assert "{agents_runner_url}" not in rendered
    assert "{midori_ai_url}" not in rendered
    assert "{agent_used}" not in rendered


def test_append_pr_attribution_footer_does_not_duplicate_existing_marker() -> None:
    body = "PR body\n<!-- midori-ai-agents-runner-pr-footer -->"

    rendered = _append_pr_attribution_footer(body, agent_cli="codex")

    assert rendered == body + "\n"


def test_append_pr_attribution_footer_handles_empty_body() -> None:
    rendered = _append_pr_attribution_footer("", agent_cli="")

    assert rendered.startswith("---\n<!-- midori-ai-agents-runner-pr-footer -->")
    assert "Agent Used: (unknown)" in rendered


def _assert_agent_display(rendered: str, expected_text: str) -> None:
    assert f"Agent Used: [{expected_text}]" in rendered


def test_footer_opencode_tui() -> None:
    rendered = _append_pr_attribution_footer(
        "body",
        agent_cli="opencode",
        agent_display_name="OpenCode TUI",
    )
    _assert_agent_display(rendered, "OpenCode TUI")
    assert "https://github.com/anomalyco/opencode" in rendered


def test_footer_opencode_web() -> None:
    rendered = _append_pr_attribution_footer(
        "body",
        agent_cli="opencode",
        agent_display_name="OpenCode Web",
    )
    _assert_agent_display(rendered, "OpenCode Web")
    assert "https://github.com/anomalyco/opencode" in rendered


def test_footer_aider() -> None:
    rendered = _append_pr_attribution_footer("body", agent_cli="aider")
    assert "Agent Used: aider" in rendered


def test_footer_claude_code() -> None:
    rendered = _append_pr_attribution_footer("body", agent_cli="claude")
    _assert_agent_display(rendered, "Claude Code")
    assert "https://github.com/anthropics/claude-code" in rendered


def test_footer_codex() -> None:
    rendered = _append_pr_attribution_footer("body", agent_cli="codex")
    _assert_agent_display(rendered, "OpenAI Codex")
    assert "https://github.com/openai/codex" in rendered


def test_footer_copilot() -> None:
    rendered = _append_pr_attribution_footer("body", agent_cli="copilot")
    _assert_agent_display(rendered, "Github Copilot")
    assert "https://github.com/github/copilot-cli" in rendered


def test_footer_gemini() -> None:
    rendered = _append_pr_attribution_footer("body", agent_cli="gemini")
    _assert_agent_display(rendered, "Google Gemini")
    assert "https://github.com/google-gemini/gemini-cli" in rendered


def test_footer_qwen() -> None:
    rendered = _append_pr_attribution_footer("body", agent_cli="qwen")
    _assert_agent_display(rendered, "Qwen")
    assert "https://github.com/QwenLM/qwen-code" in rendered


def test_pr_footer_helpers_do_not_accept_cli_flag_arguments() -> None:
    assert "agent_cli_args" not in inspect.signature(_append_pr_attribution_footer).parameters
    assert "agent_cli_args" not in inspect.signature(commit_push_and_pr).parameters


def test_footer_opencode_web_no_args() -> None:
    rendered = _append_pr_attribution_footer(
        "body",
        agent_cli="opencode",
        agent_display_name="OpenCode Web",
    )
    _assert_agent_display(rendered, "OpenCode Web")
