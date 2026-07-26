from __future__ import annotations

from agents_runner.environments import Environment
from agents_runner.environments.model import AGENTSNOVA_AUTO_MODE_DISABLED
from agents_runner.environments.model import AGENTSNOVA_AUTO_MODE_ENABLED
from agents_runner.environments.model import AGENTSNOVA_MARKER_COMMENT_MODE_DISABLED
from agents_runner.environments.model import AGENTSNOVA_MARKER_COMMENT_MODE_INHERIT
from agents_runner.environments.model import AGENTSNOVA_MARKER_COMMENT_MODE_KEEP
from agents_runner.environments.model import normalize_agentsnova_auto_mode
from agents_runner.environments.model import normalize_agentsnova_marker_comment_mode


def normalize_default_marker_comment_mode(value: object) -> str:
    """Normalize the app-wide default marker-comment mode."""
    if isinstance(value, bool):
        return AGENTSNOVA_MARKER_COMMENT_MODE_KEEP if value else AGENTSNOVA_MARKER_COMMENT_MODE_DISABLED

    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes", "on"}:
        return AGENTSNOVA_MARKER_COMMENT_MODE_KEEP
    if text in {"false", "0", "no", "off"}:
        return AGENTSNOVA_MARKER_COMMENT_MODE_DISABLED

    normalized = normalize_agentsnova_marker_comment_mode(text)
    if normalized == AGENTSNOVA_MARKER_COMMENT_MODE_INHERIT:
        return AGENTSNOVA_MARKER_COMMENT_MODE_KEEP
    return normalized


def _resolve_effective_auto_mode(
    *,
    settings: dict[str, object],
    default_key: str,
    env_value: object,
) -> bool:
    default_enabled = bool(settings.get(default_key, True))
    mode = normalize_agentsnova_auto_mode(str(env_value or "inherit"))
    if mode == AGENTSNOVA_AUTO_MODE_ENABLED:
        return True
    if mode == AGENTSNOVA_AUTO_MODE_DISABLED:
        return False
    return default_enabled


def resolve_effective_auto_review_enabled(*, settings: dict[str, object], env: Environment | None) -> bool:
    return _resolve_effective_auto_mode(
        settings=settings,
        default_key="agentsnova_auto_review_enabled",
        env_value=getattr(env, "agentsnova_auto_review_mode", "inherit"),
    )


def resolve_effective_auto_reactions_enabled(*, settings: dict[str, object], env: Environment | None) -> bool:
    return _resolve_effective_auto_mode(
        settings=settings,
        default_key="agentsnova_auto_reactions_enabled",
        env_value=getattr(env, "agentsnova_auto_reactions_mode", "inherit"),
    )


def resolve_effective_marker_comment_mode(*, settings: dict[str, object], env: Environment | None) -> str:
    default_mode = normalize_default_marker_comment_mode(
        settings.get(
            "agentsnova_auto_marker_comments_mode",
            settings.get("agentsnova_auto_marker_comments_enabled", True),
        )
    )
    mode = normalize_agentsnova_marker_comment_mode(
        str(getattr(env, "agentsnova_marker_comment_mode", "inherit") or "inherit")
    )
    if mode == AGENTSNOVA_MARKER_COMMENT_MODE_INHERIT:
        return default_mode
    return mode
