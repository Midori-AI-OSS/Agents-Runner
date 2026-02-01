# Task: Audit and Reduce Environment Variable Config Usage

## Goal

Reduce environment variable usage for configuration, preferring TOML config per AGENTS.md guidance, while keeping necessary exceptions for UI/runtime integration and security.

## Rule Reference

**AGENTS.MD Section:** "Configuration"
> "Env vars are allowed only for Qt/UI/runtime integration; derive them from TOML settings and apply in-process temporarily and/or only to child process `env` dicts."

**Violation:** Environment variables used for application config beyond UI/runtime scope.

## Scope

- Audit all `os.environ.get` and `os.getenv` usage
- Identify config that should move to TOML
- Document acceptable env var exceptions
- Propose migration path for each

## Non-Goals

- Do not remove UI/runtime env vars (Qt flags, fontconfig, etc.)
- Do not remove security-sensitive env vars (API keys) unless clearly wrong
- Do not change behavior, only audit and propose

## Affected Files Inventory

**Non-UI Env Var Usage Found:**

1. `agents_runner/persistence.py`:
   - `AGENTS_RUNNER_STATE_PATH`: State file path override
   - **Assessment:** Should be TOML config

2. `agents_runner/github_token.py`:
   - GitHub token lookup from multiple env vars
   - **Assessment:** Security-sensitive, may be acceptable

3. `agents_runner/agent_cli.py`:
   - `CODEX_HOST_CODEX_DIR`: Host directory path
   - **Assessment:** Should be TOML config or CLI arg

4. `agents_runner/setup/agent_status.py`:
   - `GEMINI_API_KEY`, `GOOGLE_GENAI_USE_VERTEXAI`, `GOOGLE_GENAI_USE_GCA`
   - **Assessment:** API credentials, likely acceptable

5. `agents_runner/terminal_apps.py`:
   - `TERMINAL`: Terminal emulator hint
   - **Assessment:** Runtime integration, acceptable

6. `agents_runner/docker/agent_worker.py`:
   - `dict(os.environ)`: Passing env to Docker
   - **Assessment:** Runtime integration, acceptable

7. `agents_runner/docker/preflight_worker.py`:
   - `dict(os.environ)`: Passing env to Docker
   - **Assessment:** Runtime integration, acceptable

8. `agents_runner/gh/process.py`:
   - `dict(os.environ)`: Passing env to subprocess
   - **Assessment:** Runtime integration, acceptable

**UI/Runtime Env Var Usage (Acceptable):**
- `ui/runtime/app.py`: Qt/fontconfig settings
- `ui/desktop_viewer/app.py`: Qt/Chromium flags
- `ui/main_window*.py`: Host paths for Docker binding
- `ui/qt_diagnostics.py`: Qt diagnostics flag

## Acceptance Criteria

- [ ] Create inventory document at `/tmp/agents-artifacts/env-var-audit.md`
- [ ] Categorize each env var usage: Move to TOML / Keep (security) / Keep (runtime)
- [ ] Document proposed TOML config structure for items to migrate
- [ ] Propose migration strategy for `AGENTS_RUNNER_STATE_PATH`
- [ ] Propose migration strategy for `CODEX_HOST_CODEX_DIR`
- [ ] Document security exceptions (API keys)
- [ ] Document runtime exceptions (subprocess env passing)

## Verification Commands

**Audit command:**
```bash
# Find all env var usage
rg -n "os\\.environ\\.get|os\\.getenv" agents_runner --include="*.py" > /tmp/env-var-audit-raw.txt
cat /tmp/env-var-audit-raw.txt

# Count by file
rg -n "os\\.environ\\.get|os\\.getenv" agents_runner --include="*.py" | cut -d: -f1 | sort | uniq -c | sort -n

# Find non-UI usage
rg -n "os\\.environ\\.get|os\\.getenv" agents_runner --glob '!agents_runner/ui/**' --include="*.py"
```

## Deliverables

Create `/tmp/agents-artifacts/env-var-audit.md` with:

1. **Inventory Table:**
   - File path
   - Env var name
   - Current usage
   - Recommendation: TOML / Keep (security) / Keep (runtime)
   - Migration effort: Low / Medium / High

2. **Proposed TOML Config Structure:**
   ```toml
   [paths]
   state_override = ""  # Empty means use default
   
   [docker]
   host_codex_dir = "~/.codex"
   host_workdir = ""
   ```

3. **Migration Strategy:**
   - Priority order
   - Breaking changes assessment
   - Backward compatibility plan

4. **Security Exceptions:**
   - API keys that should stay as env vars
   - Justification for each

## Expected Outcome

After this audit task:
- Clear inventory of env var usage
- Documented migration path
- Prioritized list of changes
- Follow-up implementation task(s) created if needed

## Definition of Done

- Audit document created at `/tmp/agents-artifacts/env-var-audit.md`
- All env var usage categorized
- Migration proposals documented
- Committed with message: `[AUDIT] Document environment variable usage and TOML migration plan`
- Version bumped in `pyproject.toml` (TASK +1)
- If implementation needed, create follow-up task: `[CODER] Migrate env config to TOML.md`
