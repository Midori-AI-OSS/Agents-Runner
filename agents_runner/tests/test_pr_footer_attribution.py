from __future__ import annotations

import inspect
import re

import pytest

from agents_runner.agent_systems import available_agent_system_names
from agents_runner.agent_systems import get_agent_system

from agents_runner.gh.task_plan import _append_pr_attribution_footer  # pyright: ignore[reportPrivateUsage]
from agents_runner.gh.task_plan import commit_push_and_pr

_CLI_FLAG_PATTERN = re.compile(r"--\w+")
_FOOTER_PLACEHOLDERS = ("{marker}", "{agent_used}", "{agents_runner_url}", "{midoriai_url}")
_FOOTER_MARKER = "<!-- midori-ai-agents-runner-pr-footer -->"
_AGENTS_RUNNER_LINK = "Created by [Midori AI Agents Runner](https://github.com/Midori-AI-OSS/Agents-Runner)"
_MIDORI_AI_LINK = "Related: [Midori AI Monorepo](https://github.com/Midori-AI-OSS/Midori-AI)"


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
    assert "{midoriai_url}" not in rendered
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


def _public_agent_system_names() -> list[str]:
    return [
        agent_name
        for agent_name in available_agent_system_names()
        if not bool(getattr(get_agent_system(agent_name), "internal_only", False))
    ]


def _footer_safety_cases() -> list[tuple[str, str | None]]:
    agent_names = _public_agent_system_names()
    cases: list[tuple[str, str | None]] = [(agent_name, None) for agent_name in agent_names]
    if agent_names:
        cases.append((agent_names[0], "Footer Safety Display"))
    return cases


def _footer_attribution_lines(rendered: str) -> list[str]:
    lines = rendered.splitlines()
    if lines and lines[0] == "---":
        return lines[1:]
    return lines


@pytest.mark.parametrize(("agent_name", "agent_display_name"), _footer_safety_cases())
def test_dynamic_pr_footer_lines_are_safe(agent_name: str, agent_display_name: str | None) -> None:
    plugin = get_agent_system(agent_name)
    assert not bool(getattr(plugin, "internal_only", False))

    rendered = _append_pr_attribution_footer(
        "",
        agent_cli=agent_name,
        agent_display_name=agent_display_name,
    )

    footer_lines = _footer_attribution_lines(rendered)
    assert len(footer_lines) == 4
    marker_line, created_by_line, agent_used_line, related_line = footer_lines

    assert marker_line == _FOOTER_MARKER
    assert _AGENTS_RUNNER_LINK in created_by_line
    assert "Agent Used:" in agent_used_line
    agent_display = agent_used_line.split("Agent Used:", maxsplit=1)[1].strip()
    assert agent_display
    assert "--" not in agent_used_line
    if agent_display_name is not None:
        assert agent_display_name in agent_used_line
    assert _MIDORI_AI_LINK in related_line
    assert _CLI_FLAG_PATTERN.search(rendered) is None
    for placeholder in _FOOTER_PLACEHOLDERS:
        assert placeholder not in rendered
