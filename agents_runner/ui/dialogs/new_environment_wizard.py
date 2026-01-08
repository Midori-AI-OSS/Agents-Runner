from __future__ import annotations

import hashlib
import os
import re
import shutil
from uuid import uuid4

from PySide6.QtCore import Signal, QTimer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from agents_runner.environments import (
    Environment, GH_MANAGEMENT_LOCAL, GH_MANAGEMENT_GITHUB, save_environment,
    load_environments, delete_environment,
)
from agents_runner.terminal_apps import detect_terminal_options, launch_in_terminal
from agents_runner.widgets import GlassCard


class NewEnvironmentWizard(QDialog):
    environment_created = Signal(object)

    TEST_DIR_BASE = "/tmp/agent-runner-env-test"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._clone_test_passed = False
        self._test_folder = ""
        self._advanced_modified = False
        self._clone_check_count = 0
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

    def _setup_step1(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        card = GlassCard()
        card_layout = QVBoxLayout(card)

        title = QLabel("Step 1: General Info")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        card_layout.addWidget(title)

        card_layout.addWidget(QLabel("Environment Name:"))
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("e.g., 'My Repo (Remote)'")
        card_layout.addWidget(self._name_input)
        helper = QLabel("A label you'll recognize later (e.g. 'My Repo (Remote)').")
        helper.setStyleSheet("color: #aaa; font-size: 11px; margin-bottom: 10px;")
        card_layout.addWidget(helper)

        card_layout.addWidget(QLabel("Workspace Source Type:"))
        self._source_combo = QComboBox()
        self._source_combo.addItem("Use a folder workspace")
        self._source_combo.addItem("Clone a repo workspace")
        self._source_combo.currentIndexChanged.connect(self._on_source_changed)
        card_layout.addWidget(self._source_combo)
        helper2 = QLabel("Both run in a container; this only changes the workspace source.")
        helper2.setStyleSheet("color: #aaa; font-size: 11px; margin-bottom: 10px;")
        card_layout.addWidget(helper2)

        self._description_label = QLabel()
        self._description_label.setWordWrap(True)
        self._description_label.setStyleSheet("margin-bottom: 10px; padding: 8px; background: rgba(255,255,255,0.05);")
        card_layout.addWidget(self._description_label)

        self._input_container = QWidget()
        self._input_layout = QVBoxLayout(self._input_container)
        self._input_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.addWidget(self._input_container)

        # Folder widgets
        self._folder_widget = QWidget()
        f_layout = QVBoxLayout(self._folder_widget)
        f_layout.setContentsMargins(0, 0, 0, 0)
        f_layout.addWidget(QLabel("Folder Path:"))
        f_row = QHBoxLayout()
        self._folder_input = QLineEdit()
        self._folder_input.textChanged.connect(self._validate_folder)
        f_row.addWidget(self._folder_input)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_folder)
        f_row.addWidget(browse_btn)
        f_layout.addLayout(f_row)
        self._folder_validation = QLabel()
        self._folder_validation.setStyleSheet("font-size: 11px; margin-top: 5px;")
        f_layout.addWidget(self._folder_validation)

        # Clone widgets
        self._clone_widget = QWidget()
        c_layout = QVBoxLayout(self._clone_widget)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.addWidget(QLabel("Repository URL:"))
        self._clone_input = QLineEdit()
        self._clone_input.setPlaceholderText("https://github.com/user/repo.git")
        self._clone_input.textChanged.connect(self._validate_clone)
        c_layout.addWidget(self._clone_input)
        self._clone_validation = QLabel()
        self._clone_validation.setStyleSheet("font-size: 11px; margin-top: 5px;")
        c_layout.addWidget(self._clone_validation)

        self._input_layout.addWidget(self._folder_widget)
        self._input_layout.addWidget(self._clone_widget)

        card_layout.addStretch()
        warning = QLabel("⚠ Step 1 choices (workspace source + path/URL) cannot be edited later. To change them, create a new environment.")
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #ff9800; font-weight: bold; margin-top: 20px; padding: 10px; background: rgba(255,152,0,0.1);")
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

    def _on_source_changed(self, index: int) -> None:
        is_folder = index == 0
        self._folder_widget.setVisible(is_folder)
        self._clone_widget.setVisible(not is_folder)
        if is_folder:
            self._description_label.setText("Uses an existing folder as the workspace (edits apply to that folder).")
            self._validate_folder()
        else:
            self._description_label.setText("Clones a repo into a new workspace each run (great for parallel runs).")
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

    def _validate_clone(self) -> None:
        url = self._clone_input.text().strip()
        if not url:
            self._clone_validation.setText("")
            self._update_next_button()
            return
        url_pattern = r'^(https?://|git@|ssh://)'
        if not re.match(url_pattern, url):
            self._clone_validation.setText("✗ Must be a valid URL (https://, git@, or ssh://)")
            self._clone_validation.setStyleSheet("color: #f44336; font-size: 11px;")
            self._update_next_button()
            return
        self._clone_validation.setText("✓ Valid URL format")
        self._clone_validation.setStyleSheet("color: #4caf50; font-size: 11px;")
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
            if not url:
                return False
            return bool(re.match(r'^(https?://|git@|ssh://)', url))

    def _on_next(self) -> None:
        if self._source_combo.currentIndex() == 1 and not self._clone_test_passed:
            self._run_clone_test()
            return
        if not self._validate_step1():
            return
        self._stack.setCurrentIndex(1)

    def _run_clone_test(self) -> None:
        url = self._clone_input.text().strip()
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
            gh_mode = GH_MANAGEMENT_LOCAL
            gh_target = self._folder_input.text().strip()
        else:
            gh_mode = GH_MANAGEMENT_GITHUB
            gh_target = self._clone_input.text().strip()
        env = Environment(
            env_id=env_id,
            name=name,
            gh_management_mode=gh_mode,
            gh_management_target=gh_target,
            gh_management_locked=True,
            headless_desktop_enabled=self._headless_check.isChecked(),
            container_caching_enabled=self._caching_check.isChecked(),
            gh_context_enabled=self._gh_context_check.isChecked(),
        )
        return env
