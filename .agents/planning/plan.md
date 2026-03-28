# Build plan: Add Qwen and OpenCode agent systems

## 1) Title and objective

Objective: add two first-class agent systems, Qwen and OpenCode, across plugin discovery, Docker runtime planning, setup/login/status flows, UI selection surfaces, prompt templates, and themes, while keeping the work plugin-driven and reviewable.

This document is planning only. It makes no implementation edits, adds no tests, and does not change `README.md`.

## 2) Scope and non-goals

### In scope

- Add new plugin packages under `agents_runner/agent_systems/qwen/` and `agents_runner/agent_systems/opencode/`.
- Wire install, verify, non-interactive planning, interactive command building, setup/login/status, prompt templates, display metadata, and optional themes.
- Update UI and status surfaces so both systems appear anywhere agent systems are selected, displayed, or validated.
- Keep package/install references PixelArch-first and use `yay` when install commands are needed.

### Non-goals

- No implementation in this planning pass.
- No `README.md` updates.
- No new tests unless explicitly requested later.
- No unrelated refactors; only make narrow cleanups where hard-coded agent assumptions block Qwen/OpenCode.
- Do not change the default system from `codex` as part of this work.
- Do not broaden OpenCode persistence mounts beyond the trusted boundary described below unless runtime evidence later proves it is required.

## 3) Confirmed CLI/install naming matrix (OpenCode + Qwen)

### OpenCode

- Runtime binary: `opencode`.
- Confirmed evidence:
  - `opencode --version` works locally (`1.2.27`).
  - `opencode --help` works locally.
  - `yay -Si opencode` exists in PixelArch `extra`, version `1.2.27-1`.
- Install command to use in plugin/runtime planning: `yay -S --noconfirm --needed opencode`.
- Runtime path model from audit:
  - config: `~/.config/opencode`
  - data: `~/.local/share/opencode`
  - cache: `~/.cache/opencode`
- Mount policy: OpenCode must use a dual mount for config + data as an intentional trusted boundary. Do not collapse it to one mount, and do not mount cache by default. The goal is to preserve functionality, auth, and session continuity without widening persistence unnecessarily.

### Qwen

- Install/package corroboration:
  - `yay -Si qwen-code` exists, version `0.12.6-1`, URL `https://github.com/QwenLM/qwen-code`.
  - `yay -Si qwen` is not a valid package target.
  - `command -v qwen` succeeds in this environment while `command -v qwen-code` is absent, so the runtime binary is `qwen`.
  - `qwen --version` works and reports `0.12.6`.
  - `npm view @qwen-code/qwen-code` returns package `@qwen-code/qwen-code` and its `bin` entry is `qwen`.
- Preferred install command to use in plugin/runtime planning: `yay -S --noconfirm --needed qwen-code`.
- Runtime executable:
  - Binary: `qwen` (the `qwen-code` package installs this binary; the `qwen-code` CLI is not provided).
  - Verified by running `qwen --help` and `qwen --version`, then lock `qwen` for that environment so all setup/status checks and command generation reuse the same executable.
  - `qwen --help` lists a limited set of safe flags that overlap with Gemini; we will only converge on the confirmed ones:
    - `--approval-mode yolo`, `--include-directories`, `-i/--prompt-interactive`.
    - Prompt input is best served via the positional query argument for one-shot flows, and `-p/--prompt` should remain deprecated compatibility only.
    - Do not assume `--no-sandbox` is a default flag for Qwen; we will add it explicitly only if the runtime help output confirms it as required.
  - Current docs indicate user config at `~/.qwen/settings.json`; implementation should use `~/.qwen` as the planned default host config dir, then confirm any auth sidecar details during runtime validation.

## 4) Architecture impact map (by subsystem with file paths)

### Plugin core and discovery

- `agents_runner/agent_systems/models.py`
  - Validate whether the current plugin contract is sufficient.
  - Prefer no contract expansion unless Qwen executable locking cannot stay localized to plugin/status helpers.
- `agents_runner/agent_systems/registry.py`
  - Built-in folder discovery already exists; verify new plugin folders are auto-discovered without new registry entries.
- `agents_runner/agent_systems/__init__.py`
  - Keep exports/docstring aligned if examples or package notes need a refresh.
- New files to add:
  - `agents_runner/agent_systems/qwen/plugin.py`
  - `agents_runner/agent_systems/qwen/__init__.py`
  - `agents_runner/agent_systems/opencode/plugin.py`
  - `agents_runner/agent_systems/opencode/__init__.py`

### Install and command/runtime plumbing

- `agents_runner/agent_install.py`
  - Add install plans for Qwen and OpenCode.
  - Keep install name and runtime executable distinct where needed, especially for Qwen (`qwen-code` package vs `qwen` runtime).
- `agents_runner/agent_cli.py`
  - Ensure default config dirs, container config dirs, extra mounts, and verify clauses stay plugin-driven.
  - Confirm OpenCode additional mounts render correctly in Docker mount strings.
- `agents_runner/ui/main_window_tasks_interactive_command.py`
  - Ensure interactive command normalization and prompt injection behave correctly for Qwen/OpenCode.
- `agents_runner/ui/main_window_tasks_interactive.py`
  - Confirm plugin default command resolution and cross-agent mount assembly work with both systems.
- `agents_runner/ui/main_window_tasks_interactive_docker.py`
  - Ensure launch-time Docker mount assembly respects OpenCode dual mounts and plugin verification rules.
- `agents_runner/docker/agent_worker_setup.py`
  - Ensure runtime environment planning carries plugin mounts/install plans forward during image prep.
- `agents_runner/execution/supervisor.py`
  - Validate attempt keys, config-dir resolution, and logging remain correct for new systems.

### Setup, status, and first-run flows

- `agents_runner/setup/commands.py`
  - Expose setup/config/verify commands for Qwen and OpenCode.
- `agents_runner/setup/agent_status.py`
  - Keep the existing generic `detect_all_agents()` flow; MVP skips a dedicated `detect_qwen_status()` so Qwen rows may temporarily remain `Unknown`/unavailable in first-run and test-chain views. Document that execution is not blocked by this omission and that a future status integration will replace the placeholder state.
  - OpenCode should prefer CLI-backed provider/auth inspection and keep a clear fallback policy.
- `agents_runner/ui/dialogs/first_run_setup.py`
  - Show both systems in first-run status/setup rows with correct display names.
- `agents_runner/ui/dialogs/test_chain_dialog.py`
  - Ensure chain testing includes both systems via `detect_all_agents()` results.

### UI, settings, display, and themes

- `agents_runner/ui/pages/settings_form.py`
  - Agent picker is already plugin-driven; verify labels and theme availability once new plugins exist.
- `agents_runner/ui/pages/environments_agents.py`
  - Replace raw `agent.title()` display with plugin display names so `OpenCode` renders cleanly and future slugs stay consistent.
- `agents_runner/ui/main_window_settings.py`
  - Keep config-dir resolution and cross-agent mount generation plugin-driven for both systems.
- `agents_runner/agent_display.py`
  - Add display names and GitHub URLs for Qwen and OpenCode.
- `agents_runner/ui/graphics.py`
  - Ensure auto-theme discovery and fallback behavior pick up the new themes.
- Possible new theme directories:
  - `agents_runner/ui/themes/qwen/`
  - `agents_runner/ui/themes/opencode/`

### Prompt templates

- `agents_runner/prompts/templates/agentcli/qwen.md`
- `agents_runner/prompts/templates/agentcli/opencode.md`
- `agents_runner/docker/agent_worker_prompt.py`
  - No new logic should be needed if template filenames match plugin names, but this loader is the runtime consumer and should be part of validation.

### Secondary hard-coded reliability/display surfaces found during review

- `agents_runner/ui/widgets/agent_chain_status.py`
  - Replace raw `title()` formatting with centralized display labels.
- `agents_runner/ui/pages/new_task.py`
  - Already routes through `agent_display.py`; new mappings must be present so override menus look right.
- `agents_runner/core/agent/rate_limit.py`
  - Add Qwen/OpenCode patterns only if runtime logs show agent-specific rate-limit signals that differ from current generic handling.
- `agents_runner/execution/supervisor_errors.py`
  - Extend agent-specific failure signatures if logs show missing-command or provider-specific wording that is not already caught.

## 5) Phased implementation plan (ordered, with checkboxes)

### Shared groundwork

- [ ] Confirm the current plugin contract can stay unchanged; only add a narrow helper surface if Qwen executable locking cannot be handled inside plugin/status code.
- [ ] Note that Qwen comes from the QwenLM project and is not literally a Google Gemini model; we can reuse the Gemini plugin implementation as structural guidance but must avoid implying model-family equivalence.
- [ ] Add centralized display metadata for `qwen` and `opencode` so UI surfaces stop relying on raw slug formatting.
- [ ] Establish final planned config/mount defaults before editing runtime code:
  - Qwen: host `~/.qwen` -> container `/home/midori-ai/.qwen`.
  - OpenCode: host `~/.config/opencode` -> container `/home/midori-ai/.config/opencode` plus host `~/.local/share/opencode` -> container `/home/midori-ai/.local/share/opencode`.
- [ ] Record the explicit policy that OpenCode config + data mounts are intentional, trusted, and sufficient by default; cache is not part of the default persistence boundary.
- [ ] Verify OpenCode’s config and auth roots before coding mounts: run `opencode debug paths` (and `opencode providers list` if needed) to confirm config stays under `~/.config/opencode` and auth/data under `~/.local/share/opencode` (expect `auth.json` or similar files there).
- [ ] Add prompt template placeholders early so runtime template loading does not warn once plugins are discoverable.

### Qwen track

- [ ] Create `agents_runner/agent_systems/qwen/__init__.py` and `agents_runner/agent_systems/qwen/plugin.py`.
- [ ] Set Qwen install command to `yay -S --noconfirm --needed qwen-code` and keep package naming separated from runtime executable selection.
- [ ] Implement Qwen executable verification by running `qwen --version` and `qwen --help`, then lock `qwen` for that environment so all setup/status checks and command generation reuse the verified binary.
- [ ] Implement Qwen non-interactive planning around documented headless mode while only including flags confirmed by `qwen --help` (currently `--approval-mode yolo`, `--include-directories`, `-i/--prompt-interactive`, and the positional query argument for one-shot flows), and explicitly avoid assuming `--no-sandbox` or other undocumented defaults.
- [ ] Implement Qwen interactive command building from actual help output once available in the target environment; include workspace and prompt handling only for flags confirmed by runtime help.
- [ ] Add `agents_runner/prompts/templates/agentcli/qwen.md` with Qwen-specific guidance.
- [ ] Add Qwen setup/verify/status integration in `agents_runner/setup/commands.py`, the existing `detect_all_agents()` flow within `agents_runner/setup/agent_status.py`, `agents_runner/ui/dialogs/first_run_setup.py`, and `agents_runner/ui/dialogs/test_chain_dialog.py`.
- [ ] Use `StatusType.UNKNOWN` rather than a false negative when Qwen auth evidence is incomplete, and document that Qwen status rows in first-run/test-chain may show `Unknown`/unavailable until a dedicated detection helper replaces the placeholder.

### OpenCode track

- [ ] Create `agents_runner/agent_systems/opencode/__init__.py` and `agents_runner/agent_systems/opencode/plugin.py`.
- [ ] Set OpenCode install command to `yay -S --noconfirm --needed opencode` and verify with `opencode --version`.
- [ ] Implement OpenCode non-interactive planning around `opencode run` and interactive planning around `opencode [project]` plus prompt support validated by local help output.
- [ ] Document that the CLI flow (`opencode run ...`) is considered janky and unsupported compared to OpenCode’s preferred TUI/WebUI modes, and keep that disclaimer visible whenever we mention CLI execution plans.
- [ ] Implement OpenCode `additional_config_mounts()` so Docker always mounts both config and data roots as RW, while leaving cache unmapped by default.
- [ ] Add OpenCode setup/config/status commands centered on:
  - setup/login: `opencode providers login`
  - verify: `opencode --version`
  - config/debug: `opencode providers list` and `opencode debug paths` / `opencode debug config`
- [ ] Add `agents_runner/prompts/templates/agentcli/opencode.md` so OpenCode can participate cleanly in normal and cross-agent prompt assembly.
- [ ] Add OpenCode status detection that prefers `opencode providers list` and falls back to `~/.local/share/opencode/auth.json` or equivalent data-root evidence only when CLI parsing is insufficient.

### Cross-cutting UI/setup/status/prompt/theme tasks

- [ ] Update display/UI consumers so both systems render with stable display names in settings, environment agent pickers, override menus, first-run setup, and chain status widgets.
- [ ] Add `agents_runner/ui/themes/qwen/` and `agents_runner/ui/themes/opencode/` and set plugin `ui_theme` values to match.
- [ ] Validate that `agents_runner/ui/graphics.py` discovers both themes and that auto-theme sync follows the selected active agent.
- [ ] Validate cross-agent mount behavior so OpenCode dual mounts and any Qwen config overrides still deduplicate correctly in interactive and non-interactive launches.
- [ ] Confirm prompt templates load for primary-agent and allowlisted cross-agent scenarios without warning spam from `agents_runner/docker/agent_worker_prompt.py`.
- [ ] Audit secondary hard-coded reliability files (`agents_runner/core/agent/rate_limit.py`, `agents_runner/execution/supervisor_errors.py`) after first live runs and extend only if logs show gaps.

## 6) Acceptance criteria per phase

### Shared groundwork acceptance

- New plugin folders are discoverable without adding manual registry entries.
- UI display paths can show `Qwen` and `OpenCode` consistently instead of raw slug formatting.
- The OpenCode dual mount policy is explicit: config + data are mounted, cache is not.
- The Qwen executable verification procedure is explicit and reusable: run `qwen --version` and `qwen --help`, then lock the verified `qwen` binary for that environment.
- Config and auth folders are confirmed: OpenCode config stays in `~/.config/opencode` and auth/data reside in `~/.local/share/opencode` (expecting `auth.json` or similar provider data), which we verify by running `opencode providers list`/`opencode debug paths` before coding mounts.

### Qwen acceptance

- `qwen` appears anywhere agent systems are selected or displayed.
- Qwen install references use `qwen-code` and never rely on a nonexistent `qwen` package.
- Qwen host-side setup/status logic uses `qwen --version` and `qwen --help` for authoritative runtime checks and keeps `qwen` locked as the executable.
- Qwen runtime planning is Qwen-specific, not a blind Gemini clone; only `--approval-mode yolo`, `--include-directories`, `-i/--prompt-interactive`, and the positional query argument are adopted from the confirmed help output, and `-p/--prompt` remains compatibility-only.
- Qwen prompt template exists and loads without warnings.
- Qwen appears in first-run setup and test-chain status flows with a documented installed/logged-in/unknown policy, explicitly noting that MVP status rows may initially show `Unknown`/unavailable.

### OpenCode acceptance

- `opencode` appears anywhere agent systems are selected or displayed.
- OpenCode install references use `yay -S --noconfirm --needed opencode`.
- Non-interactive and interactive planning use documented OpenCode commands rather than generic shell wrappers.
- Docker launches mount both `~/.config/opencode` and `~/.local/share/opencode` as the default trusted persistence boundary.
- OpenCode setup/status flows can launch provider login and detect whether credentials/providers are configured.
- OpenCode prompt template exists and loads without warnings.

### Cross-cutting acceptance

- Settings/theme UI can discover and render Qwen/OpenCode themes.
- Environment agent add/select flows show correct display names.
- First-run setup, test-chain status, new-task override menus, and PR/summary displays show friendly labels and links.
- Cross-agent mount de-duplication still works when OpenCode contributes extra mounts.
- Existing agents continue to behave as before.

## 7) Validation checklist (commands/manual checks; no new tests)

### Repo-wide validation after implementation

```bash
uv sync --group ci
uv run ruff format .
uv run ruff check .
uv run basedpyright
```

Do not add or run new tests unless they are explicitly requested later.

### Runtime evidence checks

```bash
opencode --version
opencode --help
opencode run --help
opencode providers --help
opencode debug paths
yay -Si opencode
yay -Si qwen-code
npm view @qwen-code/qwen-code bin repository.url homepage
qwen --version
qwen --help
```

### Manual product checks

- Launch `uv run main.py`.
- Settings page:
  - `Qwen` and `OpenCode` appear in the default agent picker.
  - Their themes appear in theme previews if theme dirs are added.
- Environments page:
  - Add-agent dropdown shows friendly display names, not raw slug casing.
  - Per-agent config override fields accept plugin defaults cleanly.
- First-run setup and Test Chain:
  - Both systems appear in status rows.
  - Status text is sensible for installed, not installed, and low-confidence auth cases.
- Non-interactive runs:
  - Qwen plans the documented headless command.
  - OpenCode plans `opencode run`.
- Interactive runs:
  - Qwen and OpenCode launch with plugin default commands.
  - OpenCode container sees both config and data mounts.
- Prompt loading:
  - No warnings for missing `templates/agentcli/qwen` or `templates/agentcli/opencode`.

## 8) Risk register + mitigations

| Risk | Why it matters | Mitigation |
| --- | --- | --- |
| Qwen runtime binary drift (`qwen` vs `qwen-code`) | Host setup/status commands can fail even when Qwen is installed | Verify the `qwen` binary with `qwen --version` / `qwen --help` and lock that executable per environment so setup/status checks do not target the wrong name |
| Qwen package vs runtime name mismatch | Install can succeed while runtime verification still checks the wrong name | Keep install package (`qwen-code`) separate from runtime executable selection and validate both paths explicitly |
| Qwen auth detection uncertainty | False negatives in first-run/setup UX create bad guidance | Prefer `UNKNOWN` when only partial evidence exists; only report logged-in on confirmed signals |
| OpenCode single-mount simplification | Auth/session behavior can break if only config is mounted | Treat config + data as the default trusted mount boundary and validate both mounts in Docker launches |
| OpenCode over-mounting | Mounting cache/state without evidence widens persistence and review surface | Keep cache out of the default policy; add more only if runtime evidence proves it is required |
| UI label drift | Raw slug formatting makes new agents look unfinished and inconsistent | Route labels through `display_name` / `agent_display.py` and audit `title()` / `capitalize()` call sites |
| Missing templates or themes | New systems may load with warnings or fall back to generic visuals | Add prompt templates before enabling plugins and add matching theme directories if `ui_theme` is declared |
| Reliability pattern gaps | Retry/cooldown logic may misclassify new vendor errors | Review first live logs and extend `rate_limit.py` / `supervisor_errors.py` only where evidence shows gaps |

## 9) Dependency/issue sequencing map

1. Use `#54` as the Qwen umbrella issue.
2. Land the Qwen plugin/template/runtime work under `#204` first, because setup/status and UI value depend on the plugin existing.
3. Land Qwen setup/login/status work under `#205` after or alongside `#204`, once commands and config defaults are stable enough to expose in UI.
4. Treat closed `#206` as background context only: it already pushed the repo toward plugin-driven config handling, so new Qwen/OpenCode work should reuse that direction rather than reintroduce per-agent hard-coded settings keys.
5. Treat closed `#207` as historical context, not a source of truth, because its package assumption (`qwen-code-bin`) is stale relative to current verified PixelArch package info (`qwen-code`).
6. OpenCode currently has no equivalent issue structure. Create one before implementation if maintainers want parity with Qwen tracking:
   - Parent issue: implement OpenCode agent system.
   - Child issue A: strict OpenCode plugin + prompt/template + runtime/mount integration.
   - Child issue B: OpenCode setup/login/status integration.
7. Recommended implementation order:
   - Shared groundwork
   - Qwen plugin/runtime/template (`#204`)
   - OpenCode plugin/runtime/template (new child issue A)
   - Qwen setup/status (`#205`)
   - OpenCode setup/status (new child issue B)
   - Cross-cutting UI/theme/reliability sweep

## 10) Decision log (locked)

- D1 – Qwen login-status detection for MVP is intentionally limited to the existing `detect_all_agents()` flow. No explicit `detect_qwen_status()` is planned for MVP, so first-run/test-chain rows can show `Unknown`/unavailable, but execution is not blocked and future work will replace the placeholder state when reliable signals emerge.
- D2 – Qwen runtime flags only align with the documented `qwen --help` output. We adopt the confirmed overlaps (`--approval-mode yolo`, `--include-directories`, `-i/--prompt-interactive`, and the positional prompt argument), treat `-p/--prompt` as deprecated compatibility, and explicitly avoid assuming undocumented defaults such as `--no-sandbox`.
