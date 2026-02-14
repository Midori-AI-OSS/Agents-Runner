"""Shared cache resolution logic for interactive and agent runtime setup.

Provides centralized cache-image resolution to avoid duplication across
interactive_prep_worker, main_window_tasks_interactive_docker, and agent_worker_setup.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from agents_runner.docker.image_builder import ensure_desktop_image
from agents_runner.docker.phase_image_builder import PREFLIGHTS_DIR, ensure_phase_image
from agents_runner.log_format import format_log

# Process-wide lock to serialize cache-image builds across threads
_cache_build_lock = threading.Lock()


@dataclass
class CacheResolutionResult:
    """Result of cache resolution containing runtime image and cache flags."""

    runtime_image: str
    system_preflight_cached: bool
    desktop_preflight_cached: bool
    settings_preflight_cached: bool
    environment_preflight_cached: bool
    desktop_preflight_script: str


def resolve_runtime_cache(
    base_image: str,
    cache_system_enabled: bool,
    cache_settings_enabled: bool,
    desktop_cache_enabled: bool,
    extra_preflight_script: str,
    settings_preflight_script: str,
    preflights_host_dir: Path | None = None,
    on_log: Callable[[str], None] | None = None,
    check_stop: Callable[[], None] | None = None,
) -> CacheResolutionResult:
    """Resolve runtime image with cache layers applied.

    Args:
        base_image: Starting Docker image
        cache_system_enabled: Whether to cache system preflight
        cache_settings_enabled: Whether to cache settings preflight
        desktop_cache_enabled: Whether to cache desktop build
        extra_preflight_script: Extra preflight script (desktop detection)
        settings_preflight_script: Settings preflight script content
        preflights_host_dir: Directory containing preflight scripts (defaults to PREFLIGHTS_DIR)
        on_log: Optional log callback
        check_stop: Optional stop-check callback (for cancellation)

    Returns:
        CacheResolutionResult with resolved runtime image and cache flags
    """
    if preflights_host_dir is None:
        preflights_host_dir = PREFLIGHTS_DIR.resolve()
    else:
        preflights_host_dir = preflights_host_dir.resolve()

    runtime_image = base_image
    desktop_preflight_script = str(extra_preflight_script or "")
    system_preflight_cached = False
    desktop_preflight_cached = False
    settings_preflight_cached = False
    environment_preflight_cached = False

    def noop_log(line: str) -> None:
        pass

    def noop_check() -> None:
        pass

    log_fn = on_log or noop_log
    check_fn = check_stop or noop_check

    # System preflight cache layer
    system_preflight_script = ""
    system_preflight_path = preflights_host_dir / "pixelarch_yay.sh"
    if system_preflight_path.is_file():
        try:
            system_preflight_script = system_preflight_path.read_text(encoding="utf-8")
        except Exception:
            system_preflight_script = ""

    if cache_system_enabled and system_preflight_script.strip():
        check_fn()
        with _cache_build_lock:
            next_image = ensure_phase_image(
                base_image=runtime_image,
                phase_name="system",
                script_content=system_preflight_script,
                preflights_dir=preflights_host_dir,
                on_log=log_fn,
            )
        system_preflight_cached = next_image != runtime_image
        runtime_image = next_image
    elif cache_system_enabled:
        log_fn(
            format_log(
                "phase",
                "cache",
                "WARN",
                "system caching enabled but system script is unavailable",
            )
        )

    # Desktop cache layer
    if desktop_cache_enabled:
        check_fn()
        desktop_base_image = runtime_image
        with _cache_build_lock:
            next_image = ensure_desktop_image(desktop_base_image, on_log=log_fn)
        desktop_preflight_cached = next_image != desktop_base_image
        runtime_image = next_image
        if desktop_preflight_cached:
            desktop_run_path = preflights_host_dir / "desktop_run.sh"
            try:
                desktop_preflight_script = desktop_run_path.read_text(encoding="utf-8")
            except Exception:
                desktop_preflight_script = ""
            if not desktop_preflight_script.strip():
                log_fn(
                    format_log(
                        "desktop",
                        "cache",
                        "WARN",
                        f"desktop cache active but runtime script is missing: {desktop_run_path}",
                    )
                )
                desktop_preflight_cached = False
                runtime_image = desktop_base_image

    # Settings preflight cache layer
    if cache_settings_enabled and settings_preflight_script.strip():
        check_fn()
        with _cache_build_lock:
            next_image = ensure_phase_image(
                base_image=runtime_image,
                phase_name="settings",
                script_content=settings_preflight_script,
                preflights_dir=preflights_host_dir,
                on_log=log_fn,
            )
        settings_preflight_cached = next_image != runtime_image
        runtime_image = next_image
    elif cache_settings_enabled:
        log_fn(
            format_log(
                "phase",
                "cache",
                "WARN",
                "settings caching enabled but settings script is empty",
            )
        )

    return CacheResolutionResult(
        runtime_image=runtime_image,
        system_preflight_cached=system_preflight_cached,
        desktop_preflight_cached=desktop_preflight_cached,
        settings_preflight_cached=settings_preflight_cached,
        environment_preflight_cached=environment_preflight_cached,
        desktop_preflight_script=desktop_preflight_script,
    )
