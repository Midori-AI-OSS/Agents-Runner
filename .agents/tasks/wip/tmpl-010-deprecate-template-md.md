# Task — Deprecate or remove template.md

## 1. Title (short)
Deprecate old template.md file

## 2. Summary (1–3 sentences)
After verifying that the new template injection is working, either delete `agents_runner/prompts/template.md` or replace it with a deprecation notice pointing to the new `templates/` structure.

## 3. Implementation notes (key decisions + constraints)
- Prerequisites: tmpl-009 must be completed and verified working
- Check that `template.md` is no longer referenced anywhere in the codebase:
  - Run: `grep -r "load_prompt.*template['\"]" agents_runner/` (should find no matches except in comments)
  - Run: `grep -r "template\.md" agents_runner/` (should find no matches except possibly in comments)
  - Specifically verify line 378 in `agents_runner/docker/agent_worker.py` no longer references template.md
- Two options (choose one):
  - **Option A (preferred):** Delete the file entirely if no references remain
  - **Option B:** Replace content with a short deprecation notice:
    ```markdown
    # DEPRECATED
    
    This file has been split into multiple template files under `templates/`:
    - `templates/midoriaibasetemplate.md`
    - `templates/subagentstemplate.md`
    - `templates/crossagentstemplate.md`
    - `templates/agentcli/*.md`
    
    See `agents_runner/docker/agent_worker.py` for the new injection logic.
    ```
- Commit message should clearly indicate deprecation/removal
- After deletion/deprecation, verify with: `git status` shows change, `ls agents_runner/prompts/` no longer shows template.md (or shows modified if using Option B)

## 4. Acceptance criteria (clear, testable statements)
- Either `agents_runner/prompts/template.md` is deleted, or contains only deprecation notice
- `grep -r "load_prompt.*template['\"]" agents_runner/` returns no matches (except possibly in git history/comments)
- Line 378 in `agents_runner/docker/agent_worker.py` does not reference template.md
- Git commit clearly documents the change with appropriate commit type tag
- If deleted: `git status` shows deletion; if deprecated: `git status` shows modification

## 5. Expected files to modify (explicit paths)
- Delete or modify: `agents_runner/prompts/template.md`

## 6. Out of scope (what not to do)
- Do not modify any Python code (already done in tmpl-009)
- Do not update `README.md`
- Do not add tests
