from __future__ import annotations

import threading

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QObject
from PySide6.QtCore import QEvent, QSignalBlocker, QTimer, Qt, Signal
from PySide6.QtGui import QIntValidator, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QCheckBox
from PySide6.QtWidgets import QComboBox
from PySide6.QtWidgets import QDoubleSpinBox
from PySide6.QtWidgets import QGridLayout
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QLineEdit
from PySide6.QtWidgets import QDialog
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QListWidget
from PySide6.QtWidgets import QListWidgetItem
from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QSlider
from PySide6.QtWidgets import QSpinBox
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.agent_cli import normalize_agent
from agents_runner.agent_configs.model import AgentConfig
from agents_runner.agent_configs.storage import delete_agent_config
from agents_runner.agent_configs.storage import find_envs_referencing_config
from agents_runner.agent_configs.storage import load_agent_configs
from agents_runner.agent_configs.storage import save_agent_config
from agents_runner.agent_labels import format_agent_ui_label
from agents_runner.agent_systems import available_agent_system_names
from agents_runner.agent_systems import get_default_agent_system_name
from agents_runner.environments import load_environments
from agents_runner.environments import normalize_opencode_interactive_mode
from agents_runner.environments.task_workspaces import (
    TASK_WORKSPACE_LOCATION_APP_DATA,
)
from agents_runner.environments.task_workspaces import (
    SCRATCH_TASK_WORKSPACES_ROOT,
)
from agents_runner.environments.task_workspaces import (
    ScratchDriveStatus,
)
from agents_runner.environments.task_workspaces import (
    TASK_WORKSPACE_LOCATION_SCRATCH_DRIVE,
)
from agents_runner.environments.task_workspaces import normalize_task_workspace_location
from agents_runner.environments.task_workspaces import scratch_drive_status
from agents_runner.terminal_apps import detect_terminal_options
from agents_runner.ui.pages.github_trust import (
    collect_seed_usernames_for_cloned_environments,
)
from agents_runner.ui.pages.github_username_list import GitHubUsernameListWidget
from agents_runner.ui.radio import RadioController
from agents_runner.ui.dialogs.agent_config_dialog import AgentConfigDialog
from agents_runner.cli import get_opencode_cli_overrides
from agents_runner.ui.dialogs.theme_preview_dialog import ThemePreviewDialog
from agents_runner.ui.graphics import available_ui_theme_names
from agents_runner.ui.graphics import normalize_ui_theme_name
from agents_runner.ui.widgets import EdgeFadeScrollArea
from agents_runner.ui.widgets import ArcSpinner
from agents_runner.ui.widgets.artifact_highlighter import ArtifactSyntaxHighlighter
from agents_runner.ui.widgets.theme_preview import ThemePreviewTile
from agents_runner.ui.constants import (
    GRID_HORIZONTAL_SPACING,
    GRID_VERTICAL_SPACING,
    BUTTON_ROW_SPACING,
)
from agents_runner.ui.utils.form_helpers import (
    add_grid_row,
    configure_form_grid,
    create_stretch_row,
)
from agents_runner.gh.automation_policy import normalize_default_marker_comment_mode
from agents_runner.persistence import default_state_path


@dataclass(frozen=True)
class _SettingsPaneSpec:
    key: str
    title: str
    subtitle: str
    section: str


class _WorkspaceStatusWorker(QObject):
    finished = Signal(int, object)

    def __init__(self, request_id: int) -> None:
        super().__init__()
        self._request_id = int(request_id)

    def start(self) -> None:
        threading.Thread(target=self.run, daemon=True).start()

    def run(self) -> None:
        try:
            status = scratch_drive_status()
        except Exception as exc:
            status = ScratchDriveStatus(
                path=SCRATCH_TASK_WORKSPACES_ROOT,
                exists_or_creatable=False,
                is_ram_drive=False,
                free_bytes=0,
                free_gib=0.0,
                has_recommended_space=False,
                warnings=(f"Scratch drive could not be checked: {exc}",),
            )
        self.finished.emit(self._request_id, status)


class SettingsFormMixin:
    _PREFLIGHT_PRESETS_DIRNAME = "preflight-scripts"
    _PREFLIGHT_PRESET_SUFFIXES = {".sh", ".bash", ".zsh"}

    # Class-level type annotations for attributes set by SettingsPage mixin host
    _queue_debounced_autosave: Any
    _compact_nav: Any
    _on_nav_button_clicked: Any
    _nav_buttons: Any
    _page_stack: Any
    _pane_index_by_key: Any
    _pane_specs: Any
    _on_test_preflight: Any
    move_task_workspaces_requested: Any

    def _default_pane_specs(self) -> list[_SettingsPaneSpec]:
        specs = [
            _SettingsPaneSpec(
                key="general_preferences",
                title="General Preferences",
                subtitle="Global editor and default behavior toggles.",
                section="General",
            ),
            _SettingsPaneSpec(
                key="storage",
                title="Storage",
                subtitle="Local task workspace storage and migration.",
                section="General",
            ),
            _SettingsPaneSpec(
                key="cleanup",
                title="Cleanup",
                subtitle="Finished workspace retention and scan cadence.",
                section="General",
            ),
            _SettingsPaneSpec(
                key="themes",
                title="Themes",
                subtitle="Background theme behavior and overrides.",
                section="Appearance",
            ),
            _SettingsPaneSpec(
                key="agent_defaults",
                title="Agent Defaults",
                subtitle="Default agent and shell behavior.",
                section="Agent Setup",
            ),
            _SettingsPaneSpec(
                key="agent_configs",
                title="Agent Configs",
                subtitle="Named agent configurations shared across environments.",
                section="Agent Setup",
            ),
            _SettingsPaneSpec(
                key="github_config",
                title="Config",
                subtitle="GitHub polling, auto-review, and write confirmation controls.",
                section="GitHub",
            ),
            _SettingsPaneSpec(
                key="github_trusted_users",
                title="Trusted Users",
                subtitle="Global trusted usernames for @agentsnova auto-review checks.",
                section="GitHub",
            ),
            _SettingsPaneSpec(
                key="runtime_behavior",
                title="Runtime Behavior",
                subtitle="Container and desktop runtime toggles.",
                section="Runtime",
            ),
            _SettingsPaneSpec(
                key="preflight_script",
                title="Preflight Script",
                subtitle="Global setup script executed before setup-agents.sh.",
                section="Runtime",
            ),
        ]
        if bool(getattr(self, "_radio_supported", True)):
            specs.append(
                _SettingsPaneSpec(
                    key="radio",
                    title="Radio",
                    subtitle="Midori AI Radio playback controls and defaults.",
                    section="Runtime",
                )
            )
        return specs

    def _build_controls(self) -> None:
        self._use = QComboBox()
        self._populate_agent_combo()

        self._shell = QComboBox()
        for label, value in [
            ("bash", "bash"),
            ("sh", "sh"),
            ("zsh", "zsh"),
            ("fish", "fish"),
            ("tmux", "tmux"),
        ]:
            self._shell.addItem(label, value)

        self._interactive_terminal = QComboBox()
        self._interactive_terminal.setToolTip("Default terminal used by Run Interactive and Get Agent Help.")
        self._refresh_terminal_options(selected_terminal_id="")

        self._refresh_interactive_terminal = QToolButton()
        self._refresh_interactive_terminal.setText("Refresh")
        self._refresh_interactive_terminal.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._refresh_interactive_terminal.clicked.connect(self._on_refresh_terminal_options_clicked)

        self._opencode_interactive_mode = QComboBox()
        self._opencode_interactive_mode.addItem("Terminal", "terminal")
        self._opencode_interactive_mode.addItem("Web", "web")
        self._opencode_interactive_mode.addItem("Ask", "ask")
        self._opencode_interactive_mode.setToolTip("Default OpenCode launch mode for Run Interactive.")

        self._agent_configs: list[AgentConfig] = []
        self._agent_configs_by_id: dict[str, AgentConfig] = {}
        self._agent_configs_list = QListWidget()
        self._agent_configs_list.setToolTip("Saved agent configurations.")
        self._agent_configs_list.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._agent_configs_list.currentRowChanged.connect(lambda _row=0: self._sync_agent_configs_actions())
        self._agent_configs_list.itemDoubleClicked.connect(lambda _item=None: self._on_agent_configs_edit_clicked())
        self._agent_configs_list.setStyleSheet(
            "QListWidget::item:selected { background-color: rgba(148, 163, 184, 50); }"
        )

        self._agent_configs_add = QToolButton()
        self._agent_configs_add.setText("Add")
        self._agent_configs_add.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._agent_configs_add.clicked.connect(self._on_agent_configs_add_clicked)

        self._agent_configs_edit = QToolButton()
        self._agent_configs_edit.setText("Edit")
        self._agent_configs_edit.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._agent_configs_edit.clicked.connect(self._on_agent_configs_edit_clicked)

        self._agent_configs_delete = QToolButton()
        self._agent_configs_delete.setText("Delete")
        self._agent_configs_delete.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._agent_configs_delete.clicked.connect(self._on_agent_configs_delete_clicked)
        self._sync_agent_configs_actions()

        self._ui_theme = QComboBox()
        self._ui_theme.setToolTip(
            "Auto syncs background theme to the active agent.\nSelect a specific theme to force an override."
        )
        self._popup_theme_animation_enabled = QCheckBox("Enabled")
        self._popup_theme_animation_enabled.setToolTip(
            "When enabled, themed popup backgrounds stay animated. Disable to render popups as static backgrounds."
        )
        self._popup_theme_animation_enabled.setChecked(True)
        self._theme_preview_tiles: dict[str, ThemePreviewTile] = {}
        self._theme_preview_order: list[str] = []
        self._theme_preview_grid: QGridLayout | None = None
        self._theme_preview_host: QWidget | None = None
        self._ui_theme.currentIndexChanged.connect(self._on_theme_combo_changed)
        self._refresh_theme_options(selected="auto")

        self._preflight_enabled = QToolButton()
        self._preflight_enabled.setCheckable(True)
        self._preflight_enabled.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._preflight_enabled.setToolTip("Run global preflight before setup-agents.sh.")
        self._preflight_enabled.toggled.connect(self._on_preflight_enabled_toggled)

        self._append_pixelarch_context = QCheckBox("Enabled")
        self._append_pixelarch_context.setToolTip(
            "When enabled, appends a short note to prompts passed to Run Agent.\nThis does not affect Run Interactive."
        )

        self._headless_desktop_enabled = QCheckBox("Enabled")
        self._headless_desktop_enabled.setToolTip(
            "When enabled, this overrides per-environment headless desktop settings."
        )
        self._gpu_enabled = QCheckBox("Enabled")
        self._gpu_enabled.setToolTip(
            "When enabled, task containers request GPU runtime access (`--gpus all`) for Agent and Interactive runs."
        )
        self._network_host = QCheckBox("Enabled")
        self._network_host.setToolTip(
            "When enabled, task containers use host networking (`--network host`). "
            "This gives containers direct access to the host's network interfaces. "
            "May require sudo/privileged access."
        )
        self._auto_navigate_on_run_agent_start = QCheckBox("Enabled")
        self._auto_navigate_on_run_agent_start.setToolTip(
            "When enabled, starting a Run Agent task switches to the Home dashboard."
        )
        self._auto_navigate_on_run_interactive_start = QCheckBox("Enabled")
        self._auto_navigate_on_run_interactive_start.setToolTip(
            "When enabled, starting a Run Interactive task switches to the Home dashboard."
        )

        self._gh_context_default = QCheckBox("Enabled")
        self._gh_context_default.setToolTip(
            "Only affects newly created environments. Existing environments keep their settings."
        )

        self._spellcheck_enabled = QCheckBox("Enabled")
        self._spellcheck_enabled.setToolTip(
            "Underlines misspelled words in the prompt editor and provides suggestions."
        )

        self._mount_host_cache = QCheckBox("Enabled")
        self._mount_host_cache.setToolTip("Mounts ~/.cache to speed up package manager installs across environments.")

        self._task_workspace_location = QComboBox()
        self._task_workspace_location.addItem("App data", TASK_WORKSPACE_LOCATION_APP_DATA)
        self._task_workspace_location.addItem("Scratch drive", TASK_WORKSPACE_LOCATION_SCRATCH_DRIVE)
        self._task_workspace_location.setToolTip("Controls where cloned task workspaces are stored on the host.")
        self._task_workspace_location.currentIndexChanged.connect(self._refresh_task_workspace_controls)

        self._scratch_drive_status = QLabel("")
        self._scratch_drive_status.setObjectName("SettingsPaneSubtitle")
        self._scratch_drive_status.setWordWrap(True)
        self._workspace_status_spinner = ArcSpinner(size=18)
        self._workspace_status_spinner.setToolTip("Checking workspace storage...")
        self._workspace_status_spinner.setVisible(False)

        self._move_task_workspaces = QToolButton()
        self._move_task_workspaces.setText("Move all tasks")
        self._move_task_workspaces.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._move_task_workspaces.clicked.connect(self._on_move_task_workspaces)
        self._move_task_workspaces.installEventFilter(cast(QObject, self))
        self._task_workspace_migration_blocked = False
        self._move_task_workspaces_shift_pressed = False
        self._move_task_workspaces_shift_click_force = False
        self._move_task_workspaces_shift_poll_timer = QTimer(cast(QObject, self))
        self._move_task_workspaces_shift_poll_timer.setInterval(50)
        self._move_task_workspaces_shift_poll_timer.timeout.connect(self._poll_move_task_workspaces_shift_state)

        self._task_workspace_cleanup_retention_days = QSpinBox()
        self._task_workspace_cleanup_retention_days.setRange(1, 365)
        self._task_workspace_cleanup_retention_days.setSuffix(" days")
        self._task_workspace_cleanup_retention_days.setValue(30)

        self._task_workspace_cleanup_interval_minutes = QSpinBox()
        self._task_workspace_cleanup_interval_minutes.setRange(5, 1440)
        self._task_workspace_cleanup_interval_minutes.setSuffix(" minutes")
        self._task_workspace_cleanup_interval_minutes.setValue(60)

        self._task_workspace_cleanup_scan_delay_seconds = QSpinBox()
        self._task_workspace_cleanup_scan_delay_seconds.setRange(0, 60)
        self._task_workspace_cleanup_scan_delay_seconds.setSuffix(" seconds")
        self._task_workspace_cleanup_scan_delay_seconds.setValue(5)

        self._task_workspace_cleanup_size_threshold_gb = QSpinBox()
        self._task_workspace_cleanup_size_threshold_gb.setRange(1, 1000)
        self._task_workspace_cleanup_size_threshold_gb.setSuffix(" GB")
        self._task_workspace_cleanup_size_threshold_gb.setValue(50)

        self._task_workspace_cleanup_size_ram_cap_label = QLabel("")
        self._task_workspace_cleanup_size_ram_cap_label.setObjectName("SettingsPaneSubtitle")
        self._task_workspace_cleanup_size_ram_cap_label.setWordWrap(True)
        self._task_workspace_cleanup_size_ram_cap_label.setVisible(False)

        self._task_workspace_cleanup_note = QLabel("")
        self._task_workspace_cleanup_note.setObjectName("SettingsPaneSubtitle")
        self._task_workspace_cleanup_note.setWordWrap(True)
        self._force_cleanup_button = QPushButton("Force Clean Now")
        self._task_workspace_cleanup_controls: list[QWidget] = [
            self._task_workspace_cleanup_retention_days,
            self._task_workspace_cleanup_interval_minutes,
            self._task_workspace_cleanup_scan_delay_seconds,
            self._task_workspace_cleanup_size_threshold_gb,
            self._force_cleanup_button,
        ]
        self._workspace_status_checking = False
        self._workspace_status_request_id = 0
        self._workspace_status_running = False
        self._workspace_status_pending = False
        self._workspace_status_worker: _WorkspaceStatusWorker | None = None
        self._scratch_drive_latest_status: ScratchDriveStatus | None = None

        self._github_workroom_prefer_browser = QCheckBox("Enabled")
        self._github_workroom_prefer_browser.setToolTip(
            "When enabled, opening an issue or pull request goes directly to the system browser."
        )

        self._github_write_confirmation_mode = QComboBox()
        self._github_write_confirmation_mode.addItem("Always confirm", "always")
        self._github_write_confirmation_mode.addItem(
            "Confirm destructive only",
            "destructive_only",
        )
        self._github_write_confirmation_mode.addItem("No confirmations", "never")
        self._github_write_confirmation_mode.setToolTip(
            "Controls confirmation prompts for GitHub write actions (open/close, comments, reaction markers)."
        )

        self._agentsnova_auto_review_enabled = QCheckBox("Enabled")
        self._agentsnova_auto_review_enabled.setToolTip(
            "When enabled, PR/Issue mentions of @agentsnova can auto-queue tasks."
        )
        self._agentsnova_auto_marker_comments_mode = QComboBox()
        self._agentsnova_auto_marker_comments_mode.addItem(
            "Keep",
            "keep",
        )
        self._agentsnova_auto_marker_comments_mode.addItem(
            "Delete after 15s",
            "delete_after_15s",
        )
        self._agentsnova_auto_marker_comments_mode.addItem(
            "Disabled",
            "disabled",
        )
        self._agentsnova_auto_marker_comments_mode.setToolTip(
            "Default mode for @agentsnova marker comments. Environments can inherit this mode or override it."
        )
        self._agentsnova_auto_reactions_enabled = QCheckBox("Enabled")
        self._agentsnova_auto_reactions_enabled.setToolTip(
            "When enabled, @agentsnova queue triggers apply GitHub `eyes` reactions."
        )
        self._github_polling_enabled = QCheckBox("Enabled")
        self._github_polling_enabled.setToolTip(
            "When enabled, GitHub Issues/PRs poll in the background across enabled environments."
        )
        self._github_poll_startup_delay_s = QLineEdit()
        self._github_poll_startup_delay_s.setValidator(QIntValidator(0, 3600, cast(QObject, self)))
        self._github_poll_startup_delay_s.setPlaceholderText("35")
        self._github_poll_startup_delay_s.setMaximumWidth(120)
        self._github_poll_startup_delay_s.setToolTip(
            "Seconds to wait after app startup before beginning background GitHub polling."
        )
        self._agentsnova_trusted_users_global = GitHubUsernameListWidget()
        self._agentsnova_trusted_users_global.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._agentsnova_trusted_users_global.set_add_button_visible(False)
        self._add_trusted_user_global = self._agentsnova_trusted_users_global.create_add_button(cast(QWidget, self))
        self._setup_github_defaults_global = QToolButton()
        self._setup_github_defaults_global.setText("Setup Defaults")
        self._setup_github_defaults_global.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._setup_github_defaults_global.setToolTip(
            "Seed trusted users from cloned environment owners/org members and current gh login."
        )
        self._setup_github_defaults_global.clicked.connect(self._on_setup_global_github_defaults)

        self._preflight_script = QPlainTextEdit()
        self._preflight_script.setPlaceholderText(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "\n"
            "# Runs inside the container before the agent command.\n"
            "# Runs on every environment, before setup-agents.sh.\n"
            "# This script is mounted read-only and deleted from the host after task finish.\n"
        )
        self._preflight_script.setTabChangesFocus(True)
        self._preflight_script.setEnabled(False)
        self._on_preflight_enabled_toggled(bool(self._preflight_enabled.isChecked()))
        self._preflight_script.textChanged.connect(self._on_preflight_script_text_changed)
        self._preflight_script_highlighter = ArtifactSyntaxHighlighter(self._preflight_script.document())
        self._refresh_preflight_script_highlighting(str(self._preflight_script.toPlainText() or ""))

        self._recommended_preflights = QComboBox()
        self._recommended_preflights.setToolTip("Load a recommended preflight script.")
        self._populate_recommended_preflights()
        self._recommended_preflights.currentIndexChanged.connect(self._on_recommended_preflight_selected)

        self._test_preflights = QToolButton()
        self._test_preflights.setText("Run preflight checks")
        self._test_preflights.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._test_preflights.setToolTip("Run preflight smoke test for all environments.")
        self._test_preflights.clicked.connect(self._on_test_preflight)

        self._radio_enabled = QCheckBox("Enabled")
        self._radio_enabled.setToolTip("Controls whether the navbar radio system is enabled.")
        self._radio_autostart = QCheckBox("Enabled")
        self._radio_autostart.setToolTip("Starts playback automatically at launch when radio is enabled.")
        self._radio_autostart.setEnabled(False)

        self._radio_channel_values: list[str] = []
        self._radio_channel_enabled = False
        self._radio_channel = QComboBox()
        self._radio_channel.setToolTip("Select a radio channel. All channels uses the server default behavior.")
        self._radio_channel.setEnabled(False)
        self.set_radio_channel_options([], selected="", enabled=False)

        self._radio_quality = QComboBox()
        self._radio_quality.addItem("Low (96 kbps)", "low")
        self._radio_quality.addItem("Medium (160 kbps)", "medium")
        self._radio_quality.addItem("High (320 kbps)", "high")

        self._radio_volume = QSlider(Qt.Orientation.Horizontal)
        self._radio_volume.setObjectName("SettingsVolumeSlider")
        self._radio_volume.setRange(0, 100)
        self._radio_volume.setValue(70)
        self._radio_volume_value = QLabel("70%")
        self._radio_volume_value.setObjectName("SettingsPaneSubtitle")
        self._radio_volume.valueChanged.connect(self._on_radio_volume_value_changed)

        self._radio_loudness_boost_enabled = QCheckBox("Enabled")
        self._radio_loudness_boost_enabled.setToolTip("Applies a gain multiplier to radio volume mapping.")
        self._radio_loudness_boost_enabled.toggled.connect(self._on_radio_loudness_boost_toggled)

        self._radio_loudness_boost_factor = QDoubleSpinBox()
        self._radio_loudness_boost_factor.setObjectName("SettingsBoostSpinBox")
        self._radio_loudness_boost_factor.setRange(
            RadioController.LOUDNESS_BOOST_MIN,
            RadioController.LOUDNESS_BOOST_MAX,
        )
        self._radio_loudness_boost_factor.setSingleStep(RadioController.LOUDNESS_BOOST_STEP)
        self._radio_loudness_boost_factor.setDecimals(2)
        self._radio_loudness_boost_factor.setValue(RadioController.LOUDNESS_BOOST_DEFAULT)
        self._radio_loudness_boost_factor.setSuffix("x")
        self._radio_loudness_boost_factor.setEnabled(False)
        self._radio_loudness_boost_factor.setToolTip(
            "Boost multiplier for radio loudness. Effective output is capped by Qt audio output at 100%."
        )
        self._radio_loudness_boost_factor.valueChanged.connect(self._on_radio_loudness_boost_factor_changed)

        self._radio_enabled.toggled.connect(self._radio_autostart.setEnabled)

    def _build_pages(self) -> None:
        specs_by_key: dict[str, _SettingsPaneSpec] = {spec.key: spec for spec in self._pane_specs}  # pyright: ignore[reportUnknownVariableType]

        general_page, general_body = self._create_page(specs_by_key["general_preferences"])
        terminal_layout = QGridLayout()
        configure_form_grid(terminal_layout)
        add_grid_row(terminal_layout, 0, QLabel("Spellcheck"), self._spellcheck_enabled)
        add_grid_row(
            terminal_layout,
            1,
            QLabel("GitHub context default"),
            self._gh_context_default,
        )
        add_grid_row(
            terminal_layout,
            2,
            QLabel("Append PixelArch context"),
            self._append_pixelarch_context,
        )
        add_grid_row(
            terminal_layout,
            3,
            QLabel("Interactive terminal"),
            self._interactive_terminal,
            self._refresh_interactive_terminal,
        )
        general_body.addLayout(terminal_layout)
        general_body.addStretch(1)
        self._register_page("general_preferences", general_page)

        storage_page, storage_body = self._create_page(specs_by_key["storage"])
        workspaces_grid = QGridLayout()
        configure_form_grid(workspaces_grid)
        add_grid_row(
            workspaces_grid,
            0,
            QLabel("Task workspace location"),
            self._task_workspace_location,
        )
        self._scratch_drive_status_label = QLabel("Scratch drive")
        self._scratch_drive_status_row = QWidget(storage_page)
        scratch_status_layout = QHBoxLayout(self._scratch_drive_status_row)
        scratch_status_layout.setContentsMargins(0, 0, 0, 0)
        scratch_status_layout.setSpacing(BUTTON_ROW_SPACING)
        scratch_status_layout.addWidget(self._workspace_status_spinner)
        scratch_status_layout.addWidget(self._scratch_drive_status, 1)
        add_grid_row(
            workspaces_grid,
            1,
            self._scratch_drive_status_label,
            self._scratch_drive_status_row,
        )
        add_grid_row(workspaces_grid, 2, QLabel("Move all tasks"), self._move_task_workspaces)
        storage_body.addLayout(workspaces_grid)
        storage_body.addStretch(1)
        self._register_page("storage", storage_page)

        cleanup_page, cleanup_body = self._create_page(specs_by_key["cleanup"])
        cleanup_grid = QGridLayout()
        configure_form_grid(cleanup_grid)
        add_grid_row(
            cleanup_grid,
            0,
            QLabel("Keep finished workspaces"),
            self._task_workspace_cleanup_retention_days,
        )
        add_grid_row(
            cleanup_grid,
            1,
            QLabel("Check for cleanup every"),
            self._task_workspace_cleanup_interval_minutes,
        )
        add_grid_row(
            cleanup_grid,
            2,
            QLabel("Wait between scans"),
            self._task_workspace_cleanup_scan_delay_seconds,
        )
        add_grid_row(
            cleanup_grid,
            3,
            QLabel("Workspace size limit"),
            self._task_workspace_cleanup_size_threshold_gb,
        )
        add_grid_row(
            cleanup_grid,
            4,
            QLabel(""),
            self._task_workspace_cleanup_size_ram_cap_label,
        )
        add_grid_row(cleanup_grid, 5, QLabel("Force cleanup"), self._force_cleanup_button)
        cleanup_body.addLayout(cleanup_grid)
        cleanup_body.addWidget(self._task_workspace_cleanup_note)
        cleanup_body.addStretch(1)
        self._register_page("cleanup", cleanup_page)

        themes_page, themes_body = self._create_page(specs_by_key["themes"])
        themes_grid = QGridLayout()
        configure_form_grid(themes_grid)
        add_grid_row(
            themes_grid,
            0,
            QLabel("Animate popup backgrounds"),
            self._popup_theme_animation_enabled,
        )
        add_grid_row(themes_grid, 1, QLabel("Theme"), self._ui_theme)
        themes_body.addLayout(themes_grid)
        previews_heading = QLabel("Theme previews")
        previews_heading.setObjectName("SettingsPaneSubtitle")
        themes_body.addWidget(previews_heading)

        self._theme_preview_host = QWidget(themes_page)
        self._theme_preview_host.setObjectName("ThemePreviewGridHost")
        self._theme_preview_grid = QGridLayout(self._theme_preview_host)
        self._theme_preview_grid.setContentsMargins(0, 0, 0, 0)
        self._theme_preview_grid.setHorizontalSpacing(GRID_HORIZONTAL_SPACING)
        self._theme_preview_grid.setVerticalSpacing(GRID_VERTICAL_SPACING)
        themes_body.addWidget(self._theme_preview_host)
        self._refresh_theme_preview_tiles(selected="auto")
        themes_body.addStretch(1)
        self._register_page("themes", themes_page)

        agent_page, agent_body = self._create_page(specs_by_key["agent_defaults"])
        agent_grid = QGridLayout()
        configure_form_grid(agent_grid)
        add_grid_row(agent_grid, 0, QLabel("Agent CLI"), self._use)
        add_grid_row(agent_grid, 1, QLabel("Agent Shell"), self._shell)
        add_grid_row(
            agent_grid,
            2,
            QLabel("OpenCode interactive"),
            self._opencode_interactive_mode,
        )
        agent_body.addLayout(agent_grid)
        agent_body.addStretch(1)
        self._register_page("agent_defaults", agent_page)

        agent_configs_page, agent_configs_body = self._create_page(specs_by_key["agent_configs"])
        agent_configs_body.addWidget(self._agent_configs_list, 1)
        agent_configs_actions = QHBoxLayout()
        agent_configs_actions.setSpacing(BUTTON_ROW_SPACING)
        agent_configs_actions.addWidget(self._agent_configs_add)
        agent_configs_actions.addWidget(self._agent_configs_edit)
        agent_configs_actions.addWidget(self._agent_configs_delete)
        agent_configs_actions.addStretch(1)
        agent_configs_body.addLayout(agent_configs_actions)
        self._register_page("agent_configs", agent_configs_page)

        github_config_page, github_config_body = self._create_page(specs_by_key["github_config"])
        github_grid = QGridLayout()
        configure_form_grid(github_grid)
        add_grid_row(
            github_grid,
            0,
            QLabel("Workroom browser"),
            self._github_workroom_prefer_browser,
        )
        add_grid_row(
            github_grid,
            1,
            QLabel("Auto-review queueing"),
            self._agentsnova_auto_review_enabled,
        )
        add_grid_row(
            github_grid,
            2,
            QLabel("Auto reactions"),
            self._agentsnova_auto_reactions_enabled,
        )
        add_grid_row(
            github_grid,
            3,
            QLabel("GitHub polling"),
            self._github_polling_enabled,
        )
        add_grid_row(
            github_grid,
            4,
            QLabel("Default marker comments"),
            self._agentsnova_auto_marker_comments_mode,
        )
        add_grid_row(
            github_grid,
            5,
            QLabel("GitHub write confirmations"),
            self._github_write_confirmation_mode,
        )
        add_grid_row(
            github_grid,
            6,
            QLabel("Polling startup delay (s)"),
            self._github_poll_startup_delay_s,
        )
        github_config_body.addLayout(github_grid)
        github_config_body.addStretch(1)
        self._register_page("github_config", github_config_page)

        github_trusted_page, github_trusted_body = self._create_page(specs_by_key["github_trusted_users"])
        github_trusted_body.addWidget(self._agentsnova_trusted_users_global, 1)

        github_actions = QHBoxLayout()
        github_actions.setSpacing(BUTTON_ROW_SPACING)
        github_actions.addWidget(self._add_trusted_user_global)
        github_actions.addStretch(1)
        github_actions.addWidget(self._setup_github_defaults_global)
        github_trusted_body.addLayout(github_actions)
        self._register_page("github_trusted_users", github_trusted_page)

        runtime_page, runtime_body = self._create_page(specs_by_key["runtime_behavior"])
        runtime_grid = QGridLayout()
        configure_form_grid(runtime_grid)
        add_grid_row(
            runtime_grid,
            0,
            QLabel("Force headless desktop"),
            self._headless_desktop_enabled,
        )
        add_grid_row(
            runtime_grid,
            1,
            QLabel("Enable GPU"),
            self._gpu_enabled,
        )
        add_grid_row(
            runtime_grid,
            2,
            QLabel("Network host"),
            self._network_host,
        )
        add_grid_row(
            runtime_grid,
            3,
            QLabel("Navigate Home on Run Agent start"),
            self._auto_navigate_on_run_agent_start,
        )
        add_grid_row(
            runtime_grid,
            4,
            QLabel("Navigate Home on Run Interactive start"),
            self._auto_navigate_on_run_interactive_start,
        )
        add_grid_row(
            runtime_grid,
            5,
            QLabel("Mount host cache"),
            self._mount_host_cache,
        )
        runtime_body.addLayout(runtime_grid)
        runtime_body.addStretch(1)
        self._register_page("runtime_behavior", runtime_page)

        preflight_page, preflight_body = self._create_page(specs_by_key["preflight_script"])
        preflight_body.addWidget(self._preflight_script, 1)
        preflight_actions = QHBoxLayout()
        preflight_actions.setSpacing(BUTTON_ROW_SPACING)
        preflight_actions.addWidget(self._preflight_enabled)
        preflight_actions.addWidget(self._recommended_preflights)
        preflight_actions.addWidget(self._test_preflights)
        preflight_actions.addStretch(1)
        autosave_hint = QLabel("Changes save automatically.")
        autosave_hint.setObjectName("SettingsPaneSubtitle")
        preflight_actions.addWidget(autosave_hint)
        preflight_body.addLayout(preflight_actions)
        self._register_page("preflight_script", preflight_page)

        radio_spec = specs_by_key.get("radio")  # pyright: ignore[reportUnknownVariableType]
        if radio_spec is not None:
            radio_page, radio_body = self._create_page(radio_spec)
            radio_grid = QGridLayout()
            configure_form_grid(radio_grid)
            add_grid_row(radio_grid, 0, QLabel("Midori AI Radio"), self._radio_enabled)
            add_grid_row(radio_grid, 1, QLabel("Radio auto-start"), self._radio_autostart)
            add_grid_row(radio_grid, 2, QLabel("Channel"), self._radio_channel)
            add_grid_row(radio_grid, 3, QLabel("Stream quality"), self._radio_quality)

            volume_row = QWidget(radio_page)
            volume_layout = QHBoxLayout(volume_row)
            volume_layout.setContentsMargins(0, 0, 0, 0)
            volume_layout.setSpacing(BUTTON_ROW_SPACING)
            volume_layout.addWidget(self._radio_volume, 1)
            volume_layout.addWidget(self._radio_volume_value)
            add_grid_row(radio_grid, 4, QLabel("Volume"), volume_row)

            boost_row = create_stretch_row(
                self._radio_loudness_boost_enabled,
                self._radio_loudness_boost_factor,
                stretch_index=2,
            )
            add_grid_row(radio_grid, 5, QLabel("Loudness"), boost_row)

            radio_body.addLayout(radio_grid)
            radio_body.addStretch(1)
            self._register_page("radio", radio_page)

    def _build_navigation(self, nav_layout: QVBoxLayout) -> None:
        sections: dict[str, list[_SettingsPaneSpec]] = {}
        for spec in self._pane_specs:  # pyright: ignore[reportUnknownVariableType]
            sections.setdefault(spec.section, []).append(spec)

        for section_title, specs in sections.items():
            section_label = QLabel(section_title)
            section_label.setObjectName("SettingsNavSection")
            nav_layout.addWidget(section_label)

            for spec in specs:
                button = QToolButton()
                button.setObjectName("SettingsNavButton")
                button_label = "Preferences" if spec.key == "general_preferences" else spec.title
                button.setText(button_label)
                button.setToolTip(spec.subtitle)
                button.setCheckable(True)
                button.setAutoExclusive(True)
                button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
                button.setFixedHeight(40)
                button.setSizePolicy(
                    QSizePolicy.Policy.Expanding,
                    QSizePolicy.Policy.Fixed,
                )
                button.clicked.connect(lambda checked=False, key=spec.key: self._on_nav_button_clicked(key))
                nav_layout.addWidget(button)
                self._nav_buttons[spec.key] = button
                self._compact_nav.addItem(button_label, spec.key)

        nav_layout.addStretch(1)

    def _resolve_state_path(self) -> str:
        state_path = str(getattr(self, "_state_path", "") or "").strip()
        if state_path:
            return state_path
        window = getattr(self, "window", lambda: None)()
        state_path = str(getattr(window, "_state_path", "") or "").strip()
        if state_path:
            return state_path
        return default_state_path()

    def _agent_config_usage_counts(self) -> dict[str, int]:
        state_path = self._resolve_state_path()
        counts: dict[str, int] = {}
        try:
            configs = load_agent_configs(state_path)
        except Exception:
            configs = []
        for cfg in configs:
            config_id = str(getattr(cfg, "config_id", "") or "").strip()
            if not config_id:
                continue
            try:
                refs = find_envs_referencing_config(state_path, config_id)
            except Exception:
                refs = []
            counts[config_id] = len(refs)
        return counts

    def _refresh_agent_configs_list(self, *, select_config_id: str = "") -> None:
        if not hasattr(self, "_agent_configs_list"):
            return

        selected = str(select_config_id or "").strip()
        if not selected:
            selected = str(self._agent_configs_selected_config_id() or "").strip()

        try:
            configs = load_agent_configs(self._resolve_state_path())
        except Exception:
            configs = []
        configs.sort(key=lambda cfg: str(getattr(cfg, "config_id", "") or "").lower())

        self._agent_configs = list(configs)
        self._agent_configs_by_id = {
            str(cfg.config_id or "").strip(): cfg for cfg in configs if str(getattr(cfg, "config_id", "") or "").strip()
        }

        usage_counts = self._agent_config_usage_counts()

        self._agent_configs_list.clear()
        if not configs:
            empty = QListWidgetItem("No agent configs saved.")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._agent_configs_list.addItem(empty)
            self._sync_agent_configs_actions()
            return

        chosen_row = -1
        for index, cfg in enumerate(configs):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, str(cfg.config_id or ""))
            widget = self._create_agent_config_row_widget(cfg, usage_counts=usage_counts)
            item.setSizeHint(widget.sizeHint())
            self._agent_configs_list.addItem(item)
            self._agent_configs_list.setItemWidget(item, widget)
            if selected and str(cfg.config_id or "").strip() == selected:
                chosen_row = index

        if chosen_row >= 0:
            self._agent_configs_list.setCurrentRow(chosen_row)
        elif self._agent_configs_list.count() > 0:
            self._agent_configs_list.setCurrentRow(0)
        self._sync_agent_configs_actions()

    def _agent_configs_selected_config_id(self) -> str:
        item = self._agent_configs_list.currentItem()
        if item is None:
            return ""
        return str(item.data(Qt.ItemDataRole.UserRole) or "").strip()

    def _selected_agent_config(self) -> AgentConfig | None:
        config_id = self._agent_configs_selected_config_id()
        if not config_id:
            return None
        return self._agent_configs_by_id.get(config_id)

    def _sync_agent_configs_actions(self) -> None:
        selected = bool(self._selected_agent_config() is not None)
        if hasattr(self, "_agent_configs_edit"):
            self._agent_configs_edit.setEnabled(selected)
        if hasattr(self, "_agent_configs_delete"):
            self._agent_configs_delete.setEnabled(selected)

    def _create_agent_config_row_widget(
        self, config: AgentConfig, *, usage_counts: dict[str, int] | None = None
    ) -> QWidget:
        row = QWidget(self._agent_configs_list)
        layout = QVBoxLayout(row)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(0)

        title = QLabel(str(getattr(config, "config_id", "") or "").strip())
        title.setStyleSheet("font-size: 12px; font-weight: 650; color: rgba(237, 239, 245, 230);")

        config_id = str(getattr(config, "config_id", "") or "").strip()
        count = (usage_counts or {}).get(config_id, 0)
        if count > 0:
            usage = QLabel(f"{count} Env")
            usage.setStyleSheet("font-size: 10px; color: rgba(129, 199, 132, 220);")
        else:
            usage = QLabel("0 Env")
            usage.setStyleSheet("font-size: 10px; color: rgba(255, 183, 77, 220);")
        usage.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        title_row.addWidget(title)
        title_row.addWidget(usage, 1)

        agent_cli = str(getattr(config, "agent_cli", "") or "").strip()
        config_dir = str(getattr(config, "config_dir", "") or "").strip()
        cli_flags = str(getattr(config, "cli_flags", "") or "").strip()
        agent = str(getattr(config, "agent", "") or "").strip()
        model = str(getattr(config, "model", "") or "").strip()
        variant = str(getattr(config, "variant", "") or "").strip()

        parts = [f"Agent CLI: {agent_cli}" if agent_cli else "Agent CLI: —"]
        if config_dir:
            parts.append(f"Config Dir: {config_dir}")
        if cli_flags:
            parts.append(f"CLI Flags: {cli_flags}")
        if agent:
            parts.append(f"Agent: {agent}")
        if model:
            parts.append(f"Model: {model}")
        if variant:
            parts.append(f"Variant: {variant}")

        detail = QLabel("\n".join(parts))
        detail.setObjectName("SettingsPaneSubtitle")
        detail.setWordWrap(True)

        layout.addLayout(title_row)
        layout.addWidget(detail)

        return row

    def _on_agent_configs_add_clicked(self) -> None:
        overrides = get_opencode_cli_overrides()
        dialog = AgentConfigDialog(
            cast(QWidget, self),
            initial_agent=overrides.get("agent", ""),
            initial_model=overrides.get("model", ""),
            initial_variant=overrides.get("variant", ""),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        config = dialog.agent_config()
        if config is None:
            return
        try:
            save_agent_config(self._resolve_state_path(), config)
        except Exception as exc:
            QMessageBox.warning(cast(QWidget, self), "Save failed", str(exc))
            return
        self._refresh_agent_configs_list(select_config_id=str(config.config_id or ""))

    def _on_agent_configs_edit_clicked(self) -> None:
        selected = self._selected_agent_config()
        if selected is None:
            return
        dialog = AgentConfigDialog(cast(QWidget, self), config=selected)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        updated = dialog.agent_config()
        if updated is None:
            return
        try:
            save_agent_config(self._resolve_state_path(), updated)
        except Exception as exc:
            QMessageBox.warning(cast(QWidget, self), "Save failed", str(exc))
            return
        self._refresh_agent_configs_list(select_config_id=str(updated.config_id or ""))

    def _on_agent_configs_delete_clicked(self) -> None:
        selected = self._selected_agent_config()
        if selected is None:
            return
        config_id = str(getattr(selected, "config_id", "") or "").strip()
        if not config_id:
            return

        state_path = self._resolve_state_path()
        referenced: list[str] = []
        try:
            referenced = find_envs_referencing_config(state_path, config_id)
        except Exception:
            referenced = []

        referenced = [str(item or "").strip() for item in referenced if str(item or "").strip()]
        referenced.sort(key=str.casefold)

        if referenced:
            prompt = (
                f"This config is referenced by {len(referenced)} environment(s): {', '.join(referenced)}\n\n"
                "Deleting it will remove this config ID from those environments."
            )
            result = QMessageBox.warning(
                cast(QWidget, self),
                "Delete agent config?",
                prompt,
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if result != QMessageBox.StandardButton.Ok:
                return

        try:
            delete_agent_config(state_path, config_id)
        except Exception as exc:
            QMessageBox.warning(cast(QWidget, self), "Delete failed", str(exc))
            return
        self._refresh_agent_configs_list()

    def _create_page(self, spec: _SettingsPaneSpec) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        scroll = EdgeFadeScrollArea(page)
        scroll.setObjectName("SettingsPaneScrollArea")

        content = QWidget(scroll)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        title = QLabel(spec.title)
        title.setObjectName("SettingsPaneTitle")

        subtitle = QLabel(spec.subtitle)
        subtitle.setObjectName("SettingsPaneSubtitle")
        subtitle.setWordWrap(True)

        body = QWidget(content)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(GRID_VERTICAL_SPACING)

        content_layout.addWidget(title)
        content_layout.addWidget(subtitle)
        content_layout.addWidget(body)

        scroll.setWidget(content)
        page_layout.addWidget(scroll, 1)
        return page, body_layout

    def _register_page(self, key: str, widget: QWidget) -> None:
        index = self._page_stack.addWidget(widget)  # pyright: ignore[reportUnknownVariableType]
        self._pane_index_by_key[key] = index

    def _populate_agent_combo(self) -> None:
        selected = str(self._use.currentData() or "") if hasattr(self, "_use") else ""

        with QSignalBlocker(self._use):
            self._use.clear()
            for agent_name in available_agent_system_names(include_internal=False):
                label = format_agent_ui_label(agent_name)
                self._use.addItem(label, agent_name)

            if self._use.count() == 0:
                default_name = get_default_agent_system_name()
                self._use.addItem(format_agent_ui_label(default_name), default_name)

        preferred = normalize_agent(selected or str(self._use.itemData(0) or ""))
        self._set_combo_value(self._use, preferred, fallback=preferred)

    def _refresh_theme_options(self, selected: str | None) -> None:
        normalized_selected = normalize_ui_theme_name(selected, allow_auto=True)

        with QSignalBlocker(self._ui_theme):
            self._ui_theme.clear()
            self._ui_theme.addItem("Auto (sync to active agent)", "auto")
            for theme_name in available_ui_theme_names():
                self._ui_theme.addItem(self._format_theme_label(theme_name), theme_name)
            self._set_combo_value(self._ui_theme, normalized_selected, fallback="auto")
        self._refresh_theme_preview_tiles(selected=normalized_selected)

    def _refresh_theme_preview_tiles(self, selected: str | None) -> None:
        if self._theme_preview_grid is None:
            return

        normalized_selected = normalize_ui_theme_name(selected, allow_auto=True)
        theme_names = [name for name in available_ui_theme_names() if str(name).strip()]
        if theme_names != self._theme_preview_order:
            self._rebuild_theme_preview_tiles(theme_names)

        for theme_name, tile in self._theme_preview_tiles.items():
            tile.set_selected(normalized_selected != "auto" and theme_name == normalized_selected)

    def _rebuild_theme_preview_tiles(self, theme_names: list[str]) -> None:
        if self._theme_preview_grid is None:
            return

        self._theme_preview_order = list(theme_names)
        self._theme_preview_tiles.clear()
        self._clear_layout(self._theme_preview_grid)

        columns = 3
        if not theme_names:
            empty = QLabel("No themes available.")
            empty.setObjectName("SettingsPaneSubtitle")
            self._theme_preview_grid.addWidget(empty, 0, 0, 1, columns)
            for col in range(columns):
                self._theme_preview_grid.setColumnStretch(col, 1)
            return

        for index, theme_name in enumerate(theme_names):
            row = index // columns
            col = index % columns
            tile = ThemePreviewTile(
                theme_name=theme_name,
                label=self._format_theme_label(theme_name),
                parent=self._theme_preview_host,
            )
            tile.clicked.connect(self._on_theme_preview_tile_clicked)
            self._theme_preview_grid.addWidget(tile, row, col)
            self._theme_preview_tiles[theme_name] = tile

        for col in range(columns):
            self._theme_preview_grid.setColumnStretch(col, 1)

        trailing_row = (len(theme_names) + columns - 1) // columns
        self._theme_preview_grid.setRowStretch(trailing_row, 1)

    def _on_theme_combo_changed(self, _index: int) -> None:
        theme_value = normalize_ui_theme_name(
            str(self._ui_theme.currentData() or "auto"),
            allow_auto=True,
        )
        self._refresh_theme_preview_tiles(selected=theme_value)

    def _on_theme_preview_tile_clicked(self, theme_name: str) -> None:
        normalized_theme = normalize_ui_theme_name(theme_name, allow_auto=False)
        dialog = ThemePreviewDialog(
            theme_name=normalized_theme,
            theme_label=self._format_theme_label(normalized_theme),
            parent=cast(QWidget, self),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        applied_theme = dialog.applied_theme_name()
        if not applied_theme:
            return

        normalized_selected = normalize_ui_theme_name(applied_theme, allow_auto=True)
        self._set_combo_value(self._ui_theme, normalized_selected, fallback="auto")
        self._refresh_theme_preview_tiles(selected=normalized_selected)

    @staticmethod
    def _clear_layout(layout: QGridLayout) -> None:
        while layout.count() > 0:
            item = layout.takeAt(0)
            widget = item.widget()  # pyright: ignore[reportOptionalMemberAccess]
            if widget is not None:
                widget.deleteLater()

    @staticmethod
    def _format_theme_label(value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized == "midoriai_dark":
            return "Midori AI (Dark Theme)"
        if normalized == "midoriai_light":
            return "Midori AI (Light Theme)"
        if normalized == "dynamic":
            return "Dynamic Music"
        try:
            return format_agent_ui_label(normalized)
        except Exception:
            pass
        return SettingsFormMixin._format_key_label(normalized)

    @staticmethod
    def _format_key_label(value: str) -> str:
        words = str(value or "").strip().replace("-", " ").replace("_", " ").split()
        if not words:
            return "Unknown"
        return " ".join(word.capitalize() for word in words)

    def _on_radio_volume_value_changed(self, value: int) -> None:
        _ = value
        self._refresh_radio_volume_label()

    def _on_radio_loudness_boost_toggled(self, enabled: bool) -> None:
        self._radio_loudness_boost_factor.setEnabled(bool(enabled))
        self._refresh_radio_volume_label()

    def _on_radio_loudness_boost_factor_changed(self, _value: float) -> None:
        self._refresh_radio_volume_label()

    def set_radio_channel_options(
        self,
        channels: list[str],
        *,
        selected: object,
        enabled: bool,
    ) -> None:
        normalized_selected = RadioController.normalize_channel(selected)
        normalized_channels: list[str] = []
        for raw in channels:
            channel = RadioController.normalize_channel(raw)
            if not channel or channel in normalized_channels:
                continue
            normalized_channels.append(channel)
        normalized_channels.sort()

        self._radio_channel_values = normalized_channels
        self._radio_channel_enabled = bool(enabled)

        with QSignalBlocker(self._radio_channel):
            self._radio_channel.clear()
            self._radio_channel.addItem("All channels", "")
            for channel in normalized_channels:
                self._radio_channel.addItem(channel, channel)
            if normalized_selected and normalized_selected not in normalized_channels:
                self._radio_channel.addItem(
                    f"Custom: {normalized_selected}",
                    normalized_selected,
                )
            self._set_combo_value(self._radio_channel, normalized_selected, fallback="")
        self._radio_channel.setEnabled(self._radio_channel_enabled)

    def _refresh_radio_volume_label(self) -> None:
        raw = max(0, min(100, int(self._radio_volume.value())))
        effective = self._effective_radio_volume_percent(raw)
        self._radio_volume_value.setText(f"{effective}%")

    def _effective_radio_volume_percent(self, value: int) -> int:
        raw = max(0, min(100, int(value)))
        if not self._radio_loudness_boost_enabled.isChecked():
            return raw
        factor = RadioController.normalize_loudness_boost_factor(self._radio_loudness_boost_factor.value())
        return max(0, int(round(raw * factor)))

    def set_settings(self, settings: dict[str, Any]) -> None:
        self._suppress_autosave = True
        try:
            self._populate_agent_combo()
            use_value = normalize_agent(str(settings.get("use") or ""))
            self._set_combo_value(
                self._use,
                use_value,
                fallback=str(self._use.itemData(0) or get_default_agent_system_name()),
            )

            shell_value = str(settings.get("shell") or "bash").strip().lower()
            self._set_combo_value(self._shell, shell_value, fallback="bash")
            self._set_combo_value(
                self._opencode_interactive_mode,
                normalize_opencode_interactive_mode(str(settings.get("opencode_interactive_mode") or "terminal")),
                fallback="terminal",
            )
            self._refresh_terminal_options(
                selected_terminal_id=str(settings.get("interactive_terminal_id") or "").strip()
            )
            enabled = bool(settings.get("preflight_enabled") or False)
            self._preflight_enabled.setChecked(enabled)
            self._preflight_script.setEnabled(enabled)
            self._preflight_script.setPlainText(str(settings.get("preflight_script") or ""))
            self._refresh_preflight_script_highlighting(str(self._preflight_script.toPlainText() or ""))
            self._reset_recommended_preflight_selection()

            self._append_pixelarch_context.setChecked(bool(settings.get("append_pixelarch_context") or False))
            self._github_workroom_prefer_browser.setChecked(
                bool(settings.get("github_workroom_prefer_browser") or False)
            )
            self._agentsnova_auto_review_enabled.setChecked(bool(settings.get("agentsnova_auto_review_enabled", True)))
            self._set_combo_value(
                self._agentsnova_auto_marker_comments_mode,
                normalize_default_marker_comment_mode(
                    settings.get(
                        "agentsnova_auto_marker_comments_mode",
                        settings.get("agentsnova_auto_marker_comments_enabled", True),
                    )
                ),
                fallback="keep",
            )
            self._agentsnova_auto_reactions_enabled.setChecked(
                bool(settings.get("agentsnova_auto_reactions_enabled", True))
            )
            self._github_polling_enabled.setChecked(bool(settings.get("github_polling_enabled") or False))
            try:
                poll_startup_delay_s = max(0, int(settings.get("github_poll_startup_delay_s", 35)))
            except Exception:
                poll_startup_delay_s = 35
            self._github_poll_startup_delay_s.setText(str(poll_startup_delay_s))
            trusted_users_raw = settings.get("agentsnova_trusted_users_global", [])
            trusted_users = trusted_users_raw if isinstance(trusted_users_raw, list) else []  # pyright: ignore[reportUnknownVariableType]
            self._agentsnova_trusted_users_global.set_usernames(trusted_users)
            self._headless_desktop_enabled.setChecked(bool(settings.get("headless_desktop_enabled") or False))
            self._gpu_enabled.setChecked(bool(settings.get("gpu_enabled") or False))
            self._network_host.setChecked(bool(settings.get("network_host") or False))
            self._auto_navigate_on_run_agent_start.setChecked(
                bool(settings.get("auto_navigate_on_run_agent_start") or False)
            )
            self._auto_navigate_on_run_interactive_start.setChecked(
                bool(settings.get("auto_navigate_on_run_interactive_start") or False)
            )
            confirmation_mode = str(settings.get("github_write_confirmation_mode") or "always").strip()
            self._set_combo_value(
                self._github_write_confirmation_mode,
                confirmation_mode,
                fallback="always",
            )
            self._gh_context_default.setChecked(bool(settings.get("gh_context_default_enabled") or False))
            self._spellcheck_enabled.setChecked(bool(settings.get("spellcheck_enabled", True)))
            self._mount_host_cache.setChecked(bool(settings.get("mount_host_cache", False)))
            workspace_location = normalize_task_workspace_location(settings.get("task_workspace_location"))
            with QSignalBlocker(self._task_workspace_location):
                self._set_combo_value(
                    self._task_workspace_location,
                    workspace_location,
                    fallback=TASK_WORKSPACE_LOCATION_APP_DATA,
                )
            self._task_workspace_cleanup_retention_days.setValue(
                self._clamp_spin_value(
                    settings.get("task_workspace_cleanup_retention_days"),
                    minimum=1,
                    maximum=365,
                    default=30,
                )
            )
            self._task_workspace_cleanup_interval_minutes.setValue(
                self._clamp_spin_value(
                    settings.get("task_workspace_cleanup_interval_minutes"),
                    minimum=5,
                    maximum=1440,
                    default=60,
                )
            )
            self._task_workspace_cleanup_scan_delay_seconds.setValue(
                self._clamp_spin_value(
                    settings.get("task_workspace_cleanup_scan_delay_seconds"),
                    minimum=0,
                    maximum=60,
                    default=5,
                )
            )
            self._task_workspace_cleanup_size_threshold_gb.setValue(
                self._clamp_spin_value(
                    settings.get("task_workspace_cleanup_size_threshold_gb"),
                    minimum=1,
                    maximum=1000,
                    default=50,
                )
            )
            self._refresh_task_workspace_controls()
            theme_value = normalize_ui_theme_name(settings.get("ui_theme"), allow_auto=True)
            self._refresh_theme_options(selected=theme_value)
            self._popup_theme_animation_enabled.setChecked(bool(settings.get("popup_theme_animation_enabled", True)))

            radio_enabled = bool(settings.get("radio_enabled") or False)
            self._radio_enabled.setChecked(radio_enabled)
            self._radio_autostart.setChecked(bool(settings.get("radio_autostart") or False))
            self._radio_autostart.setEnabled(radio_enabled)
            radio_channel = RadioController.normalize_channel(settings.get("radio_channel"))
            self.set_radio_channel_options(
                self._radio_channel_values,
                selected=radio_channel,
                enabled=self._radio_channel_enabled,
            )
            radio_quality = RadioController.normalize_quality(settings.get("radio_quality"))
            self._set_combo_value(self._radio_quality, radio_quality, fallback="medium")
            radio_volume = RadioController.clamp_volume(settings.get("radio_volume"))
            self._radio_volume.setValue(radio_volume)
            radio_loudness_boost_enabled = bool(settings.get("radio_loudness_boost_enabled") or False)
            self._radio_loudness_boost_enabled.setChecked(radio_loudness_boost_enabled)
            radio_loudness_boost_factor = RadioController.normalize_loudness_boost_factor(
                settings.get("radio_loudness_boost_factor")
            )
            self._radio_loudness_boost_factor.setValue(radio_loudness_boost_factor)
            self._radio_loudness_boost_factor.setEnabled(radio_loudness_boost_enabled)
            self._refresh_radio_volume_label()
            try:
                self._refresh_agent_configs_list()
            except Exception:
                pass
        finally:
            self._suppress_autosave = False

    def _on_preflight_enabled_toggled(self, enabled: bool) -> None:
        self._preflight_enabled.setText("Preflight Enabled" if bool(enabled) else "Enable Preflight")
        if hasattr(self, "_preflight_script"):
            self._preflight_script.setEnabled(bool(enabled))

    def _on_preflight_script_text_changed(self) -> None:
        self._refresh_preflight_script_highlighting(str(self._preflight_script.toPlainText() or ""))

    @staticmethod
    def _detect_preflight_script_language(script: str) -> str:
        shebang = str(script or "").split("\n", 1)[0].strip().lower()
        if shebang.startswith("#!"):
            if "fish" in shebang:
                return "fish"
            if "bash" in shebang or "zsh" in shebang or "sh" in shebang:
                return "bash"
        return "bash"

    def _refresh_preflight_script_highlighting(self, script: str) -> None:
        self._preflight_script_highlighter.set_language(self._detect_preflight_script_language(script))

    @staticmethod
    def _recommended_preflights_dir() -> Path:
        return Path(__file__).resolve().parents[2] / SettingsFormMixin._PREFLIGHT_PRESETS_DIRNAME

    def _load_recommended_preflights(self) -> list[tuple[str, str]]:
        scripts_dir = self._recommended_preflights_dir()
        if not scripts_dir.is_dir():
            return []

        presets: list[tuple[str, str]] = []
        for file_path in scripts_dir.iterdir():
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in self._PREFLIGHT_PRESET_SUFFIXES:
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
            except Exception:
                continue
            label = self._format_key_label(file_path.stem)
            presets.append((label, content))
        presets.sort(key=lambda item: item[0].lower())
        return presets

    def _populate_recommended_preflights(self) -> None:
        with QSignalBlocker(self._recommended_preflights):
            self._recommended_preflights.clear()
            self._recommended_preflights.addItem("Recommended preflights...", None)
            for label, content in self._load_recommended_preflights():
                self._recommended_preflights.addItem(label, content)
            self._recommended_preflights.setCurrentIndex(0)

    def _reset_recommended_preflight_selection(self) -> None:
        with QSignalBlocker(self._recommended_preflights):
            self._recommended_preflights.setCurrentIndex(0)

    def _on_recommended_preflight_selected(self, index: int) -> None:
        if index <= 0:
            return

        preset_script = str(self._recommended_preflights.itemData(index) or "")
        if not preset_script.strip():
            self._reset_recommended_preflight_selection()
            return

        current_script = str(self._preflight_script.toPlainText() or "")
        should_replace = True
        if current_script.strip():
            should_replace = (
                QMessageBox.question(
                    None,
                    "Replace preflight script?",
                    "Would you like to replace what you have with the recommended preflight?",
                )
                == QMessageBox.StandardButton.Yes
            )

        if should_replace:
            self._preflight_script.setPlainText(preset_script)
            self._refresh_preflight_script_highlighting(preset_script)
        self._reset_recommended_preflight_selection()

    def get_settings(self) -> dict[str, Any]:
        poll_startup_delay_text = str(self._github_poll_startup_delay_s.text() or "35").strip()
        try:
            poll_startup_delay_s = max(0, int(poll_startup_delay_text or "35"))
        except Exception:
            poll_startup_delay_s = 35
        return {
            "use": str(self._use.currentData() or get_default_agent_system_name()),
            "shell": str(self._shell.currentData() or "bash"),
            "opencode_interactive_mode": normalize_opencode_interactive_mode(
                str(self._opencode_interactive_mode.currentData() or "terminal")
            ),
            "interactive_terminal_id": str(self._interactive_terminal.currentData() or ""),
            "ui_theme": normalize_ui_theme_name(str(self._ui_theme.currentData() or "auto"), allow_auto=True),
            "popup_theme_animation_enabled": bool(self._popup_theme_animation_enabled.isChecked()),
            "preflight_enabled": bool(self._preflight_enabled.isChecked()),
            "preflight_script": str(self._preflight_script.toPlainText() or ""),
            "append_pixelarch_context": bool(self._append_pixelarch_context.isChecked()),
            "github_workroom_prefer_browser": bool(self._github_workroom_prefer_browser.isChecked()),
            "github_write_confirmation_mode": str(self._github_write_confirmation_mode.currentData() or "always"),
            "agentsnova_auto_review_enabled": bool(self._agentsnova_auto_review_enabled.isChecked()),
            "agentsnova_auto_marker_comments_mode": (
                normalize_default_marker_comment_mode(self._agentsnova_auto_marker_comments_mode.currentData())
            ),
            "agentsnova_auto_reactions_enabled": bool(self._agentsnova_auto_reactions_enabled.isChecked()),
            "github_polling_enabled": bool(self._github_polling_enabled.isChecked()),
            "github_poll_startup_delay_s": poll_startup_delay_s,
            "agentsnova_trusted_users_global": self._agentsnova_trusted_users_global.get_usernames(),
            "headless_desktop_enabled": bool(self._headless_desktop_enabled.isChecked()),
            "gpu_enabled": bool(self._gpu_enabled.isChecked()),
            "network_host": bool(self._network_host.isChecked()),
            "auto_navigate_on_run_agent_start": bool(self._auto_navigate_on_run_agent_start.isChecked()),
            "auto_navigate_on_run_interactive_start": bool(self._auto_navigate_on_run_interactive_start.isChecked()),
            "gh_context_default_enabled": bool(self._gh_context_default.isChecked()),
            "spellcheck_enabled": bool(self._spellcheck_enabled.isChecked()),
            "mount_host_cache": bool(self._mount_host_cache.isChecked()),
            "task_workspace_location": normalize_task_workspace_location(self._task_workspace_location.currentData()),
            "task_workspace_cleanup_retention_days": int(self._task_workspace_cleanup_retention_days.value()),
            "task_workspace_cleanup_interval_minutes": int(self._task_workspace_cleanup_interval_minutes.value()),
            "task_workspace_cleanup_scan_delay_seconds": int(self._task_workspace_cleanup_scan_delay_seconds.value()),
            "task_workspace_cleanup_size_threshold_gb": int(self._task_workspace_cleanup_size_threshold_gb.value()),
            "radio_enabled": bool(self._radio_enabled.isChecked()),
            "radio_autostart": bool(self._radio_autostart.isChecked()),
            "radio_channel": RadioController.normalize_channel(str(self._radio_channel.currentData() or "")),
            "radio_quality": RadioController.normalize_quality(str(self._radio_quality.currentData() or "medium")),
            "radio_volume": RadioController.clamp_volume(self._radio_volume.value()),
            "radio_loudness_boost_enabled": bool(self._radio_loudness_boost_enabled.isChecked()),
            "radio_loudness_boost_factor": (
                RadioController.normalize_loudness_boost_factor(self._radio_loudness_boost_factor.value())
            ),
        }

    @staticmethod
    def _clamp_spin_value(value: object, *, minimum: int, maximum: int, default: int) -> int:
        try:
            parsed = int(str(value).strip())
        except Exception:
            parsed = default
        return max(minimum, min(maximum, parsed))

    def _refresh_task_workspace_controls(self, *_args: object) -> None:
        self._start_workspace_status_check()

    def _start_workspace_status_check(self) -> None:
        self._workspace_status_request_id += 1
        request_id = int(self._workspace_status_request_id)
        self._set_workspace_status_checking(True)
        if bool(getattr(self, "_workspace_status_running", False)):
            self._workspace_status_pending = True
            return
        self._launch_workspace_status_check(request_id)

    def _launch_workspace_status_check(self, request_id: int) -> None:
        worker = _WorkspaceStatusWorker(request_id)
        self._workspace_status_running = True
        self._workspace_status_worker = worker
        worker.finished.connect(self._on_workspace_status_check_finished)
        worker.start()

    def _on_workspace_status_check_finished(self, request_id: int, status: object) -> None:
        self._workspace_status_running = False
        worker = getattr(self, "_workspace_status_worker", None)
        if worker is not None:
            worker.deleteLater()
        self._workspace_status_worker = None
        if bool(getattr(self, "_workspace_status_pending", False)):
            self._workspace_status_pending = False
            self._launch_workspace_status_check(int(getattr(self, "_workspace_status_request_id", 0)))
            return
        if int(request_id) != int(getattr(self, "_workspace_status_request_id", 0)):
            return
        if not isinstance(status, ScratchDriveStatus):
            self._set_workspace_status_checking(False)
            return
        self._scratch_drive_latest_status = status
        self._set_workspace_status_checking(False)
        self._apply_task_workspace_status(status)

    def _set_workspace_status_checking(self, checking: bool) -> None:
        checking = bool(checking)
        self._workspace_status_checking = checking
        self._task_workspace_location.setEnabled(not checking)
        for widget in self._task_workspace_cleanup_controls:
            widget.setEnabled(not checking)
        self._task_workspace_cleanup_note.setText("")
        self._task_workspace_cleanup_note.setVisible(False)
        self._task_workspace_cleanup_size_ram_cap_label.setText("")
        self._task_workspace_cleanup_size_ram_cap_label.setVisible(False)
        self._scratch_drive_status.setText("")
        self._workspace_status_spinner.setVisible(checking)
        if checking:
            self._workspace_status_spinner.start()
        else:
            self._workspace_status_spinner.stop()
        scratch_selected = (
            normalize_task_workspace_location(self._task_workspace_location.currentData())
            == TASK_WORKSPACE_LOCATION_SCRATCH_DRIVE
        )
        status_visible = bool(checking or scratch_selected)
        self._scratch_drive_status_row.setVisible(status_visible)
        if hasattr(self, "_scratch_drive_status_label"):
            self._scratch_drive_status_label.setVisible(status_visible)
        self._refresh_move_task_workspaces_button()

    def _apply_task_workspace_status(self, status: ScratchDriveStatus) -> None:
        location = normalize_task_workspace_location(self._task_workspace_location.currentData())
        scratch_selected = location == TASK_WORKSPACE_LOCATION_SCRATCH_DRIVE
        self._scratch_drive_status_row.setVisible(scratch_selected)
        self._scratch_drive_status.setVisible(scratch_selected)
        if hasattr(self, "_scratch_drive_status_label"):
            self._scratch_drive_status_label.setVisible(scratch_selected)

        if not status.exists_or_creatable:
            scratch_text = "Scratch drive is not ready."
        elif not status.is_ram_drive:
            scratch_text = "Scratch drive is not a RAM drive."
        elif not status.has_recommended_space:
            scratch_text = "Scratch drive has less than 16 GiB free."
        elif status.is_ram_drive:
            scratch_text = "Scratch data is ready. Storage clears on reboot."
        else:
            scratch_text = "Scratch drive is ready."
        self._scratch_drive_status.setText(scratch_text)
        self._scratch_drive_status.setToolTip(
            f"{status.path}\n"
            f"RAM drive (tmpfs): {'yes' if status.is_ram_drive else 'no'}\n"
            f"Free: {status.free_gib:.1f} GiB"
        )

        if scratch_selected and status.is_ram_drive:
            try:
                with open("/proc/meminfo", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            parts = line.split()
                            if len(parts) >= 2:
                                mem_total_kb = int(parts[1])
                                system_ram_gb = mem_total_kb / 1048576.0
                                spinbox_value = int(self._task_workspace_cleanup_size_threshold_gb.value())
                                effective_cap_gb = max(1, min(spinbox_value, int(system_ram_gb * 0.5)))
                                self._task_workspace_cleanup_size_ram_cap_label.setText(
                                    f"Effective cap: {effective_cap_gb} GB (50% of system RAM)"
                                )
                                self._task_workspace_cleanup_size_ram_cap_label.setVisible(True)
                            break
            except Exception:
                self._task_workspace_cleanup_size_ram_cap_label.setText("")
                self._task_workspace_cleanup_size_ram_cap_label.setVisible(False)
        else:
            self._task_workspace_cleanup_size_ram_cap_label.setText("")
            self._task_workspace_cleanup_size_ram_cap_label.setVisible(False)

        cleanup_disabled = bool(scratch_selected and status.is_ram_drive)
        for widget in self._task_workspace_cleanup_controls:
            widget.setEnabled(not cleanup_disabled)
        if cleanup_disabled:
            self._task_workspace_cleanup_note.setText("Cleanup is not needed while Scratch drive is using a RAM drive.")
            self._task_workspace_cleanup_note.setVisible(True)
        elif scratch_selected:
            self._task_workspace_cleanup_note.setText(
                "Scratch drive is not a RAM drive, so cleanup settings still apply."
            )
            self._task_workspace_cleanup_note.setVisible(True)
        else:
            self._task_workspace_cleanup_note.setText("")
            self._task_workspace_cleanup_note.setVisible(False)
        self._refresh_move_task_workspaces_button()

    def _refresh_move_task_workspaces_button(self) -> None:
        blocked = bool(getattr(self, "_task_workspace_migration_blocked", False))
        checking = bool(getattr(self, "_workspace_status_checking", False))
        self._move_task_workspaces.setEnabled(not blocked and not checking)
        if blocked:
            self._move_task_workspaces.setToolTip("Active tasks must finish first.")
        else:
            self._move_task_workspaces.setToolTip("Moves cloned task workspaces to the selected location.")
        force_tint = bool(
            getattr(self, "_move_task_workspaces_shift_pressed", False) and self._move_task_workspaces.isEnabled()
        )
        self._move_task_workspaces.setStyleSheet(
            (
                "QToolButton { border: 1px solid rgba(244, 63, 94, 130); "
                "background-color: rgba(244, 63, 94, 62); }"
                "QToolButton:hover { background-color: rgba(244, 63, 94, 76); }"
            )
            if force_tint
            else ""
        )

    def set_task_workspace_migration_blocked(self, blocked: bool) -> None:
        self._task_workspace_migration_blocked = bool(blocked)
        if hasattr(self, "_move_task_workspaces"):
            self._refresh_move_task_workspaces_button()

    def _on_move_task_workspaces(self) -> None:
        modifiers = QApplication.keyboardModifiers()
        force = bool(
            getattr(self, "_move_task_workspaces_shift_pressed", False)
            or getattr(self, "_move_task_workspaces_shift_click_force", False)
            or modifiers & Qt.KeyboardModifier.ShiftModifier
        )
        self._move_task_workspaces_shift_click_force = False
        self.move_task_workspaces_requested.emit(force)

    def eventFilter(self, watched: QObject, event: QEvent, /) -> bool:
        if not cast(QWidget, self).isVisible():
            self._set_move_task_workspaces_shift_pressed(False)
            return QObject.eventFilter(cast(QObject, self), watched, event)  # pyright: ignore[reportUnknownVariableType]
        if event.type() in {QEvent.Type.KeyPress, QEvent.Type.KeyRelease}:
            self._update_move_task_workspaces_shift_state(event)
        elif event.type() in {
            QEvent.Type.ApplicationDeactivate,
            QEvent.Type.WindowDeactivate,
        }:
            self._set_move_task_workspaces_shift_pressed(False)
        if watched is getattr(self, "_move_task_workspaces", None):
            if event.type() == QEvent.Type.MouseButtonPress and isinstance(event, QMouseEvent):
                self._move_task_workspaces_shift_click_force = bool(
                    event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                )
                if self._move_task_workspaces_shift_click_force:
                    self._set_move_task_workspaces_shift_pressed(True)
            if event.type() in {
                QEvent.Type.Enter,
                QEvent.Type.Leave,
                QEvent.Type.MouseMove,
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonRelease,
            }:
                self._refresh_move_task_workspaces_button()
        return QObject.eventFilter(cast(QObject, self), watched, event)  # pyright: ignore[reportUnknownVariableType]

    def keyPressEvent(self, event: QKeyEvent, /) -> None:
        QWidget.keyPressEvent(cast(QWidget, self), event)
        self._update_move_task_workspaces_shift_state(event)

    def keyReleaseEvent(self, event: QKeyEvent, /) -> None:
        QWidget.keyReleaseEvent(cast(QWidget, self), event)
        self._update_move_task_workspaces_shift_state(event)

    def _update_move_task_workspaces_shift_state(self, event: QEvent) -> None:
        if not isinstance(event, QKeyEvent):
            return
        if event.key() != Qt.Key.Key_Shift:
            return
        self._set_move_task_workspaces_shift_pressed(event.type() == QEvent.Type.KeyPress)

    def _set_move_task_workspaces_shift_pressed(self, pressed: bool) -> None:
        pressed = bool(pressed)
        if getattr(self, "_move_task_workspaces_shift_pressed", False) == pressed:
            return
        self._move_task_workspaces_shift_pressed = pressed
        self._refresh_move_task_workspaces_button()

    def _start_move_task_workspaces_shift_polling(self) -> None:
        if not self._move_task_workspaces_shift_poll_timer.isActive():
            self._move_task_workspaces_shift_poll_timer.start()
        self._poll_move_task_workspaces_shift_state()

    def _stop_move_task_workspaces_shift_polling(self) -> None:
        self._move_task_workspaces_shift_poll_timer.stop()
        self._move_task_workspaces_shift_click_force = False
        self._set_move_task_workspaces_shift_pressed(False)

    def _poll_move_task_workspaces_shift_state(self) -> None:
        if not cast(QWidget, self).isVisible():
            self._stop_move_task_workspaces_shift_polling()
            return
        modifiers = QApplication.keyboardModifiers()
        self._set_move_task_workspaces_shift_pressed(bool(modifiers & Qt.KeyboardModifier.ShiftModifier))

    def _on_application_state_changed(self, state: object) -> None:
        if state != Qt.ApplicationState.ApplicationActive:
            self._set_move_task_workspaces_shift_pressed(False)

    def _on_setup_global_github_defaults(self) -> None:
        environments = load_environments().values()
        seeded = collect_seed_usernames_for_cloned_environments(environments)
        if not seeded:
            return
        self._agentsnova_trusted_users_global.merge_usernames(seeded)
        try:
            self._queue_debounced_autosave()
        except Exception:
            pass

    def _refresh_terminal_options(self, *, selected_terminal_id: str) -> None:
        selected_id = str(selected_terminal_id or "").strip()
        current_id = str(self._interactive_terminal.currentData() or "").strip()
        options = detect_terminal_options()

        with QSignalBlocker(self._interactive_terminal):
            self._interactive_terminal.clear()
            if not options:
                self._interactive_terminal.addItem("No terminals detected", "")
                self._interactive_terminal.setCurrentIndex(0)
                return

            for option in options:
                self._interactive_terminal.addItem(option.label, option.terminal_id)

            desired = selected_id or current_id
            if not desired:
                desired = str(options[0].terminal_id or "").strip()
            self._set_combo_value(
                self._interactive_terminal,
                desired,
                fallback=str(options[0].terminal_id or "").strip(),
            )

    def _on_refresh_terminal_options_clicked(self) -> None:
        self._refresh_terminal_options(selected_terminal_id=str(self._interactive_terminal.currentData() or "").strip())
        self._queue_debounced_autosave()

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: str, fallback: str) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return
        idx = combo.findData(fallback)
        if idx >= 0:
            combo.setCurrentIndex(idx)
