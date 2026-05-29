"""Utilities for reading OpenCode model metadata."""

from __future__ import annotations

import json
import subprocess

from typing import Any
from typing import Protocol
from typing import cast

from midori_ai_logger import MidoriAiLogger


class _Logger(Protocol):
    def error(self, message: object) -> object: ...

    def exception(self, message: object) -> object: ...


logger = cast(_Logger, MidoriAiLogger(channel=None, name=__name__))


def _is_model_header(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped[0] in {"{", "[", '"'}:
        return False
    if any(character.isspace() for character in stripped):
        return False
    provider_id, separator, remainder = stripped.partition("/")
    return bool(provider_id and separator and remainder and ":" not in provider_id)


def _variant_names(payload: dict[str, Any]) -> list[str]:
    raw_variants = payload.get("variants")
    if not isinstance(raw_variants, dict):
        return []

    variant_names: list[str] = []
    for raw_name in cast(dict[object, object], raw_variants):
        variant_name = str(raw_name or "").strip()
        if variant_name:
            variant_names.append(variant_name)
    return variant_names


def _finalize_model_entry(header: str, json_lines: list[str]) -> dict[str, object]:
    raw_payload = json.loads("\n".join(json_lines))
    if not isinstance(raw_payload, dict):
        raise ValueError(f"Expected JSON object for model '{header}'")

    payload = cast(dict[str, Any], raw_payload)
    provider_from_header = header.split("/", 1)[0].strip()
    provider_id = str(payload.get("providerID") or provider_from_header).strip()
    model_id = header.strip() or str(payload.get("id") or "").strip()
    if not model_id:
        raise ValueError("Model entry is missing an id")

    display_name = str(payload.get("name") or model_id).strip() or model_id
    return {
        "id": model_id,
        "name": display_name,
        "provider_id": provider_id,
        "variants": _variant_names(payload),
    }


def _parse_verbose_models_output(raw_output: str) -> list[dict[str, object]]:
    models: list[dict[str, object]] = []
    current_header = ""
    current_json_lines: list[str] = []

    for raw_line in raw_output.splitlines():
        stripped = raw_line.strip()

        if _is_model_header(stripped):
            if current_header:
                if not current_json_lines:
                    raise ValueError(f"Missing JSON block for model '{current_header}'")
                models.append(_finalize_model_entry(current_header, current_json_lines))
                current_json_lines = []

            current_header = stripped
            continue

        if not stripped:
            if current_header and current_json_lines:
                models.append(_finalize_model_entry(current_header, current_json_lines))
                current_header = ""
                current_json_lines = []
            continue

        if not current_header:
            continue

        current_json_lines.append(raw_line)

    if current_header:
        if not current_json_lines:
            raise ValueError(f"Missing JSON block for model '{current_header}'")
        models.append(_finalize_model_entry(current_header, current_json_lines))

    return models


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []

    items: list[str] = []
    for raw_item in cast(list[object], value):
        item = str(raw_item or "").strip()
        if item:
            items.append(item)
    return items


def parse_opencode_models() -> list[dict[str, object]]:
    """Return parsed `opencode models --verbose` output."""

    try:
        result = subprocess.run(
            ["opencode", "models", "--verbose"],
            capture_output=True,
            check=False,
            text=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired as exc:
        logger.error(f"Timed out while loading OpenCode models: {exc}")
        return []
    except (FileNotFoundError, OSError) as exc:
        logger.error(f"Failed to run `opencode models --verbose`: {exc}")
        return []

    if result.returncode != 0:
        detail = str(result.stderr or result.stdout or "").strip()
        if not detail:
            detail = f"exit code {result.returncode}"
        logger.error(f"OpenCode models command failed: {detail}")
        return []

    try:
        return _parse_verbose_models_output(str(result.stdout or ""))
    except Exception as exc:
        logger.exception(f"Failed to parse OpenCode model output: {exc}")
        return []


def opencode_model_options() -> list[tuple[str, str, list[str]]]:
    """Return sorted OpenCode model options for UI dropdowns."""

    options: list[tuple[str, str, list[str]]] = []
    for model in parse_opencode_models():
        model_id = str(model.get("id") or "").strip()
        if not model_id:
            continue

        display_label = str(model.get("name") or model_id).strip() or model_id
        options.append((model_id, display_label, _string_list(model.get("variants"))))

    options.sort(key=lambda item: (item[1].casefold(), item[0].casefold()))
    return options


def opencode_model_options_by_provider() -> dict[str, list[tuple[str, str, list[str]]]]:
    """Return OpenCode model options grouped by provider for UI dropdowns.

    Each key is a provider name; each value is a sorted list of
    ``(model_id, display_label, variants)`` tuples for that provider.
    """

    by_provider: dict[str, list[tuple[str, str, list[str]]]] = {}
    for model in parse_opencode_models():
        model_id = str(model.get("id") or "").strip()
        if not model_id:
            continue

        provider, _, _ = model_id.partition("/")
        provider = provider.strip()
        if not provider:
            continue

        display_label = str(model.get("name") or model_id).strip() or model_id
        by_provider.setdefault(provider, []).append(
            (model_id, display_label, _string_list(model.get("variants")))
        )

    for models in by_provider.values():
        models.sort(key=lambda item: (item[1].casefold(), item[0].casefold()))

    return by_provider


__all__ = [
    "opencode_model_options",
    "opencode_model_options_by_provider",
    "parse_opencode_models",
]
