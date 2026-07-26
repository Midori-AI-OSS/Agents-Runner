from __future__ import annotations

from pathlib import Path

MAGIC_PROMPTS_DIR = Path(__file__).resolve().parent


def load_magic_prompts() -> list[dict[str, str]]:
    prompts: list[dict[str, str]] = []
    for md_file in sorted(MAGIC_PROMPTS_DIR.glob("*.md")):
        try:
            lines = md_file.read_text(encoding="utf-8").strip().splitlines()
            if len(lines) < 2:
                continue
            title = lines[0].strip()
            body = "\n".join(lines[1:]).strip()
            if not title or not body:
                continue
            prompts.append({"title": title, "prompt": body})
        except Exception:
            continue
    return prompts


__all__ = ["MAGIC_PROMPTS_DIR", "load_magic_prompts"]
