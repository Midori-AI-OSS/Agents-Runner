from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTabWidget
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.environments import Environment
from agents_runner.environments import resolve_environment_github_repo
from agents_runner.ui.pages.github_work_list import GitHubWorkListPage
from agents_runner.ui.pages.new_task import NewTaskPage


class TasksPage(QWidget):
    auto_review_requested = Signal(str, str)

    def __init__(
        self,
        *,
        new_task_page: NewTaskPage,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._new_task = new_task_page
        self._environments: dict[str, Environment] = {}
        self._active_env_id = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.tabBar().setDrawBase(False)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._prs = GitHubWorkListPage(item_type="pr")
        self._issues = GitHubWorkListPage(item_type="issue")

        self._new_task_tab_index = self._tabs.addTab(self._new_task, "New Task")
        self._pr_tab_index = self._tabs.addTab(self._prs, "Pull Requests")
        self._issues_tab_index = self._tabs.addTab(self._issues, "Issues")

        self._new_task.environment_changed.connect(
            self._on_new_task_environment_changed
        )
        self._prs.environment_changed.connect(self._on_work_environment_changed)
        self._issues.environment_changed.connect(self._on_work_environment_changed)

        self._prs.prompt_append_requested.connect(self._append_prompt_to_new_task)
        self._issues.prompt_append_requested.connect(self._append_prompt_to_new_task)

        self._prs.auto_review_requested.connect(self.auto_review_requested.emit)
        self._issues.auto_review_requested.connect(self.auto_review_requested.emit)

        layout.addWidget(self._tabs, 1)
        self._set_work_tabs_visible(False)

    def _set_work_tabs_visible(self, visible: bool) -> None:
        tab_bar = self._tabs.tabBar()
        if hasattr(tab_bar, "setTabVisible"):
            tab_bar.setTabVisible(self._pr_tab_index, bool(visible))
            tab_bar.setTabVisible(self._issues_tab_index, bool(visible))
        else:
            self._tabs.setTabEnabled(self._pr_tab_index, bool(visible))
            self._tabs.setTabEnabled(self._issues_tab_index, bool(visible))

        if not visible and self._tabs.currentIndex() != self._new_task_tab_index:
            self._tabs.setCurrentIndex(self._new_task_tab_index)

        self._on_tab_changed(self._tabs.currentIndex())

    def _on_tab_changed(self, index: int) -> None:
        self._prs.set_polling_enabled(index == self._pr_tab_index)
        self._issues.set_polling_enabled(index == self._issues_tab_index)

    def _sync_visibility_for_active_environment(self) -> None:
        env = self._environments.get(self._active_env_id)
        is_supported = resolve_environment_github_repo(env) is not None
        self._set_work_tabs_visible(is_supported)

    def set_environments(self, envs: dict[str, Environment], active_id: str) -> None:
        self._environments = dict(envs or {})
        self._active_env_id = str(active_id or "").strip()

        self._prs.set_environments(self._environments, self._active_env_id)
        self._issues.set_environments(self._environments, self._active_env_id)

        self._sync_visibility_for_active_environment()

    def set_settings_data(self, settings_data: dict[str, object]) -> None:
        self._prs.set_settings_data(settings_data)
        self._issues.set_settings_data(settings_data)

    def show_new_task_tab(self, *, focus_prompt: bool = True) -> None:
        self._tabs.setCurrentIndex(self._new_task_tab_index)
        if focus_prompt:
            self._new_task.focus_prompt()

    def _append_prompt_to_new_task(self, env_id: str, prompt: str) -> None:
        target_env_id = str(env_id or "").strip()
        if target_env_id:
            self._new_task.set_environment_id(target_env_id)

        self._new_task.append_prompt_text(prompt)
        self.show_new_task_tab(focus_prompt=True)

    def _on_new_task_environment_changed(self, env_id: str) -> None:
        env_id = str(env_id or "").strip()
        self._active_env_id = env_id
        self._prs.set_active_environment_id(env_id)
        self._issues.set_active_environment_id(env_id)
        self._sync_visibility_for_active_environment()

    def _on_work_environment_changed(self, env_id: str) -> None:
        env_id = str(env_id or "").strip()
        if env_id:
            self._new_task.set_environment_id(env_id)

    def is_new_task_tab_active(self) -> bool:
        return self._tabs.currentIndex() == self._new_task_tab_index
