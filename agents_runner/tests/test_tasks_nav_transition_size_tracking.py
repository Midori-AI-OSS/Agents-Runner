from __future__ import annotations

import os

from PySide6.QtCore import QObject
from PySide6.QtCore import QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QWidget

from agents_runner.environments import Environment
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.ui.main_window import MainWindow

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _ResizeTracker(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.samples: list[tuple[bool, int, int]] = []

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Resize and isinstance(watched, QWidget):
            self.samples.append(
                (watched.isVisible(), watched.width(), watched.height())
            )
        return False


def _pump(app: QApplication, rounds: int = 15) -> None:
    for _ in range(rounds):
        app.processEvents()
        QTest.qWait(20)


def test_tasks_nav_width_stable_during_main_window_page_transitions() -> None:
    app = QApplication.instance() or QApplication([])

    win = MainWindow()
    win.resize(1280, 720)
    win.show()
    _pump(app)

    env = Environment(
        env_id="transition-test",
        name="Transition Test",
        color="cyan",
        workspace_type=WORKSPACE_CLONED,
        workspace_target="owner/repo",
    )
    win._tasks_page.set_environments({env.env_id: env}, env.env_id)
    _pump(app)

    tracker = _ResizeTracker()
    win._tasks_page._nav_host.installEventFilter(tracker)

    expected = int(win._tasks_page._nav_expanded_width)

    win._show_tasks()
    _pump(app, rounds=30)
    assert win._tasks_page.isVisible()
    assert int(win._tasks_page._nav_host.width()) == expected

    win._show_dashboard()
    _pump(app, rounds=30)
    assert win._dashboard.isVisible()

    win._show_tasks()
    _pump(app, rounds=30)
    assert win._tasks_page.isVisible()
    assert int(win._tasks_page._nav_host.width()) == expected

    visible_widths = {w for visible, w, _h in tracker.samples if visible}
    if visible_widths:
        assert visible_widths == {expected}, (
            f"nav width changed during transitions: {sorted(visible_widths)}; "
            f"tracked={tracker.samples}"
        )
