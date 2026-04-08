# setup-agents.sh

## Overview
`setup-agents.sh` prepares the PixelArch Emerald container for your repository.

## Location
- Primary: `.agents/setup-agents.sh`
- Fallback: `.github/setup-agents.sh`
- Must be executable and committed
- Runs from repository root - do NOT add cd commands

## What Goes In The Script
- Install packages not in Emerald: `yay -Syu --noconfirm --needed <packages>`
- Install project dependencies (`uv sync`, `npm install`, etc.)
- Configure git hooks and tooling

## PixelArch Emerald Preinstalled
See [PixelArch Emerald](https://io.midori-ai.xyz/pixelos/pixelarch/).
Already includes: `gh`, `claude-code`, `codex`, `copilot`, `python`, `nodejs`, `rust`, `openssh`, `tmate`, `tor`, `lynx`

## Environment Variable
`MIDORI_AI_AGENTS_RUNNER_INTERACTIVE=true` for interactive mode, `false` for agent runs.

## Example (from this repo)
```bash
#!/usr/bin/env bash
set -euo pipefail

uv sync
uv sync --group ci
git config --local core.hooksPath .githooks
```

## Anti-Patterns
- Do NOT add cd commands - working directory is already repo root
- Do NOT use `pacman` or plain `yay -S` - always `yay -Syu`
- Do NOT store secrets
- Do NOT manipulate git branches/remotes

## Missing Script
If missing, guidance is injected in non-IDE mode. Environment setting `Inject missing setup-agents prompt` controls this.
