# Task: Setup diagnostics directory infrastructure

## Description
Create the infrastructure for storing diagnostics bundles and crash reports in a stable location within the application data directory.

## Requirements
1. Create a diagnostics module/file that establishes:
   - A stable diagnostics directory path (e.g., `~/.midoriai/diagnostics/`)
   - Subdirectories for bundles and crash reports
   - Helper functions to ensure directories exist on demand
2. Add functions to get the paths for:
   - Diagnostics root directory
   - Bundles subdirectory
   - Crash reports subdirectory

## Acceptance Criteria
- [ ] Diagnostics directory is created in `~/.midoriai/diagnostics/`
- [ ] Directory structure includes `bundles/` and `crash_reports/` subdirectories
- [ ] Module provides clean API to access these paths
- [ ] Directories are created automatically if they don't exist
- [ ] Code follows Python 3.13+ type hints standards

## Related Tasks
- Depends on: None
- Blocks: b8d4c320, c9e5d431, d0f6e542

## Notes
- Use pathlib for cross-platform path handling
- Follow existing patterns in `agents_runner/environments/paths.py` for consistency
- The base data directory is `~/.midoriai/agents-runner/` (see `agents_runner/persistence.py:default_state_path()`)
- Example structure: Create `agents_runner/diagnostics/paths.py` with functions like:
  - `diagnostics_root_dir()` -> `~/.midoriai/diagnostics/`
  - `bundles_dir()` -> `~/.midoriai/diagnostics/bundles/`
  - `crash_reports_dir()` -> `~/.midoriai/diagnostics/crash_reports/`
- Use `os.makedirs(path, exist_ok=True)` to ensure directories exist
