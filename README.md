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

- **State**: `~/.midoriai/codex-container-gui/state.json`
- **Environments**: `~/.midoriai/codex-container-gui/environment-*.json`
- **Agent Config**: `~/.codex`, `~/.claude`, or `~/.copilot` → `/home/midori-ai/.{agent}` (override: `CODEX_HOST_CODEX_DIR`)
