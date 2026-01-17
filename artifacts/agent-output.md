## Task: Implement GitHub Context Pass-through for Interactive Mode - Summary

### Fix Description

The application was failing to pass the GitHub token to the 'Run Interactive' session's environment. The original implementation relied on a shell script snippet (`gh_token_snippet`) to resolve the token on the host and pass it to the Docker container. This mechanism was unreliable.

The fix involves the following changes in `agents_runner/ui/main_window_tasks_interactive_docker.py`:

1.  **Direct Token Resolution:** The `resolve_github_token` function from `agents_runner.github_token` is now used to directly resolve the GitHub token within the application's Python code before launching the Docker container.

2.  **Environment Variable Injection:** The resolved token is directly injected into the Docker container's environment variables via the `-e` flag in the `docker run` command.

3.  **Removal of Redundant Code:** The old, unreliable `gh_token_snippet` and the `docker_env_passthrough` logic have been removed, resulting in a cleaner and more robust implementation.

### Verification Steps

To verify the fix:

1.  Launch the application.
2.  Enable **Github Context** in the **Environments** menu.
3.  Start a **Run Interactive** session.
4.  In the interactive terminal, execute `env | grep GITHUB_TOKEN`. The `GITHUB_TOKEN` environment variable should be present and have a value.
5.  Execute `gh auth status`. It should now report that you are logged in to GitHub.