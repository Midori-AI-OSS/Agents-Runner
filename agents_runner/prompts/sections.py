from __future__ import annotations

from collections.abc import Sequence


PROMPT_SECTION_DIVIDER = "-----"
_PROMPT_SECTION_JOINER = f"\n\n{PROMPT_SECTION_DIVIDER}\n\n"


def _clean_section(value: str | None) -> str:
    return str(value or "").strip()


def split_prompt_sections(prompt: str) -> list[str]:
    text = str(prompt or "").strip()
    if not text:
        return []
    if _PROMPT_SECTION_JOINER not in text:
        return [text]
    return [part.strip() for part in text.split(_PROMPT_SECTION_JOINER) if part.strip()]


def compose_prompt_sections(sections: Sequence[str]) -> str:
    cleaned = [_clean_section(section) for section in sections]
    non_empty = [section for section in cleaned if section]
    return _PROMPT_SECTION_JOINER.join(non_empty)


def append_prompt_sections(prompt: str, sections: Sequence[str]) -> str:
    existing = split_prompt_sections(prompt)
    additions = [_clean_section(section) for section in sections]
    additions = [section for section in additions if section]
    return compose_prompt_sections([*existing, *additions])


def insert_prompt_sections_before_user_prompt(
    prompt: str, sections: Sequence[str]
) -> str:
    existing = split_prompt_sections(prompt)
    additions = [_clean_section(section) for section in sections]
    additions = [section for section in additions if section]

    if not additions:
        return compose_prompt_sections(existing)
    if not existing:
        return compose_prompt_sections(additions)

    return compose_prompt_sections([*existing[:-1], *additions, existing[-1]])
