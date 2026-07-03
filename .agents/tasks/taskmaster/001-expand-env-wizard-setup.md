# Replace 2-step wizard with 5-page left-nav + right-pane layout

## File to modify

`agents_runner/ui/dialogs/new_environment_wizard.py` (501 lines, complete rewrite)

## Architecture

Replace the current 2-step QStackedWidget wizard (`_step1_widget` / `_step2_widget`) with a left-navigation + right-pane layout matching the Environments/Settings pages pattern. Keep ThemedDialog base. Nav buttons allow free jumping between pages.

Layout (inside `self.content_layout()`):

```
┌─────────────────────────────────────────────────────────┐
│ GlassCard                                               │
│ ┌─ Left nav (EdgeFadeScrollArea, 280px) ─┬─ Right ───┐ │
│ │                                        │            │ │
│ │ [General Info]         ◄ nav button    │ QStacked   │ │
│ │ [Runtime & Agents]     ◄ nav button    │ Widget     │ │
│ │ [Desktop & Cache]      ◄ nav button    │ (pages)    │ │
│ │ [GitHub Behavior]      ◄ nav button    │            │ │
│ │ [AgentsNova Automation] ◄ nav button    │            │ │
│ │                                        │            │ │
│ └────────────────────────────────────────┴────────────┘ │
│                                                        │
│ ─────────────────── shared bottom bar ─────────────── │
│              [Cancel]  [Back]  [Next / Finish / Skip]    │
└─────────────────────────────────────────────────────────┘
```

## 5 Pages

Each page gets its own QWidget in the QStackedWidget, wrapped in an EdgeFadeScrollArea (use a `_create_wizard_page(title, subtitle)` helper matching `environments_form.py:583-610` `_create_page` pattern).

### Page 1: General Info

Same content as current `_setup_step1()` (lines 79-187), plus the color combo moved here from old step 2:

- Environment Name QLineEdit (with tooltip: `"A label you'll recognize later (e.g., 'My Repo (Remote)')"`)
- Workspace Source Type QComboBox (folder / clone, with tooltip: `"Both run in a container; this only changes the workspace source"`)
- Folder Path QLineEdit + Browse button (visible when folder selected)
  - Validation label (✓/✗) with `_validate_folder()` logic (lines 283-306, keep as-is)
- Repository URL QLineEdit (visible when clone selected)
  - Validation label (✓/✗) with `_validate_clone()` logic (lines 320-339, keep as-is)
- Color QComboBox (populated from `ALLOWED_STAINS`, with tint application via `currentIndexChanged`)
  - Tooltip: `"Used for identifying environments in the UI"`
- Warning label (lines 163-170): `"⚠ Step 1 choices (workspace source + path/URL) cannot be edited later. To change them, create a new environment."`

### Page 2: Runtime & Agents (all new)

Controls:

- **GPU runtime override** (QComboBox)
  - Items: "Inherit global setting"→`"inherit"`, "Enabled"→`"enabled"`, "Disabled"→`"disabled"`
  - Import: `GPU_OVERRIDE_MODES` from `agents_runner.environments.model` (lines 84-91)
  - Tooltip: `"Override the global GPU runtime setting for this environment."` (from environments_form.py:157)

- **OpenCode interactive mode** (QComboBox)
  - Items: "Inherit global setting"→`"inherit"`, "Terminal"→`"terminal"`, "Web"→`"web"`, "Ask"→`"ask"`
  - Import: `OPENCODE_INTERACTIVE_OVERRIDE_MODES` from model.py (lines 101-107)
  - Tooltip: `"Override the global OpenCode Run Interactive launch mode."` (from environments_form.py:163)

- **Max agents running** (QLineEdit + `QIntValidator(-1, 10_000_000)`)
  - Placeholder: `"-1"`
  - Tooltip: `"Maximum agents running at the same time for this environment. Set to -1 for no limit.\nTip: For local-folder workspaces, set this to 1 to avoid agents fighting over setup/files."` (from environments_form.py:140-143)
  - Set `setMaximumWidth(150)` like environments_form.py:145

- **Use cross agents** (QCheckBox)
  - Label: `"Use cross agents"`
  - Tooltip: `"When enabled, allows agent instances from the Agents pane to be mounted\nas cross-agents in task containers. Configure the allowlist in the Agents pane."` (from environments_form.py:182-185)

### Page 3: Desktop & Cache (existing + new)

Controls:

- **Enable headless desktop** (QCheckBox, moved from old step 2)
  - Tooltip: `"When enabled, agent runs for this environment will start a noVNC desktop.\nSettings → Force headless desktop overrides this setting."` (from environments_form.py:148-151)

- **Cache desktop build** (QCheckBox, new)
  - Tooltip: `"When enabled, desktop components are pre-installed in a cached Docker image.\nThis reduces task startup time from 45-90s to 2-5s.\nRequires 'Enable headless desktop' to be enabled.\n\nImage is automatically rebuilt when scripts change."` (from environments_form.py:166-171)
  - **Visibility:** enabled only when headless desktop is checked → wire `_headless_desktop_enabled.toggled` to enable/disable + uncheck this when headless is off

- **Cache system preflight** (QCheckBox, new)
  - Tooltip: `"When enabled, the system preflight (pixelarch_yay.sh) is cached as an image layer."` (from environments_form.py:331-333)
  - Initially disabled, enabled when container caching is on

- **Cache settings preflight** (QCheckBox, new)
  - Tooltip: `"When enabled, the Settings preflight script is cached as an image layer."` (from environments_form.py:337-339)
  - Initially disabled, enabled when container caching is on

- **Enable container caching** (QCheckBox, moved from old step 2)
  - Tooltip: `"When enabled, selected preflight phases build cached Docker layers.\nConfigure phase cache toggles in the Caching pane."` (from environments_form.py:175-178)
  - When toggled on: enable `cache_system_preflight_enabled` and `cache_settings_preflight_enabled`
  - When toggled off: disable + uncheck those two sub-phase checkboxes
  - Pattern: `environments.py:607-613` `_on_container_caching_toggled`

### Page 4: GitHub Behavior (all new)

Controls:

- **Enable GitHub context** (QCheckBox, moved from old step 2)
  - Tooltip: `"When enabled, repository context (URL, branch, commit) is provided to the agent.\nFor GitHub-managed environments: Always available.\nFor folder-managed environments: Only if folder is a git repository.\n\nNote: This does NOT provide GitHub authentication - that is separate."` (from environments_form.py:189-194)

- **Branch workflow mode** (QComboBox)
  - Items: "Use task branches"→`"task_branch"`, "Work on direct base"→`"direct_base"`
  - Import: `GH_BRANCH_WORK_MODES` from model.py (lines 52-57)
  - Tooltip: `"Controls whether GitHub work for this environment uses per-task branches or works directly on the selected base branch."` (from environments_form.py:261-263)

- **Task branch naming style** (QComboBox)
  - Items: Standard→`"standard"`, Songs→`"songs"`, Foods→`"foods"`, Animals→`"animals"`, Colors→`"colors"`, Space→`"space"`, Custom→`"custom"`
  - Import: `GH_TASK_BRANCH_NAMING_STYLES` from model.py (lines 59-74)
  - Tooltip: `"Controls how future task branches are named for this environment."` (from environments_form.py:272-274)

- **Custom branch template** (QLineEdit, visible only when naming style is "custom")
  - Placeholder: `GH_TASK_BRANCH_CUSTOM_TEMPLATE_DEFAULT` = `"{task_id}"` (model.py:75)
  - Tooltip: `"Custom template used when task branch naming style is set to Custom."` (from environments_form.py:277-279)
  - Add a helper QLabel: `"Custom templates can use placeholders like {task_id}."` with ObjectName `"SettingsPaneSubtitle"` (from environments_form.py:280-282)
  - Visibility wired to `_gh_task_branch_naming_style.currentIndexChanged`

- **Show interactive PR prompt** (QCheckBox)
  - Tooltip: `"When enabled, interactive GitHub work can keep showing the PR prompt for this environment."` (from environments_form.py:232-234)

- **PR no-prompt mode** (QComboBox, visible only when PR prompt is unchecked)
  - Items: "Auto-create PR after interactive run"→`INTERACTIVE_PR_NO_PROMPT_MODE_AUTO_CREATE` (`"auto_create_pr"`), "Manual only (Review -> Create PR)"→`INTERACTIVE_PR_NO_PROMPT_MODE_MANUAL_REVIEW` (`"manual_via_review_menu"`)
  - Import: `INTERACTIVE_PR_NO_PROMPT_MODES` from model.py (lines 77-82)
  - Tooltip: `"Used when 'Show interactive PR prompt' is disabled.\nManual mode means you can enter the task, then click Review -> Create PR yourself."` (from environments_form.py:244-247)
  - Visibility wired to `_interactive_pr_prompt_enabled.toggled`

### Page 5: AgentsNova Automation (all new)

Controls:

- **Auto review mode** (QComboBox)
  - Items: "Inherit global setting"→`"inherit"`, "Enabled"→`"enabled"`, "Disabled"→`"disabled"`
  - Import: `AGENTSNOVA_AUTO_MODES` from model.py (lines 32-39)
  - Tooltip: `"Override whether @agentsnova mentions auto-queue review work for this environment."` (from environments_form.py:213-215)

- **Auto reactions mode** (QComboBox)
  - Items: "Inherit global setting"→`"inherit"`, "Enabled"→`"enabled"`, "Disabled"→`"disabled"`
  - Import: `AGENTSNOVA_AUTO_MODES` (same set, reuse)
  - Tooltip: `"Override whether @agentsnova queue triggers add GitHub reactions for this environment."` (from environments_form.py:220-222)

- **Marker comment mode** (QComboBox)
  - Items: "Inherit global setting"→`"inherit"`, "Keep"→`"keep"`, "Delete after 15s"→`"delete_after_15s"`, "Disabled"→`"disabled"`
  - Import: `AGENTSNOVA_MARKER_COMMENT_MODES` from model.py (lines 41-50)
  - Tooltip: `"Override marker-comment behavior for @agentsnova auto-review activity in this environment."` (from environments_form.py:228-230)

## Shared bottom button bar

One button bar (not per-page) at the bottom of the content layout, below the GlassCard:

- **Cancel** — calls `self.reject()`
- **Back** — disabled on page 0, enabled otherwise; navigates to previous page by index
- **Next** — on pages 0-3 shows "Next", on page 4 (last) shows "Finish" / "Skip" (based on `_advanced_modified`)

Button label rules:
- Page 0 (General Info): "Next" text, enabled only when `_validate_step1()` returns True (clone test logic preserved — shows "Test" when cloning and test not yet passed)
- Pages 1-3: "Next", always enabled
- Page 4 (last): toggles between "Skip" (when `_advanced_modified` is False) and "OK" (when `_advanced_modified` is True). Clicking always calls `_on_finish()` which creates the environment.

Any combo/checkbox change on pages 2-5 (i.e., non-step-1 pages) must set `_advanced_modified = True` and update the finish button label to "OK".

## Navigation logic

- Left nav buttons: QToolButton, checkable, autoExclusive, `setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)`, `setFixedHeight(40)`, `setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)`
  - ObjectName: `"SettingsNavButton"` (matches environments styling)
- Clicking any nav button sets the QStackedWidget current index to that page
- Back/Next buttons navigate sequentially; they update which nav button is checked
- Use nav panel wrapped in EdgeFadeScrollArea with ObjectName `"SettingsNavScrollArea"` and `setFixedWidth(LEFT_NAV_PANEL_WIDTH)` (280px from constants.py:21)
- Right side QStackedWidget set ObjectName `"SettingsPageStack"`

## `_create_environment()` update

A new `_collect_wizard_data()` method should gather all values from new controls. Update `_create_environment()` (lines 460-493) to pass all new fields to `Environment(...)`:

```python
Environment(
    env_id=env_id,
    name=name,
    color=color,
    gh_management_locked=True,
    workspace_type=workspace_type,
    workspace_target=gh_target,
    # Existing fields (keep these)
    headless_desktop_enabled=self._headless_desktop_enabled.isChecked(),
    container_caching_enabled=self._container_caching_enabled.isChecked(),
    gh_context_enabled=self._gh_context_enabled.isChecked(),
    agentsnova_auto_review_mode=self._auto_review_combo.currentData(),
    agentsnova_auto_reactions_mode=self._auto_reactions_combo.currentData(),
    agentsnova_marker_comment_mode=self._marker_comment_combo.currentData(),
    interactive_pr_prompt_enabled=self._interactive_pr_prompt_enabled.isChecked(),
    interactive_pr_no_prompt_mode=self._interactive_pr_no_prompt_mode.currentData(),
    # New fields (add these)
    gpu_override_mode=self._gpu_override_combo.currentData(),        # default: "inherit"
    opencode_interactive_mode=self._opencode_interactive_combo.currentData(),  # default: "inherit"
    max_agents_running=int(self._max_agents_running.text() or "-1"),  # default: -1
    use_cross_agents=self._use_cross_agents.isChecked(),              # default: False
    cache_desktop_build=self._cache_desktop_build.isChecked(),        # default: False
    cache_system_preflight_enabled=self._cache_system_preflight_enabled.isChecked(),  # default: False
    cache_settings_preflight_enabled=self._cache_settings_preflight_enabled.isChecked(),  # default: False
    gh_branch_work_mode=self._gh_branch_work_mode.currentData(),      # default: "task_branch"
    gh_task_branch_naming_style=self._gh_task_branch_naming_style.currentData(),  # default: "standard"
    gh_task_branch_custom_template=self._gh_task_branch_custom_template.text().strip() or GH_TASK_BRANCH_CUSTOM_TEMPLATE_DEFAULT,
)
```

## Standard imports to add (from model.py)

```python
from agents_runner.environments.model import (
    AGENTSNOVA_AUTO_MODES,
    AGENTSNOVA_MARKER_COMMENT_MODES,
    GH_BRANCH_WORK_MODES,
    GH_TASK_BRANCH_NAMING_STYLES,
    GH_TASK_BRANCH_CUSTOM_TEMPLATE_DEFAULT,
    GPU_OVERRIDE_MODES,
    INTERACTIVE_PR_NO_PROMPT_MODES,
    INTERACTIVE_PR_NO_PROMPT_MODE_AUTO_CREATE,
    INTERACTIVE_PR_NO_PROMPT_MODE_MANUAL_REVIEW,
    OPENCODE_INTERACTIVE_OVERRIDE_MODES,
)
```

## Preserved behaviors (must keep)

- `ThemedDialog` base class (init, content_layout, theme support)
- `EnvironmentTintOverlay` with `resizeEvent` tracking
- `_pick_new_environment_color()` (lines 495-501)
- `_apply_environment_tint()` + `_current_stain()` (lines 251-265)
- Clone test workflow: `_expand_repo_url`, `_validate_clone`, `_run_clone_test`, `_check_clone_result` (lines 308-432)
- Folder validation: `_validate_folder`, `_browse_folder` (lines 278-306)
- `_on_source_changed` (lines 267-276)
- `_update_next_button` (lines 341-353) — adapt to work with the shared button bar
- `_validate_step1` (lines 355-370)
- `_on_cancel` (line 437-438) — reject
- `_on_finish` (lines 448-458) — create env, save, delete default, emit signal, accept
- `environment_created = Signal(object)` signal
- Default-env-delete logic after creating first env (lines 452-455)
- `_advanced_modified` toggle affecting the finish button label

## Dependent visibility wiring

| Parent control | Page | Child control | Rule |
|---|---|---|---|
| `_headless_desktop_enabled` (QCheckBox) | 3 | `_cache_desktop_build` (QCheckBox) | Enable on check; disable + uncheck on uncheck |
| `_container_caching_enabled` (QCheckBox) | 3 | `_cache_system_preflight_enabled`, `_cache_settings_preflight_enabled` | Enable on check; disable + uncheck on uncheck |
| `_gh_task_branch_naming_style` (QComboBox) | 4 | `_gh_task_branch_custom_template` (QLineEdit) + helper label | Show when currentData == "custom", hide otherwise |
| `_interactive_pr_prompt_enabled` (QCheckBox) | 4 | `_interactive_pr_no_prompt_mode` (QComboBox) | Show when unchecked, hide when checked |

## Dialog sizing

Set in `__init__`:
```python
self.setMinimumWidth(900)
self.setMinimumHeight(620)
```

## Dead code to remove

After migration is complete, remove:
- `_setup_step1()` method (lines 79-187) — replaced by page 1 build
- `_setup_step2()` method (lines 189-249) — replaced by pages 2-5 build
- `_step1_widget`, `_step2_widget`, `_on_back`, `_cancel_btn2`, `_back_btn2`, `_finish_btn` (old per-page button references)
- Old `_on_next` (lines 372-378) — replaced by new nav-aware next handler
- Old `_on_back` (lines 434-435) — replaced by new nav-aware back handler

## Implementation order

1. Skeleton: define 5 pane specs (key/title/subtitle), build left nav panel (EdgeFadeScrollArea + QToolButtons), build right QStackedWidget, build shared bottom button bar, implement page navigation (setCurrentIndex, Back/Next handlers), write `_create_wizard_page(title, subtitle)` helper
2. Build page 1: migrate step 1 content + color combo from old step 2 into the new `_create_wizard_page` layout
3. Build page 2 (Runtime & Agents): all new controls with tooltips
4. Build page 3 (Desktop & Cache): existing checkboxes + new sub-phase checkboxes with dependency wiring
5. Build page 4 (GitHub Behavior): all new controls with dependency wiring
6. Build page 5 (AgentsNova Automation): all new controls with tooltips
7. Update `_create_environment()` with new fields
8. Wire all dependent visibility signals + `_advanced_modified` tracking on pages 2-5
9. Remove dead code (old `_setup_step1`, `_setup_step2`, old button references, old `_on_next`, old `_on_back`)
10. Format with `uv run ruff format .`, lint with `uv run ruff check .`, type-check with `uv run basedpyright`

## Reference files

- Current wizard: `new_environment_wizard.py` (501 lines)
- Environment model/constants: `agents_runner/environments/model.py` (307 lines, key lines: 32-107)
- Form patterns / tooltips: `agents_runner/ui/pages/environments_form.py` (646 lines, key lines: 131-611)
- Page layout pattern: `agents_runner/ui/pages/environments.py` (735 lines, key lines: 153-186, 553-614)
- ThemedDialog base: `agents_runner/ui/dialogs/themed_dialog.py` (105 lines, key line: 98 `content_layout()`)
- UI constants: `agents_runner/ui/constants.py` (key lines: 21 `LEFT_NAV_PANEL_WIDTH = 280`)

## Completion Note

Implemented the 5-page left-navigation wizard, wired new runtime/cache/GitHub/AgentsNova controls into environment creation, preserved validation and clone-test workflows, and moved this task to done.
