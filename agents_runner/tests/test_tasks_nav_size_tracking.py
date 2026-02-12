from __future__ import annotations

import os

from PySide6.QtCore import QObject
from PySide6.QtCore import QEvent
from PySide6.QtCore import Signal
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QWidget

from agents_runner.environments import Environment
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.ui.pages.tasks import TasksPage

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _DummyNewTaskPage(QWidget):
    environment_changed = Signal(str)

    def focus_prompt(self) -> None:
        return

    def set_environment_id(self, _env_id: str) -> None:
        return

    def append_prompt_text(self, _prompt: str) -> None:
        return


class _SizeTracker(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.samples: list[tuple[bool, int, int]] = []

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Resize and isinstance(watched, QWidget):
            self.samples.append(
                (watched.isVisible(), watched.width(), watched.height())
            )
        return False


def _pump(app: QApplication, rounds: int = 8) -> None:
    for _ in range(rounds):
        app.processEvents()
        QTest.qWait(20)


def test_tasks_nav_panel_width_stays_stable_across_hide_show_cycles() -> None:
    app = QApplication.instance() or QApplication([])

    page = TasksPage(new_task_page=_DummyNewTaskPage())
    page.resize(1400, 900)

    env = Environment(
        env_id="ui-test",
        name="UI Test",
        color="cyan",
        workspace_type=WORKSPACE_CLONED,
        workspace_target="owner/repo",
    )
    page.set_environments({env.env_id: env}, env.env_id)

    panel_tracker = _SizeTracker()
    page._nav_panel.installEventFilter(panel_tracker)

    page.show()
    _pump(app)

    panel_widths: list[int] = [int(page._nav_panel.width())]

    page.hide()
    _pump(app, rounds=4)
    page.resize(760, 700)
    _pump(app, rounds=4)
    page.resize(1400, 900)
    _pump(app, rounds=4)

    page.show()
    _pump(app)
    panel_widths.append(int(page._nav_panel.width()))

    page.hide()
    _pump(app, rounds=4)
    page.show()
    _pump(app)
    panel_widths.append(int(page._nav_panel.width()))

    minimum = int(page._nav_panel.minimumWidth())
    maximum = int(page._nav_panel.maximumWidth())
    assert all(minimum <= width <= maximum for width in panel_widths), (
        f"nav panel width escaped bounds [{minimum}, {maximum}]: {panel_widths}"
    )

    settled_spread = max(panel_widths) - min(panel_widths)
    assert settled_spread <= 2, (
        f"nav panel settled width drifted across show/hide: {panel_widths}; "
        f"tracked={panel_tracker.samples}"
    )

    visible_panel_samples = [w for visible, w, _h in panel_tracker.samples if visible]
    if visible_panel_samples:
        spread = max(visible_panel_samples) - min(visible_panel_samples)
        assert spread <= 8, (
            f"nav panel width oscillated too much during resize events: "
            f"{visible_panel_samples}"
        )
