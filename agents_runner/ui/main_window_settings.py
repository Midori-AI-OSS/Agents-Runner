from __future__ import annotations

import logging
import os
import shlex

from PySide6.QtWidgets import QMessageBox

from agents_runner.agent_cli import container_config_dir
from agents_runner.agent_cli import normalize_agent
from agents_runner.agent_cli import verify_cli_clause
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

        host_codex_dir = os.path.expanduser(str(merged.get("host_codex_dir") or "").strip())
        if not host_codex_dir:
            host_codex_dir = os.path.expanduser("~/.codex")
        merged["host_codex_dir"] = host_codex_dir

        merged["host_claude_dir"] = os.path.expanduser(str(merged.get("host_claude_dir") or "").strip())
        merged["host_copilot_dir"] = os.path.expanduser(str(merged.get("host_copilot_dir") or "").strip())

        merged["preflight_enabled"] = bool(merged.get("preflight_enabled") or False)
        merged["preflight_script"] = str(merged.get("preflight_script") or "")
        merged["interactive_command"] = str(merged.get("interactive_command") or "--sandbox danger-full-access")
        merged["interactive_command_claude"] = str(merged.get("interactive_command_claude") or "")
        merged["interactive_command_copilot"] = str(merged.get("interactive_command_copilot") or "")
        for key in ("interactive_command", "interactive_command_claude", "interactive_command_copilot"):
            merged[key] = self._sanitize_interactive_command_value(key, merged.get(key))
        merged["append_pixelarch_context"] = bool(merged.get("append_pixelarch_context") or False)

        try:
            merged["max_agents_running"] = int(str(merged.get("max_agents_running", -1)).strip())
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
        return "interactive_command"


    def _host_config_dir_key(self, agent_cli: str) -> str:
        agent_cli = normalize_agent(agent_cli)
        if agent_cli == "claude":
            return "host_claude_dir"
        if agent_cli == "copilot":
            return "host_copilot_dir"
        return "host_codex_dir"


    def _default_interactive_command(self, agent_cli: str) -> str:
        agent_cli = normalize_agent(agent_cli)
        if agent_cli == "claude":
            return "--add-dir /home/midori-ai/workspace"
        if agent_cli == "copilot":
            return "--add-dir /home/midori-ai/workspace"
        return "--sandbox danger-full-access"


    def _sanitize_interactive_command_value(self, key: str, raw: object) -> str:
        value = str(raw or "").strip()
        if not value:
            return ""

        try:
            cmd_parts = shlex.split(value)
        except ValueError:
            cmd_parts = []
        if cmd_parts and cmd_parts[0] in {"codex", "claude", "copilot"}:
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
        """Resolve config directory for a given agent.

        This helper method encapsulates the common logic for determining the
        config directory for an agent, following this precedence:

        1. Environment-specific agent_selection.agent_config_dirs (normalized keys)
        2. Global per-agent settings (host_claude_dir, host_copilot_dir, host_codex_dir)
        3. Legacy env.host_codex_dir override (deprecated, backwards compatibility)

        Args:
            agent_cli: The normalized agent name (e.g., "codex", "claude", "copilot")
            env: Optional environment with potential overrides
            settings: The settings dictionary containing global agent config

        Returns:
            The resolved config directory path (with ~ expanded)
        """
        # Check environment agent_selection for per-agent config directory
        if env and env.agent_selection and env.agent_selection.agent_config_dirs:
            # Normalize keys to handle case sensitivity issues
            normalized_dirs = {
                normalize_agent(str(name)): path
                for name, path in env.agent_selection.agent_config_dirs.items()
            }
            if agent_cli in normalized_dirs:
                return os.path.expanduser(str(normalized_dirs[agent_cli] or "").strip())

        # Fall back to global settings-based config dir
        config_dir = ""
        if agent_cli == "claude":
            config_dir = str(settings.get("host_claude_dir") or "")
        elif agent_cli == "copilot":
            config_dir = str(settings.get("host_copilot_dir") or "")
        else:
            config_dir = str(
                settings.get("host_codex_dir")
                or os.environ.get("CODEX_HOST_CODEX_DIR", os.path.expanduser("~/.codex"))
            )

        # Legacy: check env.host_codex_dir override (deprecated)
        if env and env.host_codex_dir:
            config_dir = env.host_codex_dir

        return os.path.expanduser(str(config_dir or "").strip())

    def _effective_agent_and_config(
        self,
        *,
        env: Environment | None,
        settings: dict[str, object] | None = None,
    ) -> tuple[str, str]:
        """Return the effective ``(agent_cli, config_dir)`` for a launch.

        Agent and config directory selection follows this precedence:

        1. Environment ``agent_selection`` override

           * If ``env`` is provided and ``env.agent_selection.enabled_agents`` is
             non-empty, the first enabled agent is used as ``agent_cli``.
           * If that agent has an explicit config directory in
             ``env.agent_selection.agent_config_dirs[agent_cli]`` (with normalized
             keys), that path is used.

        2. Global UI settings

           * If no environment-specific agent is found, the agent is taken from
             ``settings["use"]`` (defaulting to ``"codex"``) and normalized via
             :func:`normalize_agent`.
           * The config directory is then derived from the corresponding
             ``host_*_dir`` entry:

               - ``"claude"``  -> ``settings["host_claude_dir"]``
               - ``"copilot"`` -> ``settings["host_copilot_dir"]``
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
        agent_cli = normalize_agent(str(settings.get("use") or "codex"))

        # Check if environment has agent_selection override
        if env and env.agent_selection and env.agent_selection.enabled_agents:
            # Use first enabled agent from environment
            original_agent = env.agent_selection.enabled_agents[0]
            agent_cli = normalize_agent(original_agent)
            
            # Log warning if agent was invalid and got normalized
            if agent_cli != original_agent.lower():
                logger.warning(
                    f"Environment agent_selection specified invalid agent '{original_agent}', "
                    f"using '{agent_cli}' instead. Valid agents: codex, claude, copilot"
                )

        # Use helper method to resolve config directory
        config_dir = self._resolve_config_dir_for_agent(
            agent_cli=agent_cli,
            env=env,
            settings=settings,
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

        1. If an ``env`` is provided and it has an ``agent_selection`` entry with a
           config directory for this (normalized) ``agent_cli``, that directory is used.
           Keys in ``agent_config_dirs`` are normalized to handle case sensitivity.
        2. Otherwise, per-agent settings are consulted:

           * ``host_claude_dir`` when ``agent_cli == "claude"``
           * ``host_copilot_dir`` when ``agent_cli == "copilot"``
           * ``host_codex_dir`` for all other agents; if unset, falls back to the
             ``CODEX_HOST_CODEX_DIR`` environment variable, then to ``~/.codex``.
        3. Finally, for legacy/backwards compatibility, if ``env`` defines
           ``host_codex_dir``, that value overrides whichever directory was selected
           earlier (even for non-codex agents).

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
        if agent_cli in {"claude", "copilot"} and not host_config_dir:
            agent_label = "Claude" if agent_cli == "claude" else "Copilot"
            QMessageBox.warning(
                self,
                "Missing config folder",
                f"Set the {agent_label} Config folder in Settings (or override it per-environment).",
            )
            return False
        if not host_config_dir:
            return False
        if os.path.exists(host_config_dir) and not os.path.isdir(host_config_dir):
            QMessageBox.warning(self, "Invalid config folder", "Config folder path is not a directory.")
            return False
        try:
            os.makedirs(host_config_dir, exist_ok=True)
        except Exception as exc:
            QMessageBox.warning(self, "Invalid config folder", str(exc))
            return False
        return True
