# Agents Runner

A GUI for running AI agents in Docker containers with workspace and GitHub management.

## Quick Start

```bash
uv run main.py
```

Requires `docker` and `ffmpeg` installed on the host.

## Supported Agents

- **OpenAI Codex** - [Install](https://github.com/openai/codex/blob/main/README.md)
- **Claude Code** - [Install](https://code.claude.com/docs/en/overview) # May not be fully supported, open a issue if you run into bugs
- **GitHub Copilot** - [Install](https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli)
- **Google Gemini** - [Install](https://github.com/google-gemini/gemini-cli)

## Features

- **Docker Integration**: Runs agents in `lunamidori5/pixelarch:emerald` container
- **Container Caching**: Pre-build cached images to reduce Run Agent startup from ~7min to ~4sec
- **Interactive Mode**: Launch TTY sessions in your terminal emulator (Linux/macOS)
- **noVNC Desktop**: Per-environment option (with global override); interactive can launch with or without desktop
- **Host Cache Mount**: Optionally mounts `~/.cache` into containers to speed up installs (Run Agent + Interactive)
- **Per-Environment Container Args**: Configure agent CLI flags per environment (Environments → Agents → CLI Flags)
- **Environment Management**: Configure multiple workspaces with custom settings
- **GitHub Support**: Automatic branch creation and PR management
- **Preflight Scripts**: Run custom setup before each container launch

## Usage

1. **New Task**: Select environment, enter prompt, click "Run Agent"
2. **Interactive**: Use "Run Interactive" for TTY access to agent TUIs

## Configuration

- **State**: `~/.midoriai/agents-runner/state.json`
- **Environments**: `~/.midoriai/agents-runner/environments.json`
- **Agent Config**: `~/.codex`, `~/.claude`, `~/.gemini` or `~/.copilot` → `/home/midori-ai/.{agent}`
