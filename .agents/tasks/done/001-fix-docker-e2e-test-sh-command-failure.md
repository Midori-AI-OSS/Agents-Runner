# Fix Docker E2E Test - sh Command Parsing Failure

## Issue
The test `test_task_lifecycle_completes_successfully` in `agents_runner/tests/test_docker_e2e.py` is failing when run with Docker access enabled (via sudo).

**Exit Code:** 1 (expected 0)

**Error Message from Container Logs:**
```
WARNING: proceeding, even though we could not update PATH: Permission denied (os error 13)
Error parsing -c overrides: Invalid override (missing '='): sleep 20 && echo 'test output' && exit 0
```

## Root Cause
The test uses `agent_cli="sh"` with `agent_cli_args=["-c", "sleep 20 && echo 'test output' && exit 0"]`. When the container executes, the yay package manager in the PixelArch image is somehow being invoked instead of the shell, treating the `-c` flag as a yay package manager override flag.

## Investigation Details
1. Container exits immediately (< 0.1s) with exit code 1
2. The error message "Error parsing -c overrides" is specific to the yay package manager
3. Direct Docker test with `/bin/bash -lc 'exec sh -c "..."'` works correctly
4. The issue occurs in the generated Docker command execution path

## Acceptance Criteria
- [x] `test_task_lifecycle_completes_successfully` passes with sudo (Docker access enabled)
- [x] Container executes the shell command and exits with code 0
- [x] Test output shows "test output" in logs
- [x] No regressions in other tests

## Reproduction Steps
```bash
cd /home/midori-ai/workspace
sudo -E /home/midori-ai/workspace/.venv/bin/pytest agents_runner/tests/test_docker_e2e.py::test_task_lifecycle_completes_successfully -v
```

## Suggested Fix Areas to Investigate
1. Check how `build_noninteractive_cmd` constructs the command for `agent_raw="sh"`
2. Verify the Docker run command generation in `_build_docker_run_args`
3. Investigate if there's a PATH issue or profile script in PixelArch causing `sh` to resolve to yay
4. Consider using absolute path `/bin/sh` instead of relative `sh` for test commands
5. Review the `verify_cli_clause` function to ensure it doesn't interfere with test commands

## Files to Review
- `agents_runner/docker/agent_worker_container.py` (Docker command building)
- `agents_runner/agent_cli.py` (`build_noninteractive_cmd` function)
- `agents_runner/tests/test_docker_e2e.py` (test setup)
- `agents_runner/core/shell_templates.py` (`verify_cli_clause`)

## Priority
High - Blocks E2E testing validation

---

## Resolution (Completed)

**Fixed by:** Coder mode
**Date:** 2026-02-03
**Commit:** 7637f40

### Actual Root Cause
The `normalize_agent()` function in `agent_worker_setup.py` was being called on all agent_cli values, including test commands like `/bin/sh`. Since `/bin/sh` is not in the `SUPPORTED_AGENTS` list ("codex", "claude", "copilot", "gemini"), it was being converted to the default agent "codex". This caused the Docker container to execute `codex exec ...` instead of `/bin/sh -c ...`, and since codex is not installed in the test image, the shell's command handler tried to interpret it as a command and yay (the AUR helper) was invoked instead.

### Changes Made
1. **agents_runner/docker/agent_worker_setup.py** - Added bypass for test/debug commands before calling normalize_agent
2. **agents_runner/agent_cli.py** - Extended test command list to include absolute paths (/bin/sh, /bin/bash, etc.)
3. **agents_runner/tests/test_docker_e2e.py** - Updated test to use `/bin/sh` instead of `sh` and fixed persistence assertions

### Verification
- Test now passes with exit code 0
- Container executes for ~21s (expected 20s sleep)
- Test output includes "test output" message
- All E2E tests pass
- Code formatted with ruff
- Ruff linter passes with no errors
