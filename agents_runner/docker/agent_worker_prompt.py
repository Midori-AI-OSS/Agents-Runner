"""Prompt assembly logic for agent worker.

Handles desktop context injection and template prompt assembly
including Midori AI template detection and cross-agent support.
"""

from typing import Any, Callable

from agents_runner.prompt_sanitizer import sanitize_prompt
from agents_runner.agent_cli import normalize_agent
from agents_runner.environments import load_environments
from agents_runner.prompts import load_prompt
from agents_runner.prompts.sections import insert_prompt_sections_before_user_prompt
from agents_runner.log_format import format_log
from agents_runner.midoriai_template import MidoriAITemplateDetection


class PromptAssembler:
    """Assembles prompts with desktop and template context."""

    def __init__(
        self,
        base_prompt: str,
        environment_id: str | None,
        on_log: Callable[[str], None],
    ):
        self._base_prompt = base_prompt
        self._environment_id = environment_id
        self._on_log = on_log

    def assemble_prompt(
        self,
        agent_cli: str,
        template_detection: MidoriAITemplateDetection,
        desktop_enabled: bool,
        desktop_display: str,
    ) -> str:
        """Assemble final prompt with desktop context and templates."""
        prompt_for_agent = self._base_prompt

        if template_detection.midoriai_template_detected:
            template_parts = self._load_template_parts(agent_cli)
            if template_parts:
                combined_template = "\n\n".join(template_parts)
                prompt_for_agent = insert_prompt_sections_before_user_prompt(
                    prompt_for_agent,
                    [combined_template],
                )
                self._on_log(
                    format_log("env", "template", "INFO", "injected template prompts")
                )

        if desktop_enabled:
            prompt_for_agent = insert_prompt_sections_before_user_prompt(
                prompt_for_agent,
                [self._headless_desktop_prompt_instructions(display=desktop_display)],
            )
            self._on_log(
                format_log(
                    "desktop",
                    "setup",
                    "INFO",
                    "added desktop context to prompt (non-interactive)",
                )
            )

        return sanitize_prompt(prompt_for_agent)

    def _load_template_parts(self, agent_cli: str) -> list[str]:
        """Load all template parts."""
        template_parts: list[str] = []

        for template_name in [
            "templates/midoriaibasetemplate",
            "templates/subagentstemplate",
        ]:
            try:
                prompt = load_prompt(template_name).strip()
                if prompt:
                    template_parts.append(prompt)
            except Exception as exc:
                self._on_log(
                    format_log(
                        "env",
                        "template",
                        "WARN",
                        f"failed to load {template_name}: {exc}",
                    )
                )

        cross_agents_enabled, env = self._check_cross_agents_enabled()
        if cross_agents_enabled:
            try:
                cross_prompt = load_prompt("templates/crossagentstemplate").strip()
                if cross_prompt:
                    template_parts.append(cross_prompt)
            except Exception as exc:
                self._on_log(
                    format_log(
                        "env",
                        "template",
                        "WARN",
                        f"failed to load templates/crossagentstemplate: {exc}",
                    )
                )

            if env is not None:
                allowlist_templates = self._load_allowlist_cli_templates(env, agent_cli)
                template_parts.extend(allowlist_templates)

        try:
            cli_prompt = load_prompt(f"templates/agentcli/{agent_cli}").strip()
            if cli_prompt:
                template_parts.append(cli_prompt)
        except Exception as exc:
            self._on_log(
                format_log(
                    "env",
                    "template",
                    "WARN",
                    f"failed to load templates/agentcli/{agent_cli}: {exc}",
                )
            )

        return template_parts

    def _check_cross_agents_enabled(self) -> tuple[bool, Any]:
        """Check if cross-agents feature is enabled."""
        if not self._environment_id:
            return (False, None)

        try:
            environments = load_environments()
            env = environments.get(str(self._environment_id))
            if env is not None:
                cross_agents_enabled = bool(
                    env.use_cross_agents is True
                    and env.cross_agent_allowlist
                    and len(env.cross_agent_allowlist) > 0
                )
                return (cross_agents_enabled, env)
        except Exception as exc:
            self._on_log(
                format_log(
                    "env",
                    "template",
                    "WARN",
                    f"failed to check cross-agents config: {exc}",
                )
            )

        return (False, None)

    def _load_allowlist_cli_templates(self, env: Any, agent_cli: str) -> list[str]:
        """Load CLI templates for agents in cross-agent allowlist."""
        if not env.agent_selection or not env.agent_selection.agents:
            return []

        agent_cli_by_id: dict[str, str] = {
            agent.agent_id: agent.agent_cli for agent in env.agent_selection.agents
        }

        loaded_allowlist_clis: set[str] = set()
        allowlist_templates: list[str] = []

        for agent_id in env.cross_agent_allowlist:
            allowlist_agent_cli = agent_cli_by_id.get(agent_id)
            if not allowlist_agent_cli:
                continue

            normalized_cli = normalize_agent(allowlist_agent_cli)
            if normalized_cli == agent_cli:
                continue
            if normalized_cli in loaded_allowlist_clis:
                continue

            try:
                allowlist_cli_prompt = load_prompt(
                    f"templates/agentcli/{normalized_cli}"
                ).strip()
                if allowlist_cli_prompt:
                    allowlist_templates.append(allowlist_cli_prompt)
                    loaded_allowlist_clis.add(normalized_cli)
            except Exception as exc:
                self._on_log(
                    format_log(
                        "env",
                        "template",
                        "WARN",
                        f"failed to load templates/agentcli/{normalized_cli} for allowlist: {exc}",
                    )
                )

        if loaded_allowlist_clis:
            self._on_log(
                format_log(
                    "env",
                    "template",
                    "INFO",
                    f"cross-agent CLI context: {', '.join(sorted(loaded_allowlist_clis))}",
                )
            )

        return allowlist_templates

    def _headless_desktop_prompt_instructions(self, *, display: str) -> str:
        """Generate prompt instructions for headless desktop usage."""
        display = str(display or "").strip() or ":1"
        return load_prompt(
            "headless_desktop",
            DISPLAY=display,
        )
