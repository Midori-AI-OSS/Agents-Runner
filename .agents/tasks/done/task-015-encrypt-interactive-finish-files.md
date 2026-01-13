# Task 015: Encrypt Interactive Finish Files as Artifacts

## Problem
The `~/.midoriai/agents-runner/` directory accumulates `interactive-finish-*.txt` files from every interactive run. These need to be encrypted as artifacts and deleted after processing.

## Location
- `agents_runner/ui/main_window_tasks_interactive_docker.py` (creates finish file at line 204)
- `agents_runner/ui/main_window_tasks_interactive_finalize.py` (processes finish file)
- `agents_runner/artifacts.py` (encryption utilities)

## Acceptance Criteria
- [ ] Identify where finish file is read/processed after interactive run completes
- [ ] After reading finish file, encrypt its contents as an artifact
- [ ] Delete plaintext finish file after successful encryption
- [ ] Test interactive run to verify finish file is created, processed, encrypted, and deleted
- [ ] Verify encrypted artifact can be decrypted and contains expected exit code data
- [ ] Handle error case: if encryption fails, log warning but still delete plaintext file

## Notes
- Finish file is created at `~/.midoriai/agents-runner/interactive-finish-{task_id}.txt`
- File contains exit code for tracking interactive session completion
- Must not break existing exit code tracking functionality
