# Task: Fix pyright errors in agents_runner/ui/pages/github_work_list.py

## File
File: `agents_runner/ui/pages/github_work_list.py`
Lines: 331, 395, 400, 420, 429, 463, 622

## Category
`github-work-list-cache`

## Errors
```
  Line 331: Cannot access attribute "cache_updated" for class "object"
  Line 395: Cannot access attribute "get_cache_entry" for class "object"
  Line 400: Cannot access attribute "request_refresh" for class "object"
  Line 420: Cannot access attribute "get_cache_entry" for class "object"
  Line 429: Cannot access attribute "request_refresh" for class "object"
  Line 463: Cannot access attribute "request_refresh_if_stale" for class "object"
  Line 622: Cannot access attribute "is_polling_effective_for_env" for class "object"
```

## Fix
Accessing cache manager attributes on `object` type.
The `coordinator` parameter (line 262) is typed as `object` but needs to be `GitHubWorkCoordinator`.
Change `coordinator: object` to `coordinator: GitHubWorkCoordinator`.
Required import: add `from agents_runner.ui.pages.github_work_coordinator import GitHubWorkCoordinator`.

## Verification
```bash
uv run pyright agents_runner/ui/pages/github_work_list.py
```
