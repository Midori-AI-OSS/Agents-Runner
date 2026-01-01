#!/usr/bin/env bash
set -euo pipefail

HELP_ROOT="${AGENT_HELP_ROOT:-${HOME}/.agent-help}"
REPOS_DIR="${HELP_ROOT}/repos"

if ! command -v git >/dev/null 2>&1; then
  echo "[preflight] helpme: git not found"
  exit 1
fi

mkdir -p "${REPOS_DIR}"

clone_repo() {
  local name="$1"
  local url="$2"
  local dest="${REPOS_DIR}/${name}"

  if [ -d "${dest}/.git" ]; then
    echo "[preflight] helpme: ${name} already cloned"
    return 0
  fi

  if [ -e "${dest}" ]; then
    local backup="${dest}.bak.$(date +%s)"
    echo "[preflight] helpme: moving existing ${dest} -> ${backup}"
    mv -- "${dest}" "${backup}"
  fi

  echo "[preflight] helpme: cloning ${name} from ${url}"
  git clone --depth 1 --single-branch "${url}" "${dest}"
}

clone_repo "codex" "https://github.com/openai/codex"
clone_repo "copilot-cli" "https://github.com/github/copilot-cli"
clone_repo "claude-code" "https://github.com/anthropics/claude-code"
clone_repo "Agents-Runner" "https://github.com/Midori-AI-OSS/Agents-Runner"

echo "[preflight] helpme: ready at ${REPOS_DIR}"
