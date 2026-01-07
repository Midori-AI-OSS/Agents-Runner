from __future__ import annotations

import logging
import os
import shlex

from PySide6.QtWidgets import QMessageBox

from agents_runner.agent_cli import normalize_agent
from agents_runner.ui.utils import _looks_like_agent_help_command
from agents_runner.environments import Environment

logger = logging.getLogger(__name__)


class _MainWindowSettingsMixin:
    def _apply_settings_to_pages(self) -> None:
        self._settings.set_settings(self._settings_data)
        self._apply_active_environment_to_new_task()

    def _apply_settings(self, settings: dict) -> None:
        merged = dict(self._settings_data)
        merged.update(settings or {})
        merged["use"] = normalize_agent(str(merged.get("use") or "codex"))

        shell_value = str(merged.get("shell") or "bash").lower()
        if shell_value not in {"bash", "sh", "zsh", "fish", "tmux"}:
            shell_value = "bash"
        merged["shell"] = shell_value

        host_codex_dir = os.path.expanduser(
            str(merged.get("host_codex_dir") or "").strip()
        )
        if not host_codex_dir:
            host_codex_dir = os.path.expanduser("~/.codex")
        merged["host_codex_dir"] = host_codex_dir

        host_claude_dir = os.path.expanduser(
            str(merged.get("host_claude_dir") or "").strip()
        )
        if not host_claude_dir:
            host_claude_dir = os.path.expanduser("~/.claude")
        merged["host_claude_dir"] = host_claude_dir

        host_copilot_dir = os.path.expanduser(
            str(merged.get("host_copilot_dir") or "").strip()
        )
        if not host_copilot_dir:
            host_copilot_dir = os.path.expanduser("~/.copilot")
        merged["host_copilot_dir"] = host_copilot_dir

        host_gemini_dir = os.path.expanduser(
            str(merged.get("host_gemini_dir") or "").strip()
        )
        if not host_gemini_dir:
            host_gemini_dir = os.path.expanduser("~/.gemini")
        merged["host_gemini_dir"] = host_gemini_dir

        merged["preflight_enabled"] = bool(merged.get("preflight_enabled") or False)
        merged["preflight_script"] = str(merged.get("preflight_script") or "")
        merged["interactive_command"] = str(
            merged.get("interactive_command") or "--sandbox danger-full-access"
        )
        merged["interactive_command_claude"] = str(
            merged.get("interactive_command_claude") or ""
        )
        merged["interactive_command_copilot"] = str(
            merged.get("interactive_command_copilot") or ""
        )
        merged["interactive_command_gemini"] = str(
            merged.get("interactive_command_gemini") or ""
        )
        for key in (
            "interactive_command",
            "interactive_command_claude",
            "interactive_command_copilot",
            "interactive_command_gemini",
        ):
            merged[key] = self._sanitize_interactive_command_value(key, merged.get(key))
        merged["append_pixelarch_context"] = bool(
            merged.get("append_pixelarch_context") or False
        )
        merged["headless_desktop_enabled"] = bool(
            merged.get("headless_desktop_enabled") or False
        )

        try:
            merged["max_agents_running"] = int(
                str(merged.get("max_agents_running", -1)).strip()
            )
        except Exception:
            merged["max_agents_running"] = -1
        self._settings_data = merged
        self._apply_settings_to_pages()
        self._schedule_save()

    def _interactive_command_key(self, agent_cli: str) -> str:
        agent_cli = normalize_agent(agent_cli)
        if agent_cli == "claude":
            return "interactive_command_claude"
        if agent_cli == "copilot":
            return "interactive_command_copilot"
        if agent_cli == "gemini":
            return "interactive_command_gemini"
        return "interactive_command"

    def _host_config_dir_key(self, agent_cli: str) -> str:
        agent_cli = normalize_agent(agent_cli)
        if agent_cli == "claude":
            return "host_claude_dir"
        if agent_cli == "copilot":
            return "host_copilot_dir"
        if agent_cli == "gemini":
            return "host_gemini_dir"
        return "host_codex_dir"

    def _default_interactive_command(self, agent_cli: str) -> str:
        agent_cli = normalize_agent(agent_cli)
        if agent_cli == "claude":
            return "--add-dir /home/midori-ai/workspace"
        if agent_cli == "copilot":
            return "--add-dir /home/midori-ai/workspace"
        if agent_cli == "gemini":
            return "--no-sandbox --approval-mode yolo --include-directories /home/midori-ai/workspace"
        return "--sandbox danger-full-access"

    def _sanitize_interactive_command_value(self, key: str, raw: object) -> str:
        value = str(raw or "").strip()
        if not value:
            return ""

        try:
            cmd_parts = shlex.split(value)
        except ValueError:
            cmd_parts = []
        if cmd_parts and cmd_parts[0] in {"codex", "claude", "copilot", "gemini"}:
            head = cmd_parts.pop(0)
            if head == "codex" and cmd_parts and cmd_parts[0] == "exec":
                cmd_parts.pop(0)
            value = " ".join(shlex.quote(part) for part in cmd_parts)

        if _looks_like_agent_help_command(value):
            agent_cli = "codex"
            if str(key or "").endswith("_claude"):
                agent_cli = "claude"
            elif str(key or "").endswith("_copilot"):
                agent_cli = "copilot"
            elif str(key or "").endswith("_gemini"):
                agent_cli = "gemini"
            return self._default_interactive_command(agent_cli)

        return value

    @staticmethod
    def _is_agent_help_interactive_launch(prompt: str, command: str) -> bool:
        prompt = str(prompt or "").strip().lower()
        if prompt.startswith("get agent help"):
            return True
        return _looks_like_agent_help_command(command)

    def _resolve_config_dir_for_agent(
        self,
        *,
        agent_cli: str,
        env: Environment | None,
        settings: dict[str, object],
    ) -> str:
        """Resolve a host config directory for an agent CLI.

        Precedence:
        1. Environment agent_selection (first matching agent instance with config_dir)
        2. Global per-agent settings (host_*_dir)
        3. Legacy env.host_codex_dir override (deprecated)
        """
        agent_cli = normalize_agent(agent_cli)

        if env and env.agent_selection and getattr(env.agent_selection, "agents", None):
            for inst in env.agent_selection.agents or []:
                if normalize_agent(getattr(inst, "agent_cli", "")) != agent_cli:
                    continue
                inst_dir = os.path.expanduser(
                    str(getattr(inst, "config_dir", "") or "").strip()
                )
                if inst_dir:
                    return inst_dir

        # Fall back to global settings-based config dir
        config_dir = ""
        if agent_cli == "claude":
            config_dir = str(settings.get("host_claude_dir") or "")
        elif agent_cli == "copilot":
            config_dir = str(settings.get("host_copilot_dir") or "")
        elif agent_cli == "gemini":
            config_dir = str(settings.get("host_gemini_dir") or "")
        else:
            config_dir = str(
                settings.get("host_codex_dir")
                or os.environ.get(
                    "CODEX_HOST_CODEX_DIR", os.path.expanduser("~/.codex")
                )
            )

        # Legacy: check env.host_codex_dir override (deprecated) — only apply for codex
        if agent_cli == "codex" and env and env.host_codex_dir:
            config_dir = env.host_codex_dir

        return os.path.expanduser(str(config_dir or "").strip())

    def _select_agent_instance_for_env(
        self,
        *,
        env: Environment,
        settings: dict[str, object],
        advance_round_robin: bool,
    ) -> tuple[str, str, str]:
        agents = list(getattr(env.agent_selection, "agents", []) or [])
        if not agents:
            agent_cli = normalize_agent(str(settings.get("use") or "codex"))
            config_dir = self._resolve_config_dir_for_agent(
                agent_cli=agent_cli, env=env, settings=settings
            )
            return agent_cli, config_dir, ""

        mode = (
            str(getattr(env.agent_selection, "selection_mode", "") or "round-robin")
            .strip()
            .lower()
        )
        env_id = str(getattr(env, "env_id", "") or "")

        if not hasattr(self, "_agent_selection_round_robin_cursor"):
            self._agent_selection_round_robin_cursor = {}

        chosen = agents[0]
        if mode == "round-robin":
            cursor = int(
                getattr(self, "_agent_selection_round_robin_cursor", {}).get(env_id, 0)
            )
            idx = cursor % len(agents)
            chosen = agents[idx]
            if advance_round_robin:
                getattr(self, "_agent_selection_round_robin_cursor", {})[env_id] = (
                    idx + 1
                )
        elif mode == "least-used":
            counts: dict[str, int] = {}
            tasks = getattr(self, "_tasks", {}) or {}
            for task in tasks.values():
                if getattr(task, "environment_id", "") != env_id:
                    continue
                if not getattr(task, "is_active", lambda: False)():
                    continue
                agent_instance_id = str(
                    getattr(task, "agent_instance_id", "") or ""
                ).strip()
                if not agent_instance_id:
                    continue
                counts[agent_instance_id] = counts.get(agent_instance_id, 0) + 1

            def _score(inst: object) -> tuple[int, int]:
                inst_id = str(getattr(inst, "agent_id", "") or "").strip()
                return counts.get(inst_id, 0), agents.index(inst)

            chosen = min(agents, key=_score)

        agent_cli = normalize_agent(str(getattr(chosen, "agent_cli", "") or "codex"))
        agent_id = str(getattr(chosen, "agent_id", "") or "").strip()

        config_dir = os.path.expanduser(
            str(getattr(chosen, "config_dir", "") or "").strip()
        )
        if not config_dir:
            config_dir = self._resolve_config_dir_for_agent(
                agent_cli=agent_cli, env=env, settings=settings
            )
        # Legacy: env.host_codex_dir was historically used as a global config-dir
        # override. Preserve backwards compatibility for Codex only; other agents
        # have their own per-agent settings (e.g. host_copilot_dir).
        if agent_cli == "codex" and env and env.host_codex_dir:
            config_dir = os.path.expanduser(str(env.host_codex_dir or "").strip())

        return agent_cli, config_dir, agent_id

    def _effective_agent_and_config(
        self,
        *,
        env: Environment | None,
        settings: dict[str, object] | None = None,
        advance_round_robin: bool = False,
    ) -> tuple[str, str]:
        """Return the effective ``(agent_cli, config_dir)`` for a launch.

        Agent and config directory selection follows this precedence:

        1. Environment ``agent_selection`` override

           * If ``env`` is provided and ``env.agent_selection.agents`` is non-empty,
             an agent instance is selected based on ``selection_mode``.
           * If the selected instance has an explicit ``config_dir``, that path is
             used; otherwise it falls back to global settings.

        2. Global UI settings

           * If no environment-specific agent is found, the agent is taken from
            ``settings["use"]`` (defaulting to ``"codex"``) and normalized via
             :func:`normalize_agent`.
           * The config directory is then derived from the corresponding
             ``host_*_dir`` entry:

               - ``"claude"``  -> ``settings["host_claude_dir"]``
               - ``"copilot"`` -> ``settings["host_copilot_dir"]``
               - ``"gemini"``  -> ``settings["host_gemini_dir"]``
               - ``"codex"``   -> ``settings["host_codex_dir"]`` or, if unset,
                 ``$CODEX_HOST_CODEX_DIR`` or ``~/.codex``.

        3. Legacy ``Environment.host_codex_dir`` override

           * If ``env`` is provided and ``env.host_codex_dir`` is set, its value
             (after :func:`os.path.expanduser`) overrides the config directory
             computed from global settings. This field is deprecated and kept
             only for backwards compatibility.

        The returned ``config_dir`` is always a string with ``~`` expanded via
        :func:`os.path.expanduser`.

        Args:
            env: Optional environment with potential agent overrides
            settings: Optional settings dict; uses ``self._settings_data`` if None

        Returns:
            A tuple of (agent_cli, config_dir) where agent_cli is normalized
        """
        settings = settings or self._settings_data
        if env and env.agent_selection and getattr(env.agent_selection, "agents", None):
            agent_cli, config_dir, _agent_id = self._select_agent_instance_for_env(
                env=env,
                settings=settings,
                advance_round_robin=advance_round_robin,
            )
            return agent_cli, config_dir

        agent_cli = normalize_agent(str(settings.get("use") or "codex"))
        config_dir = self._resolve_config_dir_for_agent(
            agent_cli=agent_cli, env=env, settings=settings
        )
        return agent_cli, config_dir

    def _effective_host_config_dir(
        self,
        *,
        agent_cli: str,
        env: Environment | None,
        settings: dict[str, object] | None = None,
    ) -> str:
        """Return the effective host config directory for the given agent CLI.

        The directory is resolved using the following precedence order:

        1. If an ``env`` is provided and it has an ``agent_selection`` entry with an
           agent instance matching this (normalized) ``agent_cli`` and a non-empty
           ``config_dir``, that directory is used.
        2. Otherwise, per-agent settings are consulted:

           * ``host_claude_dir`` when ``agent_cli == "claude"``
           * ``host_copilot_dir`` when ``agent_cli == "copilot"``
           * ``host_gemini_dir`` when ``agent_cli == "gemini"``
           * ``host_codex_dir`` for all other agents; if unset, falls back to the
             ``CODEX_HOST_CODEX_DIR`` environment variable, then to ``~/.codex``.
        3. Finally, for legacy/backwards compatibility, if ``env`` defines
           ``host_codex_dir`` and ``agent_cli == "codex"``, that value overrides
           whichever directory was selected earlier.

        The returned path is normalized with :func:`os.path.expanduser`.

        Args:
            agent_cli: The agent CLI name (will be normalized)
            env: Optional environment with potential overrides
            settings: Optional settings dict; uses ``self._settings_data`` if None

        Returns:
            The resolved config directory path (with ~ expanded)
        """
        agent_cli = normalize_agent(agent_cli)
        settings = settings or self._settings_data

        # Use helper method to resolve config directory
        return self._resolve_config_dir_for_agent(
            agent_cli=agent_cli,
            env=env,
            settings=settings,
        )

    def _ensure_agent_config_dir(self, agent_cli: str, host_config_dir: str) -> bool:
        agent_cli = normalize_agent(agent_cli)
        host_config_dir = os.path.expanduser(str(host_config_dir or "").strip())
        if agent_cli in {"claude", "copilot", "gemini"} and not host_config_dir:
            agent_label = (
                "Claude"
                if agent_cli == "claude"
                else ("Copilot" if agent_cli == "copilot" else "Gemini")
            )
            QMessageBox.warning(
                self,
                "Missing config folder",
                f"Set the {agent_label} Config folder in Settings (or override it per-environment).",
            )
            return False
        if not host_config_dir:
            return False
        if os.path.exists(host_config_dir) and not os.path.isdir(host_config_dir):
            QMessageBox.warning(
                self, "Invalid config folder", "Config folder path is not a directory."
            )
            return False
        try:
            os.makedirs(host_config_dir, exist_ok=True)
        except Exception as exc:
            QMessageBox.warning(self, "Invalid config folder", str(exc))
            return False
        return True

    def _get_next_agent_info(self, *, env: Environment | None) -> tuple[str, str]:
        """Return (current, next) labels for Run button tooltips."""
        agent_cli, _ = self._effective_agent_and_config(env=env)

        if (
            not env
            or not env.agent_selection
            or not getattr(env.agent_selection, "agents", None)
        ):
            return agent_cli, ""

        agents = list(env.agent_selection.agents or [])
        if len(agents) <= 1:
            inst = agents[0] if agents else None
            if inst is None:
                return agent_cli, ""
            return self._format_agent_label(inst), ""

        mode = (
            str(getattr(env.agent_selection, "selection_mode", "") or "round-robin")
            .strip()
            .lower()
        )
        env_id = str(getattr(env, "env_id", "") or "")
        cursor_map = (
            getattr(self, "_agent_selection_round_robin_cursor", {})
            if hasattr(self, "_agent_selection_round_robin_cursor")
            else {}
        )
        cursor = int(cursor_map.get(env_id, 0))
        current_idx = 0 if mode != "round-robin" else (cursor % len(agents))
        current = agents[current_idx]

        if mode == "fallback":
            fallbacks = dict(getattr(env.agent_selection, "agent_fallbacks", {}) or {})
            wanted_id = str(
                fallbacks.get(str(getattr(current, "agent_id", "") or "").strip(), "")
                or ""
            ).strip()
            next_inst = next(
                (
                    a
                    for a in agents
                    if str(getattr(a, "agent_id", "") or "").strip() == wanted_id
                ),
                None,
            )
            next_label = self._format_agent_label(next_inst) if next_inst else ""
            if next_label:
                next_label = f"Fallback: {next_label}"
            return self._format_agent_label(current), next_label

        if mode == "least-used":
            tasks = getattr(self, "_tasks", {}) or {}
            counts: dict[str, int] = {}
            for task in tasks.values():
                if getattr(task, "environment_id", "") != env_id:
                    continue
                if not getattr(task, "is_active", lambda: False)():
                    continue
                inst_id = str(getattr(task, "agent_instance_id", "") or "").strip()
                if inst_id:
                    counts[inst_id] = counts.get(inst_id, 0) + 1
            ordered = sorted(
                agents,
                key=lambda a: (
                    counts.get(str(getattr(a, "agent_id", "") or "").strip(), 0),
                    agents.index(a),
                ),
            )
            now = ordered[0] if ordered else current
            nxt = ordered[1] if len(ordered) > 1 else None
            return self._format_agent_label(now), (
                self._format_agent_label(nxt) if nxt else ""
            )

        # round-robin (default)
        next_idx = (current_idx + 1) % len(agents)
        return self._format_agent_label(current), self._format_agent_label(
            agents[next_idx]
        )

    @staticmethod
    def _format_agent_label(inst: object | None) -> str:
        if inst is None:
            return ""
        agent_cli = normalize_agent(str(getattr(inst, "agent_cli", "") or "codex"))
        agent_id = str(getattr(inst, "agent_id", "") or "").strip()
        if agent_id and agent_id != agent_cli:
            return f"{agent_cli} ({agent_id})"
        return agent_cli
