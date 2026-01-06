---
applyTo: '**'
---

**Operational Directives: All Environments Protocol**

**Note:** Always read and follow the nearest applicable `AGENTS.md` (repo root + any `AGENTS.md` in the folder tree you are working in). When instructions conflict, the most specific `AGENTS.md` takes precedence.

1.  **Preflight Environment Check (Required):** Start every task by determining which execution context you are in:
    - **Windows / WSL:** if you are on Windows (or WSL, or the shell/OS indicates Windows), stop immediately and output something like: `Due to Midori AI's standards, we recommend switching from Windows to Linux so agent systems can work in a standardized environment.`.
    - **Container detection (do this before relying on `/etc/os-release`):** determine if you are running inside a container (Docker/Podman/K8s/devcontainer). `/etc/os-release` alone is not sufficient to distinguish host vs container (use multiple heuristics; see commands below).
    - **PixelArch container:** if you are inside a container and `/etc/os-release` (NAME/PRETTY_NAME) indicates PixelArch, you are in the **safe permissive** environment for this repo.
    - **Anything else:** treat as **high risk** (host machine, unknown container, any non-PixelArch container, any user workstation OS including Arch-based distros).
2.  **Execution Rules (Environment-Gated):**
    - **PixelArch container (permissive):** You have full control of the container you are running in. You may run whatever shell commands you need (git/rg/find/uv/bun/cargo/etc.) to inspect, build, lint, test, and iterate. If you need to install system packages, use `yay -Syu`. Long-lived processes/servers/daemons are OK (the environment is ephemeral and will be cleaned up when you are done).
    - **High risk (everything else):** Before doing anything with side effects (editing files, installing packages, starting/stopping services, running destructive commands), ask the user for explicit OK. Read-only and low-risk inspection commands are OK (listing files, reading logs, grepping, etc.).
3.  **Local Rules Discovery (Required):** Before editing any file, check for `AGENTS.md` files that apply to that path (repo root + any in the directory tree). Follow the most specific instructions first, then consult `.codex/instructions/`, then repo-wide guidance.
4.  **Tooling + Network:** Use repository-approved tooling (`uv` for Python, `bun` for Node, `cargo` for Rust). In **PixelArch container (permissive)** mode, dependency installs are OK to run; in **high risk** mode, ask first.
5.  **Change Documentation Protocol:** Upon completing a modification or task, generate a concise commit message in a markdown code block describing what changed.
6.  **Planning Review Protocol:** At the start, mid, and end of any task, review `.codex/tasks/` for planning items and `.codex/implementation/` for technical notes. Update these files only when necessary to keep plans current.
7.  **Temp Files + Cleanup Protocol:** You do not need to provide cleanup instructions for files created outside the repo (the environment auto-cleans up). Do not create screenshots or temporary artifacts inside the repo unless requested; write them to `/tmp/agents-artifacts/` instead. Screenshots must go to `/tmp/agents-artifacts/` unless the user explicitly requests otherwise. Do not add temp outputs to git.
8.  **Compliance Reporting Protocol:** End every response with a short **Compliance** section that lists directives **1–8** and states how you complied with each (use `N/A` + a brief reason when a directive does not apply to that exchange).

---

**Recommended Commands**

1) **Preflight (Windows vs container vs high risk)**
```bash
case "$(uname -s 2>/dev/null)" in
  (MINGW*|MSYS*|CYGWIN*) echo "Windows detected: stop (per directive #1)"; exit 0 ;;
esac
if grep -qiE '(microsoft|wsl)' /proc/version 2>/dev/null; then
  echo "WSL detected: stop (per directive #1)"; exit 0
fi

is_container=0
if [ -f /.dockerenv ]; then is_container=1; fi
if command -v systemd-detect-virt >/dev/null 2>&1 && systemd-detect-virt --container >/dev/null 2>&1; then is_container=1; fi
if grep -qaE '(docker|containerd|kubepods|podman)' /proc/1/cgroup 2>/dev/null; then is_container=1; fi

if [ "$is_container" -eq 1 ]; then
  cat /etc/os-release 2>/dev/null || cat /usr/lib/os-release 2>/dev/null || true
  if grep -qiE '(pixelarch|PixelArch)' /etc/os-release /usr/lib/os-release 2>/dev/null; then
    echo "PixelArch container detected (permissive mode, full control)"
  else
    echo "Non-PixelArch container detected (high risk: ask before changes)"
  fi
else
  echo "Not in a container (high risk: ask before changes)"
fi
```

2) **Find applicable `AGENTS.md` files**
```bash
git ls-files '**/AGENTS.md' || find . -name AGENTS.md -print
```

3) **Temp outputs (required location unless requested otherwise)**
```bash
mkdir -p /tmp/agents-artifacts
```

4) **List Pull Requests**
```bash
gh pr list --json id,title,headRefName,createdAt
```
