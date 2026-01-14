from __future__ import annotations

import hashlib
import os
import random
import re
import shutil
from uuid import uuid4

from PySide6.QtCore import Signal, QTimer
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from agents_runner.environments import (
    ALLOWED_STAINS,
    Environment, save_environment,
    load_environments, delete_environment,
    WORKSPACE_CLONED, WORKSPACE_MOUNTED,
)
from agents_runner.terminal_apps import detect_terminal_options, launch_in_terminal
from agents_runner.ui.graphics import _EnvironmentTintOverlay
from agents_runner.ui.utils import _apply_environment_combo_tint, _stain_color
from agents_runner.widgets import GlassCard


class NewEnvironmentWizard(QDialog):
    environment_created = Signal(object)

    TEST_DIR_BASE = "/tmp/agent-runner-env-test"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("NewEnvironmentWizard")
        self.setStyleSheet(
            "\n".join(
                [
                    "#NewEnvironmentWizard {",
                    "  background-color: rgba(10, 12, 18, 255);",
                    "}",
                ]
            )
        )
        self._clone_test_passed = False
        self._test_folder = ""
        self._advanced_modified = False
        self._clone_check_count = 0
        self._suggested_color: str = self._pick_new_environment_color()
        self.setWindowTitle("New Environment Wizard")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        layout = QVBoxLayout(self)
        self._stack = QStackedWidget()
        layout.addWidget(self._stack)
        self._step1_widget = self._setup_step1()
        self._step2_widget = self._setup_step2()
        self._stack.addWidget(self._step1_widget)
        self._stack.addWidget(self._step2_widget)
        self._stack.setCurrentIndex(0)
        self._tint_overlay = _EnvironmentTintOverlay(self, alpha=22)
        self._tint_overlay.setGeometry(self.rect())
        self._tint_overlay.raise_()
        self._apply_environment_tint()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._tint_overlay.setGeometry(self.rect())
        self._tint_overlay.raise_()

    def _setup_step1(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        card = GlassCard()
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(8)

        title = QLabel("Step 1: General Info")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        card_layout.addWidget(title)

        # Environment Name with tooltip
        name_label = QLabel("Environment Name:")
        name_label.setToolTip("A label you'll recognize later (e.g., 'My Repo (Remote)')")
        card_layout.addWidget(name_label)
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("e.g., 'My Repo (Remote)'")
        self._name_input.setToolTip("A label you'll recognize later (e.g., 'My Repo (Remote)')")
        self._name_input.textChanged.connect(self._update_next_button)
        card_layout.addWidget(self._name_input)

        # Workspace Source Type with tooltip
        source_label = QLabel("Workspace Source Type:")
        source_label.setToolTip("Both run in a container; this only changes the workspace source")
        card_layout.addWidget(source_label)
        self._source_combo = QComboBox()
        self._source_combo.addItem("Use a folder workspace")
        self._source_combo.addItem("Clone a repo workspace")
        self._source_combo.setToolTip("Folder: uses existing folder (edits apply there). Repo: clones fresh workspace each run")
        self._source_combo.currentIndexChanged.connect(self._on_source_changed)
        card_layout.addWidget(self._source_combo)

        self._input_container = QWidget()
        self._input_layout = QVBoxLayout(self._input_container)
        self._input_layout.setContentsMargins(0, 0, 0, 0)
        self._input_layout.setSpacing(8)
        card_layout.addWidget(self._input_container)

        # Folder widgets
        self._folder_widget = QWidget()
        f_layout = QVBoxLayout(self._folder_widget)
        f_layout.setContentsMargins(0, 0, 0, 0)
        f_layout.setSpacing(4)
        folder_label = QLabel("Folder Path:")
        folder_label.setToolTip("Path to an existing folder that will be used as the workspace")
        f_layout.addWidget(folder_label)
        f_row = QHBoxLayout()
        f_row.setSpacing(4)
        self._folder_input = QLineEdit()
        self._folder_input.setToolTip("Path to an existing folder that will be used as the workspace")
        self._folder_input.textChanged.connect(self._validate_folder)
        f_row.addWidget(self._folder_input, 1)
        browse_btn = QPushButton("Browse...")
        f_row.addWidget(browse_btn, 0)
        browse_btn.clicked.connect(self._browse_folder)
        f_layout.addLayout(f_row)
        self._folder_validation = QLabel()
        self._folder_validation.setStyleSheet("font-size: 11px;")
        f_layout.addWidget(self._folder_validation)

        # Clone widgets
        self._clone_widget = QWidget()
        c_layout = QVBoxLayout(self._clone_widget)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(4)
        repo_label = QLabel("Repository URL:")
        repo_label.setToolTip("GitHub shorthand (owner/repo) or full URL (https://github.com/owner/repo.git)")
        c_layout.addWidget(repo_label)
        self._clone_input = QLineEdit()
        self._clone_input.setPlaceholderText("owner/repo or full URL")
        self._clone_input.setToolTip("GitHub shorthand (owner/repo) or full URL (https://github.com/owner/repo.git)")
        self._clone_input.textChanged.connect(self._validate_clone)
        c_layout.addWidget(self._clone_input)
        self._clone_validation = QLabel()
        self._clone_validation.setStyleSheet("font-size: 11px;")
        c_layout.addWidget(self._clone_validation)

        self._input_layout.addWidget(self._folder_widget)
        self._input_layout.addWidget(self._clone_widget)

        card_layout.addStretch()
        warning = QLabel("⚠ Step 1 choices (workspace source + path/URL) cannot be edited later. To change them, create a new environment.")
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #ff9800; font-weight: bold; margin-top: 10px; padding: 8px; background: rgba(255,152,0,0.1);")
        card_layout.addWidget(warning)
        layout.addWidget(card)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self._cancel_btn)
        self._back_btn = QPushButton("Back")
        self._back_btn.setEnabled(False)
        self._back_btn.clicked.connect(self._on_back)
        btn_layout.addWidget(self._back_btn)
        self._next_btn = QPushButton("Next")
        self._next_btn.clicked.connect(self._on_next)
        btn_layout.addWidget(self._next_btn)
        layout.addLayout(btn_layout)
        self._on_source_changed(0)
        return widget

    def _setup_step2(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        card = GlassCard()
        card_layout = QVBoxLayout(card)

        title = QLabel("Step 2: Advanced Options")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        card_layout.addWidget(title)
        desc = QLabel("Configure advanced environment settings:")
        desc.setStyleSheet("margin-bottom: 15px;")
        card_layout.addWidget(desc)

        color_row = QHBoxLayout()
        color_label = QLabel("Color:")
        color_label.setToolTip("Used for identifying environments in the UI")
        color_row.addWidget(color_label)
        self._color_combo = QComboBox()
        self._color_combo.setToolTip("Used for identifying environments in the UI")
        for stain in ALLOWED_STAINS:
            self._color_combo.addItem(stain.title(), stain)
        idx = self._color_combo.findData(self._suggested_color)
        if idx >= 0:
            self._color_combo.blockSignals(True)
            try:
                self._color_combo.setCurrentIndex(idx)
            finally:
                self._color_combo.blockSignals(False)
        self._color_combo.currentIndexChanged.connect(self._on_color_changed)
        color_row.addWidget(self._color_combo, 1)
        card_layout.addLayout(color_row)

        self._headless_check = QCheckBox("Enable headless desktop")
        self._headless_check.stateChanged.connect(self._on_advanced_changed)
        card_layout.addWidget(self._headless_check)
        self._caching_check = QCheckBox("Enable container caching")
        self._caching_check.stateChanged.connect(self._on_advanced_changed)
        card_layout.addWidget(self._caching_check)
        self._gh_context_check = QCheckBox("Enable GitHub context")
        self._gh_context_check.stateChanged.connect(self._on_advanced_changed)
        card_layout.addWidget(self._gh_context_check)
        card_layout.addStretch()

        note = QLabel("You can change these later in Environments.")
        note.setStyleSheet("color: #aaa; font-size: 10px; margin-top: 20px;")
        card_layout.addWidget(note)
        layout.addWidget(card)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._cancel_btn2 = QPushButton("Cancel")
        self._cancel_btn2.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self._cancel_btn2)
        self._back_btn2 = QPushButton("Back")
        self._back_btn2.clicked.connect(self._on_back)
        btn_layout.addWidget(self._back_btn2)
        self._finish_btn = QPushButton("Skip")
        self._finish_btn.clicked.connect(self._on_finish)
        btn_layout.addWidget(self._finish_btn)
        layout.addLayout(btn_layout)
        return widget

    def _current_stain(self) -> str:
        combo = getattr(self, "_color_combo", None)
        stain = str(combo.currentData() or "").strip().lower() if combo is not None else ""
        return stain or str(self._suggested_color or "").strip().lower()

    def _apply_environment_tint(self) -> None:
        if not hasattr(self, "_tint_overlay"):
            return
        stain = self._current_stain()
        if not stain:
            self._tint_overlay.set_tint_color(None)
            return
        self._tint_overlay.set_tint_color(_stain_color(stain))
        if hasattr(self, "_color_combo"):
            _apply_environment_combo_tint(self._color_combo, stain)

    def _on_source_changed(self, index: int) -> None:
        is_folder = index == 0
        self._folder_widget.setVisible(is_folder)
        self._clone_widget.setVisible(not is_folder)
        if is_folder:
            self._validate_folder()
        else:
            self._validate_clone()
            self._clone_test_passed = False
        self._update_next_button()

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Workspace Folder")
        if folder:
            self._folder_input.setText(folder)

    def _validate_folder(self) -> None:
        path = self._folder_input.text().strip()
        if not path:
            self._folder_validation.setText("")
            return
        if not os.path.exists(path):
            self._folder_validation.setText("✗ Path does not exist")
            self._folder_validation.setStyleSheet("color: #f44336; font-size: 11px;")
            return
        if not os.path.isdir(path):
            self._folder_validation.setText("✗ Path is not a directory")
            self._folder_validation.setStyleSheet("color: #f44336; font-size: 11px;")
            return
        if not os.access(path, os.R_OK):
            self._folder_validation.setText("✗ Path is not readable")
            self._folder_validation.setStyleSheet("color: #f44336; font-size: 11px;")
            return
        if not os.access(path, os.W_OK):
            self._folder_validation.setText("✗ Path is not writable")
            self._folder_validation.setStyleSheet("color: #f44336; font-size: 11px;")
            return
        self._folder_validation.setText("✓ Valid folder")
        self._folder_validation.setStyleSheet("color: #4caf50; font-size: 11px;")
        self._update_next_button()

    def _expand_repo_url(self, url: str) -> str:
        """Convert GitHub shorthand (owner/repo) to full URL."""
        url = url.strip()
        # Check if it's already a full URL
        if url.startswith(('https://', 'http://', 'git@', 'ssh://')):
            return url
        # Check if it matches GitHub shorthand pattern (owner/repo)
        if re.match(r'^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$', url):
            return f"https://github.com/{url}.git"
        return url

    def _validate_clone(self) -> None:
        url = self._clone_input.text().strip()
        if not url:
            self._clone_validation.setText("")
            self._update_next_button()
            return
        # Check for spaces (invalid)
        if ' ' in url:
            self._clone_validation.setText("✗ URL cannot contain spaces")
            self._clone_validation.setStyleSheet("color: #f44336; font-size: 11px;")
            self._update_next_button()
            return
        # Accept GitHub shorthand (owner/repo) or full URLs
        shorthand_pattern = r'^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$'
        url_pattern = r'^(https?://|git@|ssh://)'
        if re.match(shorthand_pattern, url) or re.match(url_pattern, url):
            self._clone_validation.setText("✓ Valid format")
            self._clone_validation.setStyleSheet("color: #4caf50; font-size: 11px;")
        else:
            self._clone_validation.setText("✗ Use owner/repo or valid URL (https://, git@, ssh://)")
            self._clone_validation.setStyleSheet("color: #f44336; font-size: 11px;")
        self._update_next_button()

    def _update_next_button(self) -> None:
        if self._source_combo.currentIndex() == 0:
            self._next_btn.setText("Next")
            self._next_btn.setEnabled(self._validate_step1())
        else:
            if self._clone_test_passed:
                self._next_btn.setText("Next")
                self._next_btn.setEnabled(True)
            else:
                name_valid = bool(self._name_input.text().strip())
                clone_valid = bool(self._clone_input.text().strip() and "✓" in self._clone_validation.text())
                self._next_btn.setText("Test")
                self._next_btn.setEnabled(name_valid and clone_valid)

    def _validate_step1(self) -> bool:
        if not self._name_input.text().strip():
            return False
        if self._source_combo.currentIndex() == 0:
            path = self._folder_input.text().strip()
            if not path or not os.path.isdir(path):
                return False
            if not os.access(path, os.R_OK | os.W_OK):
                return False
            return True
        else:
            url = self._clone_input.text().strip()
            if not url or ' ' in url:
                return False
            # Accept GitHub shorthand (owner/repo) or full URLs
            shorthand_pattern = r'^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$'
            url_pattern = r'^(https?://|git@|ssh://)'
            return bool(re.match(shorthand_pattern, url) or re.match(url_pattern, url))

    def _on_next(self) -> None:
        if self._source_combo.currentIndex() == 1 and not self._clone_test_passed:
            self._run_clone_test()
            return
        if not self._validate_step1():
            return
        self._stack.setCurrentIndex(1)

    def _run_clone_test(self) -> None:
        url = self._expand_repo_url(self._clone_input.text().strip())
        name = self._name_input.text().strip() or "test"
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', name)[:50]
        test_id = hashlib.md5(url.encode()).hexdigest()[:8]
        self._test_folder = os.path.join(self.TEST_DIR_BASE, f"{sanitized}-{test_id}")
        if os.path.exists(self._test_folder):
            shutil.rmtree(self._test_folder, ignore_errors=True)
        os.makedirs(self.TEST_DIR_BASE, exist_ok=True)
        self._clone_check_count = 0
        terminals = detect_terminal_options()
        if not terminals:
            self._clone_validation.setText("✗ No terminal found on system")
            self._clone_validation.setStyleSheet("color: #f44336; font-size: 11px;")
            self._next_btn.setText("Try test again")
            return
        script = f"""
echo "Testing git clone..."
echo "URL: {url}"
echo "Target: {self._test_folder}"
echo ""
git clone "{url}" "{self._test_folder}"
echo ""
echo "Test complete. Press Enter to close..."
read
"""
        terminal_launched = False
        for terminal in terminals:
            try:
                launch_in_terminal(terminal, script, cwd="/tmp")
                terminal_launched = True
                QTimer.singleShot(2000, self._check_clone_result)
                break
            except Exception:
                continue
        if not terminal_launched:
            self._clone_validation.setText("✗ Failed to launch terminal")
            self._clone_validation.setStyleSheet("color: #f44336; font-size: 11px;")
            self._next_btn.setText("Try test again")

    def _check_clone_result(self) -> None:
        self._clone_check_count += 1
        if os.path.isdir(self._test_folder) and os.path.isdir(os.path.join(self._test_folder, ".git")):
            self._clone_test_passed = True
            self._clone_validation.setText("✓ Clone test passed")
            self._clone_validation.setStyleSheet("color: #4caf50; font-size: 11px;")
            self._update_next_button()
        elif self._clone_check_count >= 30:
            self._clone_validation.setText("✗ Clone test timeout (60s)")
            self._clone_validation.setStyleSheet("color: #f44336; font-size: 11px;")
            self._next_btn.setText("Try test again")
        else:
            QTimer.singleShot(2000, self._check_clone_result)

    def _on_back(self) -> None:
        self._stack.setCurrentIndex(0)

    def _on_cancel(self) -> None:
        self.reject()

    def _on_advanced_changed(self) -> None:
        self._advanced_modified = True
        self._finish_btn.setText("OK")

    def _on_color_changed(self) -> None:
        self._apply_environment_tint()
        self._on_advanced_changed()

    def _on_finish(self) -> None:
        env = self._create_environment()
        save_environment(env)
        
        # Delete the "default" environment after creating a new one
        environments = load_environments()
        if "default" in environments and env.env_id != "default":
            delete_environment("default")
        
        self.environment_created.emit(env)
        self.accept()

    def _create_environment(self) -> Environment:
        env_id = f"env-{uuid4().hex[:8]}"
        name = self._name_input.text().strip()
        if self._source_combo.currentIndex() == 0:
            gh_target = self._folder_input.text().strip()
            workspace_type = WORKSPACE_MOUNTED
        else:
            gh_target = self._expand_repo_url(self._clone_input.text().strip())
            workspace_type = WORKSPACE_CLONED
        color = str(getattr(self, "_color_combo", None).currentData() or self._suggested_color)
        env = Environment(
            env_id=env_id,
            name=name,
            color=color,
            gh_management_locked=True,
            workspace_type=workspace_type,
            workspace_target=gh_target,
            headless_desktop_enabled=self._headless_check.isChecked(),
            container_caching_enabled=self._caching_check.isChecked(),
            gh_context_enabled=self._gh_context_check.isChecked(),
        )
        return env

    def _pick_new_environment_color(self) -> str:
        envs = load_environments()
        used = {env.normalized_color() for env in envs.values()}
        unused = [stain for stain in ALLOWED_STAINS if stain not in used]
        if unused and random.random() < 0.9:
            return random.choice(unused)
        return random.choice(ALLOWED_STAINS)
