# Agents Runner

A GUI for running AI agents in Docker containers with workspace and GitHub management.

## Quick Start

```bash
uv run main.py
```

## Supported Agents

- **OpenAI Codex** - [Install](https://github.com/openai/codex/blob/main/README.md)
- **Claude Code** - [Install](https://code.claude.com/docs/en/overview) # May not be fully supported, open a issue if you run into bugs
- **GitHub Copilot** - [Install](https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli) # May not be fully supported, open a issue if you run into bugs
- **Google Gemini** - [Install](https://github.com/google-gemini/gemini-cli) # May not be fully supported, open a issue if you run into bugs

## Features

- **Docker Integration**: Runs agents in `lunamidori5/pixelarch:emerald` container
- **Interactive Mode**: Launch TTY sessions in your terminal emulator (Linux/macOS)
- **Environment Management**: Configure multiple workspaces with custom settings
- **GitHub Support**: Automatic branch creation and PR management
- **Preflight Scripts**: Run custom setup before each container launch

## Usage

1. **New Task**: Enter prompt, select environment, click "Run Agent"
2. **Interactive**: Use "Run Interactive" for TTY access to agent TUIs
3. **Container Args**: Pass CLI flags (starting with `-`) or shell commands like `bash`

## Configuration

- **State**: `~/.midoriai/agents-runner/state.json`
- **Environments**: `~/.midoriai/agents-runner/environment-*.json`
- **Agent Config**: `~/.codex`, `~/.claude`, `~/.gemini` or `~/.copilot` → `/home/midori-ai/.{agent}` (override: `AGENTS_RUNNER_STATE_PATH`)

## Diagnostics and Issue Reporting

### Creating Diagnostics Bundle

To report an issue or bug:

1. Click the "Report Issue" button in the main toolbar
2. Review the explanation of what data will be included
3. Click "Create Diagnostics Bundle"
4. Attach the generated bundle to your issue report

Diagnostics bundles contain:
- Application version and system information
- Recent task logs (last 10 tasks)
- Application settings (safe settings only)
- Task state information

All sensitive information (tokens, keys, passwords, authorization headers) is automatically redacted.

### Crash Reports

If the application crashes, a crash report is automatically saved to:
- `~/.midoriai/agents-runner/diagnostics/crash_reports/`

On next startup, you will be notified and can open the crash reports folder to attach the report to your issue.

### What Gets Redacted

The diagnostics system automatically redacts:
- Authorization headers and bearer tokens
- API keys, secrets, passwords
- Cookie values
- GitHub tokens (ghp_, gho_, ghs_, etc.)
- Any token-like strings in logs

Bundles are safe to share publicly on issue trackers.
