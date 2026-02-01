# Meta Task: AGENTS.md Compliance Scan (Read-Only) + Follow-up Task Generation

> **AUDITOR FIX NOTE (2026-02-01):**  
> Task returned from done/ for completion. Missing primary deliverable: `/tmp/agents-artifacts/agents-md-compliance-report.md`.  
> Follow-up tasks (7) were created successfully. Must create the comprehensive scan report summarizing all 5 scan areas, evidence, and mapping to follow-up tasks before re-submitting.  
> See audit report: `/tmp/agents-artifacts/304ffb52-audit-meta-task.audit.md`

## Goal

Produce a concrete list of mismatches between the repo and the current contributor rules, and convert each mismatch into an actionable task file under `.agents/tasks/wip/`.

Primary rule sources:

- `AGENTS.md` (repo root)
- `.github/copilot-instructions.md`

This meta task itself is **read-only** (no code changes). It is specifically about:

1. Finding rule mismatches.
2. Writing follow-up tasks with acceptance criteria + verification commands.

## Constraints

- No code edits in this meta task run.
- No dependency installs.
- Do not update `README.md`.
- Keep notes short and task-scoped (prefer task files over long documents).

## Deliverables

1. A scan report artifact at `/tmp/agents-artifacts/agents-md-compliance-report.md` containing:
   - Rule reference (file + section)
   - Evidence (file paths + grep hits)
   - Impact/risk
   - Recommended remediation approach
   - Proposed follow-up task file name(s)
2. Follow-up task files added to `.agents/tasks/wip/`:
   - One task per “theme” (avoid dozens of micro tasks unless the mismatch is isolated).
   - Each task includes: scope, non-goals, acceptance criteria, and verification commands.

## Recommended Subagent-Driven Workflow (Read-Only)

Run 5 focused sub-agents and merge their findings into one report:

### Subagent 1: Repo Layout + UI boundaries

Artifact: `/tmp/agents-artifacts/agents-md-scan-layout-ui.md`

Prompt:

> You are running in read-only mode. Scan this repo for mismatches with `AGENTS.md` related to repo layout, UI placement, and Qt import boundaries. Provide a list of concrete violations with file paths, ripgrep commands to reproduce the finding, and a recommended remediation plan. Do not propose code patches; propose follow-up task file titles and acceptance criteria.

### Subagent 2: Packaging + Python packages hygiene

Artifact: `/tmp/agents-artifacts/agents-md-scan-packaging.md`

Prompt:

> You are running in read-only mode. Scan this repo for mismatches with `AGENTS.md` related to packaging, Python package boundaries, and `__init__.py` presence for importable directories. Provide concrete findings with file paths and commands to verify. Suggest follow-up task titles and acceptance criteria.

### Subagent 3: Config hygiene (TOML + canonical rewrite rules)

Artifact: `/tmp/agents-artifacts/agents-md-scan-config.md`

Prompt:

> You are running in read-only mode. Scan this repo for mismatches with `AGENTS.md` related to configuration: TOML-only config, canonicalization with Pydantic, and atomic rewrites. Identify any JSON config usage or env-var-driven config that exceeds the allowed scope. Provide concrete findings and recommended follow-up tasks.

### Subagent 4: Logging + “minimal logging” / “no print” guidance

Artifact: `/tmp/agents-artifacts/agents-md-scan-logging.md`

Prompt:

> You are running in read-only mode. Scan this repo for mismatches with `AGENTS.md` related to logging: `midori_ai_logger` usage, avoiding `print()` for non-CLI output, and avoiding ad-hoc logging wrappers. Provide concrete findings and propose follow-up task(s).

### Subagent 5: Structure guardrails (main dispatcher, file size limits, tests placement)

Artifact: `/tmp/agents-artifacts/agents-md-scan-structure.md`

Prompt:

> You are running in read-only mode. Scan this repo for mismatches with `AGENTS.md` related to: `main.py` being a thin dispatcher, monolith file limits (soft/hard), and tests placement rules. Provide concrete findings with commands and propose follow-up tasks.

## Manual Scan Commands (Fast Local Checks)

Run these commands and paste any hits into the report.

### UI / Qt boundary checks

```bash
rg -n "^(from PySide6|import PySide6)" -S agents_runner --glob '!agents_runner/ui/**'
rg -n "\\bQt[A-Za-z0-9_]+" -S agents_runner --glob '!agents_runner/ui/**'
```

### UI placement checks (UI code outside `agents_runner/ui/`)

```bash
rg -n "QWidget|QMainWindow|QApplication|Signal\\b|Slot\\b" -S agents_runner --glob '!agents_runner/ui/**'
ls -la agents_runner | rg -n "^(style|widgets)$"
```

### Packaging hygiene (`__init__.py`)

```bash
python - <<'PY'
from pathlib import Path
root = Path("agents_runner")
missing = []
for directory in root.rglob("*"):
    if not directory.is_dir():
        continue
    if directory.name == "__pycache__":
        continue
    has_py = any(p.suffix == ".py" for p in directory.iterdir() if p.is_file())
    if not has_py:
        continue
    if not (directory / "__init__.py").exists():
        missing.append(str(directory))
print("\\n".join(sorted(missing)))
PY
```

### Config hygiene (JSON + env usage)

```bash
rg -n "\\bjson\\.(dump|dumps|load|loads)\\b|\\.json\\b" -S agents_runner
rg -n "\\bos\\.(getenv|environ)\\b" -S agents_runner
```

### Logging hygiene (print)

```bash
rg -n "\\bprint\\(" -S agents_runner
```

### Dispatcher / file size limits / tests placement

```bash
wc -l main.py agents_runner/**/*.py | sort -n | tail -n 25
rg -n "\\bpytest\\b|unittest\\b" -S agents_runner | head
```

## Follow-up Task Authoring Guide

Each follow-up task must include:

- Summary + goal
- Scope / non-goals
- Inventory of affected files (as discovered by scans)
- Acceptance criteria written as verifiable checks
- Verification commands (ripgrep checks + `uv run ruff check .` if relevant)

## Definition of Done (Meta Task)

- `/tmp/agents-artifacts/agents-md-compliance-report.md` exists and summarizes findings across all scan areas.
- Follow-up tasks exist under `.agents/tasks/wip/` for each major mismatch theme.
- Each follow-up task has at least one verification command that fails before changes and passes after changes.
