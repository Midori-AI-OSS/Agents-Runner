from __future__ import annotations

from agents_runner.gh.task_plan import _append_pr_attribution_footer  # pyright: ignore[reportPrivateUsage]


def test_append_pr_attribution_footer_substitutes_placeholders() -> None:
    rendered = _append_pr_attribution_footer(
        "PR body",
        agent_cli="codex",
        agent_cli_args="--model gpt-5",
    )

    assert "<!-- midori-ai-agents-runner-pr-footer -->" in rendered
    assert "https://github.com/Midori-AI-OSS/Agents-Runner" in rendered
    assert "https://github.com/Midori-AI-OSS/Midori-AI" in rendered
    assert "Agent Used:" in rendered
    assert "--model gpt-5" in rendered
    assert "{marker}" not in rendered
    assert "{agents_runner_url}" not in rendered
    assert "{midori_ai_url}" not in rendered
    assert "{agent_used}" not in rendered


def test_append_pr_attribution_footer_does_not_duplicate_existing_marker() -> None:
    body = "PR body\n<!-- midori-ai-agents-runner-pr-footer -->"

    rendered = _append_pr_attribution_footer(body, agent_cli="codex", agent_cli_args="")

    assert rendered == body + "\n"


def test_append_pr_attribution_footer_handles_empty_body() -> None:
    rendered = _append_pr_attribution_footer("", agent_cli="", agent_cli_args="")

    assert rendered.startswith("---\n<!-- midori-ai-agents-runner-pr-footer -->")
    assert "Agent Used: (unknown)" in rendered
