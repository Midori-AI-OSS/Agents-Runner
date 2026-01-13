# UI Terminology Sweep - Replace Legacy Mode Terms

## Objective
Replace UI strings and identifiers that still reference "git locked", "folder locked", or "gh management mode" with consistent workspace type terminology.

## Scope
Repo-wide search and replace for user-facing strings and UI identifiers.

## Tasks
1. Search for strings containing:
   - "git locked"
   - "folder locked"
   - "gh management mode"
   - "management mode"
   - Other legacy mode terminology
2. Replace with consistent terminology:
   - "Cloned repo" (for WORKSPACE_CLONED)
   - "Mounted folder" (for WORKSPACE_MOUNTED)
   - "No workspace" (for WORKSPACE_NONE)
3. Update UI labels, tooltips, help text, error messages
4. Update comments that reference old terminology
5. Focus on user-facing text; internal variable names handled in other tasks

## Acceptance Criteria
- No user-facing strings mention "git locked", "folder locked", or "management mode"
- Consistent terminology: "Cloned repo", "Mounted folder", "No workspace"
- UI labels and help text are clear and use new terms
- Comments reflect current architecture
- Manual UI review: Check all visible text in environment and task pages
- Grep verification: No matches for legacy terms in user-facing strings
- No console errors from updated strings
