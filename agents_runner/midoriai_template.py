from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class MidoriAITemplateDetection:
    midoriai_template_likelihood: float
    midoriai_template_detected: bool
    midoriai_template_detected_path: str | None


_CANDIDATE_DIRS: tuple[str, ...] = (
    ".agents/modes",
    ".codex/modes",
    ".github/agents",
)

_KNOWN_NAMES_BY_DIR: dict[str, tuple[str, ...]] = {
    ".agents/modes": (
        "AUDITOR.md",
        "CLEANER.md",
        "CODER.md",
        "MANAGER.md",
        "QA.md",
        "REVIEWER.md",
        "TASKMASTER.md",
        "TESTER.md",
    ),
    ".codex/modes": (
        "AUDITOR.md",
        "CLEANER.md",
        "CODER.md",
        "MANAGER.md",
        "QA.md",
        "REVIEWER.md",
        "TASKMASTER.md",
        "TESTER.md",
    ),
    ".github/agents": (
        "auditor.md",
        "cleaner.md",
        "coder.md",
        "mode-picker.md",
        "qa.md",
        "taskmaster.md",
        "worker.md",
    ),
}


def _clamp_unit(value: float) -> float:
    if value <= 0.0:
        return 0.0
    if value >= 1.0:
        return 1.0
    return float(value)


def scan_midoriai_agents_template(workspace_root: str) -> MidoriAITemplateDetection:
    root = Path(workspace_root).expanduser()

    best_score = -1.0
    best_path: str | None = None
    any_dir_matched_at_least_four = False
    found_candidate_dir = False

    for rel_dir in _CANDIDATE_DIRS:
        expected = _KNOWN_NAMES_BY_DIR.get(rel_dir)
        if not expected:
            continue
        candidate = root / rel_dir
        if not candidate.is_dir():
            continue
        found_candidate_dir = True

        try:
            actual_names = {
                p.name.casefold() for p in candidate.iterdir() if p.is_file()
            }
        except Exception:
            actual_names = set()

        expected_names = {name.casefold() for name in expected}
        matched = len(actual_names & expected_names)
        any_dir_matched_at_least_four = any_dir_matched_at_least_four or matched >= 4

        expected_count = max(1, len(expected))
        score = _clamp_unit(matched / expected_count)
        if score > best_score:
            best_score = score
            best_path = rel_dir

    likelihood = _clamp_unit(best_score if found_candidate_dir else 0.0)
    detected = bool((likelihood > 0.4) or any_dir_matched_at_least_four)
    return MidoriAITemplateDetection(
        midoriai_template_likelihood=likelihood,
        midoriai_template_detected=detected,
        midoriai_template_detected_path=best_path,
    )
