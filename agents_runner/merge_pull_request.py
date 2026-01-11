from __future__ import annotations


def build_merge_pull_request_prompt(
    *,
    base_branch: str,
    target_branch: str,
    pull_request_number: int,
) -> str:
    base_branch = str(base_branch or "").strip()
    target_branch = str(target_branch or "").strip()
    pull_request_number = int(pull_request_number)

    return f"""Goal
- Make the pull request mergeable, then merge it.

Authoritative inputs (do not change these)
- Base branch: {base_branch}
- Target branch: {target_branch}
- Pull request number: {pull_request_number}

Required procedure (must resolve conflicts if they exist)
1) Use `gh` to view pull request details and confirm:
   - The base branch matches the provided base branch.
   - The head branch matches the provided target branch.
   - If there is a mismatch, stop and report it. Do not merge.
2) Check out the pull request branch using `gh`.
3) Fetch the base branch from origin.
4) Merge the base branch into the target branch locally.
5) If merge conflicts occur:
   - List every conflicted file.
   - Resolve each conflict carefully, preserving intended behavior from both branches.
   - Build and run repository validation steps if they exist (tests, linting, formatting, type checks).
   - Commit conflict resolutions with a clear message.
   - Push the updated target branch so the pull request updates.
   - Re-check mergeability.
6) Repeat conflict resolution until the pull request is mergeable or until a blocking issue is found.
7) When mergeable and validation passes, merge using `gh`.
8) Confirm the pull request is merged and record the merge commit.

Decision rules (must follow)
- If validation fails, do not merge. Report what failed and how to reproduce it.
- If conflicts cannot be resolved without dangerous guessing, do not merge. Report the conflicts and recommended next steps.
- Do not use force push unless the repository explicitly requires it and you explain why.
- Do not merge if base branch or target branch does not match the authoritative inputs.
"""

