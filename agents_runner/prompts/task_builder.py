from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetryContext:
    attempt_number: int
    total_configured_attempts: int | None
    previous_agent: str
    previous_config: str
    previous_failure_category: str
    previous_failure_summary: str


def build_task_prompt(base_prompt: str, *, retry_context: RetryContext | None) -> str:
    prompt = str(base_prompt or "").strip()
    if retry_context is None or int(retry_context.attempt_number) <= 1:
        return prompt

    total = (
        int(retry_context.total_configured_attempts)
        if retry_context.total_configured_attempts is not None
        else None
    )
    attempt_line = (
        f"attempt {retry_context.attempt_number} of {total}"
        if total and total > 0
        else f"attempt {retry_context.attempt_number}"
    )

    preamble = "\n".join(
        [
            "RETRY CONTEXT",
            f"This is a retry attempt ({attempt_line}).",
            f"Previous attempt: agent={retry_context.previous_agent} config={retry_context.previous_config}.",
            "Previous failure: "
            f"category={retry_context.previous_failure_category}; summary={retry_context.previous_failure_summary}.",
            "",
            "Warning: The workspace may already contain partial progress from a previous attempt.",
            "",
            "Retry instructions (must follow):",
            "1) Inspect the workspace for existing changes before doing new work.",
            "2) Continue from existing progress if it exists.",
            "3) Avoid redoing completed steps.",
            "4) Avoid deleting work or resetting the workspace unless the task explicitly asks for it.",
            "",
        ]
    )

    if not prompt:
        return preamble.rstrip()
    return f"{preamble}{prompt}"
