import os
import sys
import time
import random
import math
import shutil
import shlex
import tempfile
import subprocess
import threading

from pathlib import Path
from uuid import uuid4
from typing import Callable
from datetime import datetime
from datetime import timezone
from dataclasses import dataclass
from dataclasses import field

from PySide6.QtCore import QObject
from PySide6.QtCore import QPointF
from PySide6.QtCore import Qt
from PySide6.QtCore import QMetaObject
from PySide6.QtCore import QThread
from PySide6.QtCore import QTimer
from PySide6.QtCore import Signal
from PySide6.QtCore import Slot
from PySide6.QtGui import QColor
from PySide6.QtGui import QFontMetrics
from PySide6.QtGui import QIcon
from PySide6.QtGui import QIntValidator
from PySide6.QtGui import QPainter
from PySide6.QtGui import QPainterPath
from PySide6.QtGui import QRadialGradient
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QCheckBox
from PySide6.QtWidgets import QComboBox
from PySide6.QtWidgets import QFileDialog
from PySide6.QtWidgets import QGridLayout
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QLineEdit
from PySide6.QtWidgets import QMainWindow
from PySide6.QtWidgets import QInputDialog
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtWidgets import QScrollArea
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QStyle
from PySide6.QtWidgets import QTabWidget
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from codex_local_conatinerd.docker_runner import DockerCodexWorker
from codex_local_conatinerd.docker_runner import DockerPreflightWorker
from codex_local_conatinerd.docker_runner import DockerRunnerConfig
from codex_local_conatinerd.docker_platform import ROSETTA_INSTALL_COMMAND
from codex_local_conatinerd.docker_platform import docker_platform_args_for_pixelarch
from codex_local_conatinerd.docker_platform import has_rosetta
from codex_local_conatinerd.agent_cli import additional_config_mounts
from codex_local_conatinerd.agent_cli import container_config_dir
from codex_local_conatinerd.agent_cli import normalize_agent
from codex_local_conatinerd.agent_cli import verify_cli_clause
from codex_local_conatinerd.environments import ALLOWED_STAINS
from codex_local_conatinerd.environments import Environment
from codex_local_conatinerd.environments import GH_MANAGEMENT_GITHUB
from codex_local_conatinerd.environments import GH_MANAGEMENT_LOCAL
from codex_local_conatinerd.environments import GH_MANAGEMENT_NONE
from codex_local_conatinerd.environments import delete_environment
from codex_local_conatinerd.environments import load_environments
from codex_local_conatinerd.environments import managed_repo_checkout_path
from codex_local_conatinerd.environments import managed_repos_dir
from codex_local_conatinerd.environments import normalize_gh_management_mode
from codex_local_conatinerd.environments import parse_env_vars_text
from codex_local_conatinerd.environments import parse_mounts_text
from codex_local_conatinerd.environments import save_environment
from codex_local_conatinerd.environments import serialize_environment
from codex_local_conatinerd.persistence import default_state_path
from codex_local_conatinerd.persistence import deserialize_task
from codex_local_conatinerd.persistence import load_state
from codex_local_conatinerd.persistence import save_state
from codex_local_conatinerd.persistence import serialize_task
from codex_local_conatinerd.prompt_sanitizer import sanitize_prompt
from codex_local_conatinerd.log_format import parse_docker_datetime
from codex_local_conatinerd.log_format import prettify_log_line
from codex_local_conatinerd.style import app_stylesheet
from codex_local_conatinerd.terminal_apps import detect_terminal_options
from codex_local_conatinerd.terminal_apps import launch_in_terminal
from codex_local_conatinerd.widgets import BouncingLoadingBar
from codex_local_conatinerd.widgets import GlassCard
from codex_local_conatinerd.widgets import LogHighlighter
from codex_local_conatinerd.widgets import StatusGlyph
from codex_local_conatinerd.gh_management import GhManagementError
from codex_local_conatinerd.gh_management import commit_push_and_pr
from codex_local_conatinerd.gh_management import ensure_github_clone
from codex_local_conatinerd.gh_management import git_list_remote_heads
from codex_local_conatinerd.gh_management import is_gh_available
from codex_local_conatinerd.gh_management import is_git_repo
from codex_local_conatinerd.gh_management import plan_repo_task
from codex_local_conatinerd.gh_management import prepare_branch_for_task
from codex_local_conatinerd.pr_metadata import ensure_pr_metadata_file
from codex_local_conatinerd.pr_metadata import load_pr_metadata
from codex_local_conatinerd.pr_metadata import normalize_pr_title
from codex_local_conatinerd.pr_metadata import pr_metadata_container_path
from codex_local_conatinerd.pr_metadata import pr_metadata_host_path
from codex_local_conatinerd.pr_metadata import pr_metadata_prompt_instructions


PIXELARCH_EMERALD_IMAGE = "lunamidori5/pixelarch:emerald"
APP_TITLE = "Midori AI Agents Runner"
PIXELARCH_AGENT_CONTEXT_SUFFIX = (
    "\n\n"
    "Environment context:\n"
    "- You are running inside PixelArch.\n"
    "- You have passwordless sudo.\n"
    "- If you need to install packages, use `yay -Syu`.\n"
    "- You have full control of the container you are running in.\n"
)


def _app_icon() -> QIcon | None:
    icon_path = Path(__file__).resolve().with_name("midoriai-logo.png")
    return QIcon(str(icon_path)) if icon_path.exists() else None


def _parse_docker_time(value: str | None) -> datetime | None:
    dt = parse_docker_datetime(value)
    # Docker reports Go's "zero time" for fields like FinishedAt while running.
    # Treat anything pre-epoch as unset.
    return dt if dt and dt.year >= 1970 else None


def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    seconds = max(0.0, float(seconds))
    if seconds < 60:
        return f"{int(seconds)}s"
    minutes, rem = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m {int(rem)}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def _safe_str(value: object, default: str = "") -> str:
    """Convert value to stripped string, returning default if empty."""
    return str(value or default).strip() or default


def _looks_like_agent_help_command(command: str) -> bool:
    value = str(command or "").strip()
    if not value:
        return False
    lowered = value.lower()
    return "agent-help" in lowered or ".agent-help" in lowered


def _status_color(status: str) -> QColor:
    """Map status string to color."""
    color_map = {
        "pulling": (56, 189, 248, 220),
        "cleaning": (56, 189, 248, 220),
        "done": (16, 185, 129, 230),
        "failed": (244, 63, 94, 230),
        "created": (148, 163, 184, 220),
        "running": (16, 185, 129, 220),
        "paused": (245, 158, 11, 220),
        "restarting": (56, 189, 248, 220),
        "removing": (56, 189, 248, 220),
        "exited": (148, 163, 184, 220),
        "dead": (148, 163, 184, 220),
        "error": (244, 63, 94, 220),
    }
    rgba = color_map.get((status or "").lower(), (148, 163, 184, 220))
    return QColor(*rgba)


def _rgba(color: QColor, alpha: int | None = None) -> str:
    """Convert QColor to CSS rgba() string."""
    a = color.alpha() if alpha is None else alpha
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {int(a)})"


def _stain_color(stain: str) -> QColor:
    """Map stain name to color."""
    color_map = {
        "cyan": (56, 189, 248, 220),
        "emerald": (16, 185, 129, 220),
        "violet": (139, 92, 246, 220),
        "rose": (244, 63, 94, 220),
        "amber": (245, 158, 11, 220),
        "blue": (59, 130, 246, 220),
        "teal": (20, 184, 166, 220),
        "lime": (132, 204, 22, 220),
        "fuchsia": (217, 70, 239, 220),
        "indigo": (99, 102, 241, 220),
        "orange": (249, 115, 22, 220),
    }
    rgba = color_map.get((stain or "").strip().lower(), (148, 163, 184, 220))
    return QColor(*rgba)


def _blend_rgb(a: QColor, b: QColor, t: float) -> QColor:
    t = float(min(max(t, 0.0), 1.0))
    r = int(round(a.red() + (b.red() - a.red()) * t))
    g = int(round(a.green() + (b.green() - a.green()) * t))
    bb = int(round(a.blue() + (b.blue() - a.blue()) * t))
    return QColor(r, g, bb)


def _apply_environment_combo_tint(combo: QComboBox, stain: str) -> None:
    env = _stain_color(stain)
    base = QColor(18, 20, 28)
    tinted = _blend_rgb(base, QColor(env.red(), env.green(), env.blue()), 0.40)
    combo.setStyleSheet(
        "\n".join(
            [
                "QComboBox {",
                f"  background-color: {_rgba(QColor(tinted.red(), tinted.green(), tinted.blue(), 190))};",
                "}",
                "QComboBox::drop-down {",
                f"  background-color: {_rgba(QColor(tinted.red(), tinted.green(), tinted.blue(), 135))};",
                "}",
                "QComboBox QAbstractItemView {",
                f"  background-color: {_rgba(QColor(tinted.red(), tinted.green(), tinted.blue(), 240))};",
                f"  selection-background-color: {_rgba(QColor(env.red(), env.green(), env.blue(), 95))};",
                "}",
            ]
        )
    )


class _EnvironmentTintOverlay(QWidget):
    def __init__(self, parent: QWidget | None = None, alpha: int = 13) -> None:
        super().__init__(parent)
        self._alpha = int(min(max(alpha, 0), 255))
        self._color = QColor(0, 0, 0, 0)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)

    def set_tint_color(self, color: QColor | None) -> None:
        if color is None:
            self._color = QColor(0, 0, 0, 0)
        else:
            self._color = QColor(color.red(), color.green(), color.blue(), self._alpha)
        self.update()

    def paintEvent(self, event) -> None:
        if self._color.alpha() <= 0:
            return
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._color)


@dataclass
class _BackgroundOrb:
    x: float
    y: float
    vx: float
    vy: float
    radius: float
    color: QColor

    def render_radius(self) -> float:
        return self.radius * 1.65


class GlassRoot(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._animate_orbs = False
        self._orb_rng = random.Random()
        self._orbs: list[_BackgroundOrb] = []
        self._orb_last_tick_s = time.monotonic()
        self._orb_timer: QTimer | None = None
        if self._animate_orbs:
            timer = QTimer(self)
            timer.setInterval(33)
            timer.timeout.connect(self._tick_orbs)
            timer.start()
            self._orb_timer = timer

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._constrain_orbs()

    def _theme_colors(self) -> list[QColor]:
        return [
            QColor(56, 189, 248),
            QColor(16, 185, 129),
            QColor(139, 92, 246),
            QColor(244, 63, 94),
            QColor(245, 158, 11),
        ]

    def _ensure_orbs(self) -> None:
        if self._orbs:
            return
        w, h = self.width(), self.height()
        if w < 80 or h < 80:
            return

        colors = self._theme_colors()
        orbs: list[_BackgroundOrb] = []
        for idx in range(9):
            radius = self._orb_rng.uniform(140.0, 260.0)
            render_r = radius * 1.65
            x = self._orb_rng.uniform(render_r, max(render_r, w - render_r))
            y = self._orb_rng.uniform(render_r, max(render_r, h - render_r))

            if self._animate_orbs:
                angle = self._orb_rng.uniform(0.0, 6.283185307179586)
                speed = self._orb_rng.uniform(8.0, 22.0)
                vx = math.cos(angle) * speed
                vy = math.sin(angle) * speed
            else:
                vx = vy = 0.0

            orbs.append(_BackgroundOrb(
                x=x, y=y, vx=vx, vy=vy, radius=radius, color=colors[idx % len(colors)]
            ))

        self._orbs = orbs
        self._constrain_orbs()

    def _constrain_orbs(self) -> None:
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0 or not self._orbs:
            return
        for orb in self._orbs:
            r = orb.render_radius()
            orb.x = min(max(orb.x, r), w - r)
            orb.y = min(max(orb.y, r), h - r)

    def _tick_orbs(self) -> None:
        if not self._animate_orbs:
            return
        now_s = time.monotonic()
        dt = now_s - self._orb_last_tick_s
        self._orb_last_tick_s = now_s

        if dt <= 0:
            return
        dt = min(dt, 0.060)

        self._ensure_orbs()
        if not self._orbs:
            return

        w = float(max(1, self.width()))
        h = float(max(1, self.height()))
        for orb in self._orbs:
            orb.x += orb.vx * dt
            orb.y += orb.vy * dt

            r = orb.render_radius()
            if orb.x - r <= 0.0:
                orb.x = r
                orb.vx = abs(orb.vx)
            elif orb.x + r >= w:
                orb.x = w - r
                orb.vx = -abs(orb.vx)

            if orb.y - r <= 0.0:
                orb.y = r
                orb.vy = abs(orb.vy)
            elif orb.y + r >= h:
                orb.y = h - r
                orb.vy = -abs(orb.vy)

        self.update()

    def _paint_orbs(self, painter: QPainter) -> None:
        if not self._orbs:
            return
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)

        for orb in self._orbs:
            for shrink, alpha in ((1.0, 34), (0.82, 24), (0.66, 16)):
                r = max(1.0, orb.render_radius() * shrink)
                center = QPointF(float(orb.x), float(orb.y))
                grad = QRadialGradient(center, float(r))
                c = orb.color
                grad.setColorAt(0.0, QColor(c.red(), c.green(), c.blue(), alpha))
                grad.setColorAt(0.55, QColor(c.red(), c.green(), c.blue(), int(alpha * 0.30)))
                grad.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))
                painter.setBrush(grad)
                painter.drawEllipse(center, float(r), float(r))

        painter.restore()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        painter.fillRect(self.rect(), QColor(10, 12, 18))

        self._ensure_orbs()
        self._paint_orbs(painter)

        w = max(1, self.width())
        h = max(1, self.height())
        shards = [
            (QColor(56, 189, 248, 38), [(0.00, 0.10), (0.38, 0.00), (0.55, 0.23), (0.22, 0.34)]),
            (QColor(16, 185, 129, 34), [(0.62, 0.00), (1.00, 0.14), (0.88, 0.42), (0.58, 0.28)]),
            (QColor(139, 92, 246, 28), [(0.08, 0.48), (0.28, 0.38), (0.52, 0.64), (0.20, 0.80)]),
            (QColor(244, 63, 94, 22), [(0.62, 0.56), (0.94, 0.46), (1.00, 0.82), (0.76, 1.00)]),
            (QColor(245, 158, 11, 18), [(0.00, 0.78), (0.20, 0.64), (0.40, 1.00), (0.00, 1.00)]),
        ]

        for color, points in shards:
            path = QPainterPath()
            x0, y0 = points[0]
            path.moveTo(int(x0 * w), int(y0 * h))
            for x, y in points[1:]:
                path.lineTo(int(x * w), int(y * h))
            path.closeSubpath()
            painter.fillPath(path, color)
            painter.setPen(QColor(255, 255, 255, 10))
            painter.drawPath(path)


class ElidedLabel(QLabel):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._full_text = text
        self.setWordWrap(False)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)

    def setFullText(self, text: str) -> None:
        self._full_text = text
        self._update_elide()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_elide()

    def _update_elide(self) -> None:
        metrics = QFontMetrics(self.font())
        elided = metrics.elidedText(self._full_text, Qt.ElideRight, max(10, self.width() - 4))
        super().setText(elided)


@dataclass
class Task:
    task_id: str
    prompt: str
    image: str
    host_workdir: str
    host_codex_dir: str
    created_at_s: float
    environment_id: str = ""
    status: str = "queued"
    exit_code: int | None = None
    error: str | None = None
    container_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    logs: list[str] = field(default_factory=list)
    gh_management_mode: str = GH_MANAGEMENT_NONE
    gh_use_host_cli: bool = True
    gh_repo_root: str = ""
    gh_base_branch: str = ""
    gh_branch: str = ""
    gh_pr_url: str = ""
    gh_pr_metadata_path: str = ""
    agent_cli: str = ""
    agent_cli_args: str = ""

    def last_nonblank_log_line(self) -> str:
        for line in reversed(self.logs):
            text = str(line or "").strip()
            if text:
                return text
        return ""

    def elapsed_seconds(self, now_s: float | None = None) -> float | None:
        created_s = float(self.created_at_s or 0.0)
        if created_s <= 0.0:
            if self.started_at and self.finished_at and self.finished_at > self.started_at:
                return (self.finished_at - self.started_at).total_seconds()
            return None
        finished = self.finished_at
        if finished is not None and finished.year < 1970:
            finished = None
        if finished is not None:
            try:
                end_s = float(finished.timestamp())
            except Exception:
                end_s = float(now_s if now_s is not None else time.time())
        else:
            end_s = float(now_s if now_s is not None else time.time())
        return max(0.0, end_s - created_s)

    def is_interactive_run(self) -> bool:
        container_id = str(self.container_id or "")
        return container_id.startswith("codex-gui-it-")

    def prompt_one_line(self) -> str:
        line = (self.prompt or "").strip().splitlines()[0] if self.prompt else ""
        if line:
            return line
        if self.is_interactive_run():
            return "Interactive"
        return "(empty prompt)"

    def info_one_line(self) -> str:
        if self.error:
            return self.error.replace("\n", " ").strip()
        duration = self.elapsed_seconds()
        if self.exit_code is None:
            if self.is_active():
                last_line = self.last_nonblank_log_line()
                if last_line:
                    return last_line
                return f"elapsed {_format_duration(duration)}"
            return ""
        if self.exit_code == 0:
            last_line = self.last_nonblank_log_line()
            dur = _format_duration(duration)
            if last_line and dur != "—":
                return f"{last_line} • {dur}"
            if last_line:
                return last_line
            return f"ok • {dur}"
        return f"exit {self.exit_code} • {_format_duration(duration)}"

    def is_active(self) -> bool:
        return (self.status or "").lower() in {"queued", "pulling", "created", "running", "starting", "cleaning"}

    def is_done(self) -> bool:
        return (self.status or "").lower() == "done"

    def is_failed(self) -> bool:
        return (self.status or "").lower() in {"failed", "error"}


def _task_display_status(task: Task) -> str:
    status = (task.status or "").lower()
    if status == "done":
        return "Done"
    if status in {"failed", "error"}:
        return "Failed"
    if status == "pulling":
        return "Pulling"
    if status == "running":
        return "Running"
    if status == "created":
        return "Created"
    if status == "queued":
        return "Queued"
    if status == "starting":
        return "Starting"
    if status == "paused":
        return "Paused"
    if status == "restarting":
        return "Restarting"
    if status == "removing":
        return "Removing"
    if status == "exited" and task.exit_code == 0:
        return "Done"
    if status == "exited" and task.exit_code is not None:
        return f"Exit {task.exit_code}"
    if status == "unknown":
        return "Unknown"
    return status.title() if status else "—"


class TaskRunnerBridge(QObject):
    state = Signal(dict)
    log = Signal(str)
    done = Signal(int, object)

    def __init__(self, task_id: str, config: DockerRunnerConfig, prompt: str = "", mode: str = "codex") -> None:
        super().__init__()
        self.task_id = task_id
        if mode == "preflight":
            self._worker = DockerPreflightWorker(
                config=config,
                on_state=self.state.emit,
                on_log=self.log.emit,
                on_done=lambda code, err: self.done.emit(code, err),
            )
        else:
            self._worker = DockerCodexWorker(
                config=config,
                prompt=prompt,
                on_state=self.state.emit,
                on_log=self.log.emit,
                on_done=lambda code, err: self.done.emit(code, err),
            )

    @property
    def container_id(self) -> str | None:
        return self._worker.container_id

    @Slot()
    def request_stop(self) -> None:
        self._worker.request_stop()

    def run(self) -> None:
        self._worker.run()


class DockerPruneBridge(QObject):
    done = Signal(int, str)

    def __init__(self) -> None:
        super().__init__()

    def run(self) -> None:
        docker_args = ["docker", "system", "prune", "-f", "-a"]
        args: list[str]
        if shutil.which("sudo"):
            args = ["sudo", "-n", *docker_args]
        else:
            args = docker_args

        try:
            proc = subprocess.run(args, capture_output=True, text=True, check=False)
        except Exception as exc:
            self.done.emit(1, str(exc))
            return

        output = "\n".join([str(proc.stdout or "").strip(), str(proc.stderr or "").strip()]).strip()
        if not output:
            output = f"Command exited with code {proc.returncode}."
        self.done.emit(int(proc.returncode), output)


class HostCleanupBridge(QObject):
    log = Signal(str)
    done = Signal(int, str)

    def __init__(
        self,
        runner: Callable[[Callable[[str], None], threading.Event], tuple[int, str]],
    ) -> None:
        super().__init__()
        self._runner = runner
        self._stop = threading.Event()

    @Slot()
    def request_stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        try:
            exit_code, output = self._runner(self.log.emit, self._stop)
        except Exception as exc:
            self.done.emit(1, str(exc))
            return
        self.done.emit(int(exit_code), str(output or "").strip())


class TaskRow(QWidget):
    clicked = Signal()
    discard_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(52)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._task_id: str | None = None
        self._last_task: Task | None = None
        self.setObjectName("TaskRow")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setProperty("selected", False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        self._task = ElidedLabel("—")
        self._task.setStyleSheet("font-weight: 650; color: rgba(237, 239, 245, 235);")
        self._task.setMinimumWidth(260)
        self._task.setTextInteractionFlags(Qt.NoTextInteraction)
        self._task.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        state_wrap = QWidget()
        state_layout = QHBoxLayout(state_wrap)
        state_layout.setContentsMargins(0, 0, 0, 0)
        state_layout.setSpacing(8)
        self._glyph = StatusGlyph(size=18)
        self._glyph.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._busy_bar = BouncingLoadingBar(width=72, height=8)
        self._busy_bar.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._busy_bar.hide()
        self._status = QLabel("idle")
        self._status.setStyleSheet("color: rgba(237, 239, 245, 190);")
        self._status.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        state_layout.addWidget(self._glyph, 0, Qt.AlignLeft)
        state_layout.addWidget(self._busy_bar, 0, Qt.AlignLeft)
        state_layout.addWidget(self._status, 0, Qt.AlignLeft)
        state_wrap.setMinimumWidth(180)
        state_wrap.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self._info = ElidedLabel("")
        self._info.setStyleSheet("color: rgba(237, 239, 245, 150);")
        self._info.setTextInteractionFlags(Qt.NoTextInteraction)
        self._info.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self._btn_discard = QToolButton()
        self._btn_discard.setObjectName("RowTrash")
        self._btn_discard.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        self._btn_discard.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._btn_discard.setToolTip("Discard task")
        self._btn_discard.setCursor(Qt.PointingHandCursor)
        self._btn_discard.setIconSize(self._btn_discard.iconSize().expandedTo(self._glyph.size()))
        self._btn_discard.clicked.connect(self._on_discard_clicked)

        layout.addWidget(self._task, 5)
        layout.addWidget(state_wrap, 0)
        layout.addWidget(self._info, 4)
        layout.addWidget(self._btn_discard, 0, Qt.AlignRight)

        self.setCursor(Qt.PointingHandCursor)
        self.set_stain("slate")

    @property
    def task_id(self) -> str | None:
        return self._task_id

    def set_task_id(self, task_id: str) -> None:
        self._task_id = task_id

    def _on_discard_clicked(self) -> None:
        if self._task_id:
            self.discard_requested.emit(self._task_id)

    def set_stain(self, stain: str) -> None:
        if (self.property("stain") or "") == stain:
            return
        self.setProperty("stain", stain)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def set_selected(self, selected: bool) -> None:
        selected = bool(selected)
        if bool(self.property("selected")) == selected:
            return
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_task(self, text: str) -> None:
        self._task.setFullText(text)

    def set_info(self, text: str) -> None:
        self._info.setFullText(text)

    def update_from_task(self, task: Task, spinner_color: QColor | None = None) -> None:
        self._last_task = task
        self.set_task(task.prompt_one_line())
        self.set_info(task.info_one_line())

        display = _task_display_status(task)
        status_key = (task.status or "").lower()
        color = _status_color(status_key)
        self._status.setText(display)
        self._status.setStyleSheet(f"color: {_rgba(color, 235)}; font-weight: 700;")

        if task.is_active():
            self._glyph.hide()
            self._busy_bar.set_color(spinner_color or color)
            self._busy_bar.set_mode("dotted" if status_key == "queued" else "bounce")
            self._busy_bar.show()
            self._busy_bar.start()
            return
        self._busy_bar.stop()
        self._busy_bar.hide()
        self._glyph.show()
        if task.is_done():
            self._glyph.set_mode("check", color)
            return
        if task.is_failed() or (task.exit_code is not None and task.exit_code != 0):
            self._glyph.set_mode("x", color)
            return
        self._glyph.set_mode("idle", color)

    def last_task(self) -> Task | None:
        return self._last_task


class DashboardPage(QWidget):
    task_selected = Signal(str)
    clean_old_requested = Signal()
    task_discard_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected_task_id: str | None = None
        self._filter_text_tokens: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        table = GlassCard()
        table_layout = QVBoxLayout(table)
        table_layout.setContentsMargins(12, 12, 12, 12)
        table_layout.setSpacing(10)

        filters = QWidget()
        filters_layout = QHBoxLayout(filters)
        filters_layout.setContentsMargins(8, 0, 8, 0)
        filters_layout.setSpacing(10)

        self._filter_text = QLineEdit()
        self._filter_text.setPlaceholderText("Filter tasks…")
        self._filter_text.textChanged.connect(self._on_filter_changed)

        self._filter_environment = QComboBox()
        self._filter_environment.setFixedWidth(240)
        self._filter_environment.addItem("All environments", "")
        self._filter_environment.currentIndexChanged.connect(self._on_filter_changed)

        self._filter_state = QComboBox()
        self._filter_state.setFixedWidth(160)
        self._filter_state.addItem("Any state", "any")
        self._filter_state.addItem("Active", "active")
        self._filter_state.addItem("Done", "done")
        self._filter_state.addItem("Failed", "failed")
        self._filter_state.currentIndexChanged.connect(self._on_filter_changed)

        clear_filters = QToolButton()
        clear_filters.setObjectName("RowTrash")
        clear_filters.setIcon(self.style().standardIcon(QStyle.SP_DialogResetButton))
        clear_filters.setToolButtonStyle(Qt.ToolButtonIconOnly)
        clear_filters.setToolTip("Clear filters")
        clear_filters.setAccessibleName("Clear filters")
        clear_filters.clicked.connect(self._clear_filters)

        self._btn_clean_old = QToolButton()
        self._btn_clean_old.setObjectName("RowTrash")
        self._btn_clean_old.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        self._btn_clean_old.setToolTip("Clean finished tasks")
        self._btn_clean_old.setAccessibleName("Clean finished tasks")
        self._btn_clean_old.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._btn_clean_old.clicked.connect(self.clean_old_requested.emit)

        filters_layout.addWidget(self._filter_text, 1)
        filters_layout.addWidget(self._filter_environment)
        filters_layout.addWidget(self._filter_state)
        filters_layout.addWidget(clear_filters, 0, Qt.AlignRight)
        filters_layout.addWidget(self._btn_clean_old, 0, Qt.AlignRight)

        columns = QWidget()
        columns_layout = QHBoxLayout(columns)
        columns_layout.setContentsMargins(8, 0, 8, 0)
        columns_layout.setSpacing(12)
        c1 = QLabel("Task")
        c1.setStyleSheet("color: rgba(237, 239, 245, 150); font-weight: 650;")
        c2 = QLabel("State")
        c2.setStyleSheet("color: rgba(237, 239, 245, 150); font-weight: 650;")
        c3 = QLabel("Info")
        c3.setStyleSheet("color: rgba(237, 239, 245, 150); font-weight: 650;")
        c1.setMinimumWidth(260)
        c2.setMinimumWidth(180)
        columns_layout.addWidget(c1, 5)
        columns_layout.addWidget(c2, 0)
        columns_layout.addWidget(c3, 4)
        columns_layout.addSpacing(self._btn_clean_old.sizeHint().width())

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setObjectName("TaskScroll")

        self._list = QWidget()
        self._list.setObjectName("TaskList")
        self._list_layout = QVBoxLayout(self._list)
        self._list_layout.setContentsMargins(8, 8, 8, 8)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch(1)
        self._scroll.setWidget(self._list)

        table_layout.addWidget(filters)
        table_layout.addWidget(columns)
        table_layout.addWidget(self._scroll, 1)
        layout.addWidget(table, 1)

        self._rows: dict[str, TaskRow] = {}

    def _set_selected_task_id(self, task_id: str | None) -> None:
        task_id = str(task_id or "").strip() or None
        if self._selected_task_id == task_id:
            return
        prev = self._selected_task_id
        self._selected_task_id = task_id

        if prev and prev in self._rows:
            self._rows[prev].set_selected(False)
        if task_id and task_id in self._rows:
            self._rows[task_id].set_selected(True)

    def _pick_new_row_stain(self) -> str:
        stains = tuple(stain for stain in ALLOWED_STAINS if stain != "slate")
        if not stains:
            stains = ("slate",)
        current: str | None = None
        for i in range(self._list_layout.count()):
            item = self._list_layout.itemAt(i)
            widget = item.widget() if item is not None else None
            if isinstance(widget, TaskRow):
                current = str(widget.property("stain") or "")
                break
        if current in stains:
            return stains[(stains.index(current) + 1) % len(stains)]
        return stains[0]

    def upsert_task(self, task: Task, stain: str | None = None, spinner_color: QColor | None = None) -> None:
        row = self._rows.get(task.task_id)
        if row is None:
            row = TaskRow()
            row.set_task_id(task.task_id)
            row.set_stain(stain or self._pick_new_row_stain())
            row.clicked.connect(self._on_row_clicked)
            row.discard_requested.connect(self.task_discard_requested.emit)
            self._rows[task.task_id] = row
            self._list_layout.insertWidget(0, row)
        elif stain:
            row.set_stain(stain)

        row.set_selected(self._selected_task_id == task.task_id)
        row.update_from_task(task, spinner_color=spinner_color)
        row.setVisible(self._row_visible_for_task(task))

    def set_environment_filter_options(self, envs: list[tuple[str, str]]) -> None:
        current = str(self._filter_environment.currentData() or "")
        self._filter_environment.blockSignals(True)
        try:
            self._filter_environment.clear()
            self._filter_environment.addItem("All environments", "")
            for env_id, label in envs:
                self._filter_environment.addItem(label or env_id, env_id)
            idx = self._filter_environment.findData(current)
            if idx < 0:
                idx = 0
            self._filter_environment.setCurrentIndex(idx)
        finally:
            self._filter_environment.blockSignals(False)
        self._apply_filters()

    def _clear_filters(self) -> None:
        self._filter_text.setText("")
        self._filter_environment.setCurrentIndex(0)
        self._filter_state.setCurrentIndex(0)

    def _on_filter_changed(self, _value: object = None) -> None:
        raw = (self._filter_text.text() or "").strip().lower()
        self._filter_text_tokens = [t for t in raw.split() if t]
        self._apply_filters()

    def _task_matches_text(self, task: Task) -> bool:
        if not self._filter_text_tokens:
            return True
        haystack = " ".join(
            [
                str(task.task_id or ""),
                str(task.environment_id or ""),
                str(task.status or ""),
                task.prompt_one_line(),
                task.info_one_line(),
            ]
        ).lower()
        return all(token in haystack for token in self._filter_text_tokens)

    @staticmethod
    def _task_matches_state(task: Task, state: str) -> bool:
        state = str(state or "any")
        if state == "any":
            return True
        if state == "active":
            return task.is_active()
        status = (task.status or "").lower()
        if state == "done":
            return task.is_done() or (status == "exited" and task.exit_code == 0)
        if state == "failed":
            if task.is_failed():
                return True
            return task.exit_code is not None and task.exit_code != 0
        return True

    def _row_visible_for_task(self, task: Task) -> bool:
        env_filter = str(self._filter_environment.currentData() or "")
        if env_filter and str(task.environment_id or "") != env_filter:
            return False
        state_filter = str(self._filter_state.currentData() or "any")
        if not self._task_matches_state(task, state_filter):
            return False
        return self._task_matches_text(task)

    def _apply_filters(self) -> None:
        for row in self._rows.values():
            task = row.last_task()
            row.setVisible(True if task is None else self._row_visible_for_task(task))

    def _on_row_clicked(self) -> None:
        row = self.sender()
        if isinstance(row, TaskRow) and row.task_id:
            self._set_selected_task_id(row.task_id)
            self.task_selected.emit(row.task_id)

    def remove_tasks(self, task_ids: set[str]) -> None:
        for task_id in task_ids:
            row = self._rows.pop(task_id, None)
            if row is not None:
                row.setParent(None)
                row.deleteLater()
            if self._selected_task_id == task_id:
                self._selected_task_id = None


class TaskDetailsPage(QWidget):
    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_task_id: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        header = GlassCard()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 18, 16)
        header_layout.setSpacing(10)

        self._title = QLabel("Task")
        self._title.setStyleSheet("font-size: 18px; font-weight: 750;")
        self._subtitle = QLabel("—")
        self._subtitle.setStyleSheet("color: rgba(237, 239, 245, 160);")

        back = QToolButton()
        back.setText("Back")
        back.setToolButtonStyle(Qt.ToolButtonTextOnly)
        back.clicked.connect(self.back_requested.emit)

        header_layout.addWidget(self._title)
        header_layout.addWidget(self._subtitle, 1)
        header_layout.addWidget(back, 0, Qt.AlignRight)
        layout.addWidget(header)

        mid = QHBoxLayout()
        mid.setSpacing(14)
        layout.addLayout(mid, 2)

        left = GlassCard()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(18, 16, 18, 16)
        left_layout.setSpacing(10)

        ptitle = QLabel("Prompt")
        ptitle.setStyleSheet("font-size: 14px; font-weight: 650;")
        self._prompt = QPlainTextEdit()
        self._prompt.setReadOnly(True)
        self._prompt.setMaximumBlockCount(2000)

        cfg = QGridLayout()
        cfg.setHorizontalSpacing(10)
        cfg.setVerticalSpacing(8)

        self._workdir = QLabel("—")
        self._codexdir = QLabel("—")
        self._container = QLabel("—")
        self._container.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._workdir.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._codexdir.setTextInteractionFlags(Qt.TextSelectableByMouse)

        cfg.addWidget(QLabel("Host Workdir"), 0, 0)
        cfg.addWidget(self._workdir, 0, 1)
        cfg.addWidget(QLabel("Host Config folder"), 1, 0)
        cfg.addWidget(self._codexdir, 1, 1)
        cfg.addWidget(QLabel("Container ID"), 2, 0)
        cfg.addWidget(self._container, 2, 1)

        left_layout.addWidget(ptitle)
        left_layout.addWidget(self._prompt, 1)
        left_layout.addLayout(cfg)
        mid.addWidget(left, 3)

        right = GlassCard()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(18, 16, 18, 16)
        right_layout.setSpacing(12)

        stitle = QLabel("Container state")
        stitle.setStyleSheet("font-size: 14px; font-weight: 650;")

        state_row = QHBoxLayout()
        state_row.setSpacing(12)
        self._glyph = StatusGlyph(size=44)
        self._status = QLabel("idle")
        self._status.setStyleSheet("font-size: 16px; font-weight: 750;")
        state_row.addWidget(self._glyph, 0, Qt.AlignLeft)
        state_row.addWidget(self._status, 1)

        details = QGridLayout()
        details.setHorizontalSpacing(10)
        details.setVerticalSpacing(8)

        self._started = QLabel("—")
        self._uptime = QLabel("—")
        self._exit = QLabel("—")
        details.addWidget(QLabel("Started"), 0, 0)
        details.addWidget(self._started, 0, 1)
        details.addWidget(QLabel("Elapsed"), 1, 0)
        details.addWidget(self._uptime, 1, 1)
        details.addWidget(QLabel("Exit code"), 2, 0)
        details.addWidget(self._exit, 2, 1)

        right_layout.addWidget(stitle)
        right_layout.addLayout(state_row)
        right_layout.addLayout(details)
        right_layout.addStretch(1)
        mid.addWidget(right, 2)

        logs = GlassCard()
        logs_layout = QVBoxLayout(logs)
        logs_layout.setContentsMargins(18, 16, 18, 16)
        logs_layout.setSpacing(10)

        ltitle = QLabel("Logs")
        ltitle.setStyleSheet("font-size: 14px; font-weight: 650;")
        self._logs = QPlainTextEdit()
        self._logs.setObjectName("LogsView")
        self._logs.setReadOnly(True)
        self._logs.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._logs.setMaximumBlockCount(5000)
        self._log_highlighter = LogHighlighter(self._logs.document())
        logs_layout.addWidget(ltitle)
        logs_layout.addWidget(self._logs, 1)
        layout.addWidget(logs, 2)

        self._ticker = QTimer(self)
        self._ticker.setInterval(1000)
        self._ticker.timeout.connect(self._tick_uptime)
        self._ticker.start()

        self._last_task: Task | None = None

    def _logs_is_at_bottom(self, slack: int = 6) -> bool:
        bar = self._logs.verticalScrollBar()
        return bar.value() >= (bar.maximum() - slack)

    def _scroll_logs_to_bottom(self) -> None:
        bar = self._logs.verticalScrollBar()
        bar.setValue(bar.maximum())

    def current_task_id(self) -> str | None:
        return self._current_task_id

    def show_task(self, task: Task) -> None:
        self._current_task_id = task.task_id
        self._last_task = task
        self._title.setText(f"Task {task.task_id}")
        self._subtitle.setText(task.prompt_one_line())
        self._prompt.setPlainText(task.prompt)
        self._workdir.setText(task.host_workdir)
        self._codexdir.setText(task.host_codex_dir)
        self._container.setText(task.container_id or "—")
        self._logs.setPlainText("\n".join(task.logs[-5000:]))
        QTimer.singleShot(0, self._scroll_logs_to_bottom)
        self._apply_status(task)
        self._tick_uptime()

    def append_log(self, task_id: str, line: str) -> None:
        if self._current_task_id != task_id:
            return
        should_follow = self._logs_is_at_bottom()
        self._logs.appendPlainText(line)
        if should_follow:
            QTimer.singleShot(0, self._scroll_logs_to_bottom)

    def update_task(self, task: Task) -> None:
        if self._current_task_id != task.task_id:
            return
        self._last_task = task
        self._container.setText(task.container_id or "—")
        self._exit.setText("—" if task.exit_code is None else str(task.exit_code))
        self._apply_status(task)
        self._tick_uptime()

    def _apply_status(self, task: Task) -> None:
        status = _task_display_status(task)
        color = _status_color(task.status)
        self._status.setText(status)
        self._status.setStyleSheet(
            "font-size: 16px; font-weight: 750; " f"color: {_rgba(color, 235)};"
        )
        if task.is_active():
            self._glyph.set_mode("spinner", color)
        elif task.is_done():
            self._glyph.set_mode("check", color)
        elif task.is_failed() or status.startswith("Exit "):
            self._glyph.set_mode("x", color)
        else:
            self._glyph.set_mode("idle", color)

        started_local = "—"
        if task.started_at:
            started_local = task.started_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        self._started.setText(started_local)
        self._exit.setText("—" if task.exit_code is None else str(task.exit_code))

    def _tick_uptime(self) -> None:
        task = self._last_task
        if not task:
            self._uptime.setText("—")
            return
        self._uptime.setText(_format_duration(task.elapsed_seconds()))


class NewTaskPage(QWidget):
    requested_run = Signal(str, str, str, str)
    requested_launch = Signal(str, str, str, str, str, str, str)
    back_requested = Signal()
    environment_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._env_stains: dict[str, str] = {}
        self._host_codex_dir = os.path.expanduser("~/.codex")
        self._workspace_ready = False
        self._workspace_error = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self._environment = QComboBox()
        self._environment.currentIndexChanged.connect(self._on_environment_changed)

        header = GlassCard()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 18, 16)
        header_layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        title = QLabel("New task")
        title.setStyleSheet("font-size: 18px; font-weight: 750;")

        env_label = QLabel("Environment")
        env_label.setStyleSheet("color: rgba(237, 239, 245, 160);")

        back = QToolButton()
        back.setText("Back")
        back.setToolButtonStyle(Qt.ToolButtonTextOnly)
        back.clicked.connect(self.back_requested.emit)

        top_row.addWidget(title)
        top_row.addWidget(env_label)
        top_row.addWidget(self._environment)
        top_row.addStretch(1)
        top_row.addWidget(back, 0, Qt.AlignRight)

        header_layout.addLayout(top_row)
        layout.addWidget(header)

        card = GlassCard()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(10)

        prompt_title = QLabel("Prompt")
        prompt_title.setStyleSheet("font-size: 14px; font-weight: 650;")
        self._prompt = QPlainTextEdit()
        self._prompt.setPlaceholderText("Describe what you want the agent to do…")
        self._prompt.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._prompt.setTabChangesFocus(True)

        interactive_hint = QLabel("Interactive: opens a terminal and runs the container with TTY/stdin for agent TUIs.")
        interactive_hint.setStyleSheet("color: rgba(237, 239, 245, 160);")

        self._terminal = QComboBox()
        self._refresh_terminals()

        refresh_terminals = QToolButton()
        refresh_terminals.setText("Refresh")
        refresh_terminals.setToolButtonStyle(Qt.ToolButtonTextOnly)
        refresh_terminals.clicked.connect(self._refresh_terminals)

        self._command = QLineEdit("--sandbox danger-full-access")
        self._command.setPlaceholderText(
            "Args for the Agent CLI (e.g. --sandbox danger-full-access or --add-dir …), or a full container command (e.g. bash)"
        )

        interactive_grid = QGridLayout()
        interactive_grid.setHorizontalSpacing(10)
        interactive_grid.setVerticalSpacing(10)
        interactive_grid.setColumnStretch(4, 1)
        interactive_grid.addWidget(QLabel("Terminal"), 0, 0)
        interactive_grid.addWidget(self._terminal, 0, 1)
        interactive_grid.addWidget(refresh_terminals, 0, 2)
        interactive_grid.addWidget(QLabel("Container command args"), 0, 3)
        interactive_grid.addWidget(self._command, 0, 4)

        cfg_grid = QGridLayout()
        cfg_grid.setHorizontalSpacing(10)
        cfg_grid.setVerticalSpacing(10)
        self._workspace = QLabel("—")
        self._workspace.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._workspace_hint = QLabel("")
        self._workspace_hint.setStyleSheet("color: rgba(237, 239, 245, 160);")
        self._workspace_hint.setWordWrap(True)

        cfg_grid.addWidget(QLabel("Workspace"), 0, 0)
        cfg_grid.addWidget(self._workspace, 0, 1, 1, 2)
        cfg_grid.addWidget(self._workspace_hint, 1, 1, 1, 2)

        self._base_branch_label = QLabel("Base branch")
        self._base_branch = QComboBox()
        self._base_branch.setToolTip("Base branch for the per-task branch (only shown for repo environments).")
        self.set_repo_branches([])
        cfg_grid.addWidget(self._base_branch_label, 2, 0)
        cfg_grid.addWidget(self._base_branch, 2, 1, 1, 2)
        self.set_repo_controls_visible(False)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self._get_agent_help = QPushButton("Get Agent Help")
        self._get_agent_help.clicked.connect(self._on_get_agent_help)
        self._get_agent_help.setEnabled(False)
        buttons.addWidget(self._get_agent_help)
        buttons.addStretch(1)
        self._run_interactive = QPushButton("Run Interactive")
        self._run_interactive.clicked.connect(self._on_launch)
        self._run_agent = QPushButton("Run Agent")
        self._run_agent.clicked.connect(self._on_run)
        self._run_interactive.setEnabled(False)
        self._run_agent.setEnabled(False)
        buttons.addWidget(self._run_interactive)
        buttons.addWidget(self._run_agent)

        card_layout.addWidget(prompt_title)
        card_layout.addWidget(self._prompt, 1)
        card_layout.addWidget(interactive_hint)
        card_layout.addLayout(interactive_grid)
        card_layout.addLayout(cfg_grid)
        card_layout.addLayout(buttons)

        layout.addWidget(card, 1)

        self._tint_overlay = _EnvironmentTintOverlay(self, alpha=13)
        self._tint_overlay.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._tint_overlay.setGeometry(self.rect())
        self._tint_overlay.raise_()

    def _refresh_terminals(self) -> None:
        current = str(self._terminal.currentData() or "")
        options = detect_terminal_options()
        self._terminal.blockSignals(True)
        try:
            self._terminal.clear()
            for opt in options:
                self._terminal.addItem(opt.label, opt.terminal_id)
            desired = current
            if desired:
                idx = self._terminal.findData(desired)
                if idx >= 0:
                    self._terminal.setCurrentIndex(idx)
                    return
            if self._terminal.count() > 0:
                self._terminal.setCurrentIndex(0)
        finally:
            self._terminal.blockSignals(False)

    def _on_run(self) -> None:
        prompt = (self._prompt.toPlainText() or "").strip()
        if not prompt:
            QMessageBox.warning(self, "Missing prompt", "Enter a prompt first.")
            return
        prompt = sanitize_prompt(prompt)

        if not self._workspace_ready:
            QMessageBox.warning(
                self,
                "Workspace not configured",
                self._workspace_error or "Pick an environment with a local folder or GitHub repo configured.",
            )
            return

        host_codex = os.path.expanduser(str(self._host_codex_dir or "").strip())

        env_id = str(self._environment.currentData() or "")
        base_branch = str(self._base_branch.currentData() or "")
        self.requested_run.emit(prompt, host_codex, env_id, base_branch)

    def _on_get_agent_help(self) -> None:
        if not self._workspace_ready:
            QMessageBox.warning(
                self,
                "Workspace not configured",
                self._workspace_error or "Pick an environment with a local folder or GitHub repo configured.",
            )
            return

        user_question = sanitize_prompt((self._prompt.toPlainText() or "").strip())
        if not user_question:
            QMessageBox.warning(
                self,
                "Missing question",
                "Please type your question to get started with the help agent.",
            )
            return

        terminal_id = str(self._terminal.currentData() or "").strip()
        if not terminal_id:
            QMessageBox.warning(
                self,
                "No terminals found",
                "Could not detect an installed terminal emulator to launch.",
            )
            return

        helpme_path = Path(__file__).resolve().parent / "preflights" / "helpme.sh"
        try:
            helpme_script = helpme_path.read_text(encoding="utf-8")
        except Exception:
            helpme_script = ""
        if not helpme_script.strip():
            QMessageBox.warning(self, "Missing preflight", f"Could not load {helpme_path}")
            return

        host_codex = os.path.expanduser(str(self._host_codex_dir or "").strip())
        env_id = str(self._environment.currentData() or "")
        base_branch = str(self._base_branch.currentData() or "")

        command = (self._command.text() or "").strip()

        prompt = "\n".join(
            [
                "Get Agent Help",
                "",
                "User question:",
                user_question,
                "",
                "You are helping a user with Agents Runner and the Agent Runner GUI.",
                "",
                "Context:",
                "- You are running inside PixelArch Linux with passwordless sudo; install/update packages via `yay -Syu`.",
                "- Repos are already cloned locally in `~/.agent-help/repos/`: `Agents-Runner` (this project) plus agent repos (`codex`, `claude-code`, `copilot-cli`).",
                "",
                "The user already provided their question above; do not ask them what they need help with again.",
                "Answer the question directly. If a repo/path detail is required, ask one short clarifying question and then proceed.",
            ]
        )
        self.requested_launch.emit(
            prompt,
            command,
            host_codex,
            env_id,
            terminal_id,
            base_branch,
            helpme_script,
        )

    def _on_launch(self) -> None:
        prompt = sanitize_prompt((self._prompt.toPlainText() or "").strip())
        command = (self._command.text() or "").strip()

        if not self._workspace_ready:
            QMessageBox.warning(
                self,
                "Workspace not configured",
                self._workspace_error or "Pick an environment with a local folder or GitHub repo configured.",
            )
            return

        host_codex = os.path.expanduser(str(self._host_codex_dir or "").strip())

        terminal_id = str(self._terminal.currentData() or "").strip()
        if not terminal_id:
            QMessageBox.warning(
                self,
                "No terminals found",
                "Could not detect an installed terminal emulator to launch.",
            )
            return

        env_id = str(self._environment.currentData() or "")
        base_branch = str(self._base_branch.currentData() or "")
        self.requested_launch.emit(prompt, command, host_codex, env_id, terminal_id, base_branch, "")

    def _on_environment_changed(self, index: int) -> None:
        self._apply_environment_tints()
        self.environment_changed.emit(str(self._environment.currentData() or ""))

    def _apply_environment_tints(self) -> None:
        env_id = str(self._environment.currentData() or "")
        stain = (self._env_stains.get(env_id) or "").strip().lower() if env_id else ""
        if not stain:
            self._environment.setStyleSheet("")
            self._tint_overlay.set_tint_color(None)
            return

        _apply_environment_combo_tint(self._environment, stain)
        self._tint_overlay.set_tint_color(_stain_color(stain))

    def set_environment_stains(self, stains: dict[str, str]) -> None:
        self._env_stains = {str(k): str(v) for k, v in (stains or {}).items()}
        self._apply_environment_tints()

    def set_environments(self, envs: list[tuple[str, str]], active_id: str) -> None:
        current = str(self._environment.currentData() or "")
        self._environment.blockSignals(True)
        try:
            self._environment.clear()
            for env_id, name in envs:
                self._environment.addItem(name, env_id)
            desired = active_id or current
            idx = self._environment.findData(desired)
            if idx >= 0:
                self._environment.setCurrentIndex(idx)
        finally:
            self._environment.blockSignals(False)
        self._apply_environment_tints()

    def set_environment_id(self, env_id: str) -> None:
        idx = self._environment.findData(env_id)
        if idx >= 0:
            self._environment.setCurrentIndex(idx)
        self._apply_environment_tints()

    def set_defaults(self, host_codex: str) -> None:
        if host_codex:
            self._host_codex_dir = host_codex

    def set_workspace_status(self, *, path: str, ready: bool, message: str) -> None:
        self._workspace.setText(str(path or "—"))
        self._workspace_ready = bool(ready)
        self._workspace_error = str(message or "")

        hint = "" if self._workspace_ready else (self._workspace_error or "Workspace not configured.")
        self._workspace_hint.setText(hint)
        self._workspace_hint.setVisible(bool(hint))

        self._run_agent.setEnabled(self._workspace_ready)
        self._run_interactive.setEnabled(self._workspace_ready)
        self._get_agent_help.setEnabled(self._workspace_ready)

    def set_repo_controls_visible(self, visible: bool) -> None:
        visible = bool(visible)
        self._base_branch_label.setVisible(visible)
        self._base_branch.setVisible(visible)

    def set_repo_branches(self, branches: list[str], selected: str | None = None) -> None:
        wanted = str(selected or "").strip()
        self._base_branch.blockSignals(True)
        try:
            self._base_branch.clear()
            self._base_branch.addItem("Auto (default)", "")
            for name in branches or []:
                b = str(name or "").strip()
                if not b:
                    continue
                self._base_branch.addItem(b, b)
            if wanted:
                idx = self._base_branch.findData(wanted)
                if idx >= 0:
                    self._base_branch.setCurrentIndex(idx)
                    return
            self._base_branch.setCurrentIndex(0)
        finally:
            self._base_branch.blockSignals(False)

    def set_interactive_defaults(self, terminal_id: str, command: str) -> None:
        if command:
            self._command.setText(command)
        terminal_id = str(terminal_id or "")
        if terminal_id:
            idx = self._terminal.findData(terminal_id)
            if idx >= 0:
                self._terminal.setCurrentIndex(idx)

    def reset_for_new_run(self) -> None:
        self._prompt.setPlainText("")
        self._prompt.setFocus(Qt.OtherFocusReason)

    def focus_prompt(self) -> None:
        self._prompt.setFocus(Qt.OtherFocusReason)


class EnvironmentsPage(QWidget):
    back_requested = Signal()
    updated = Signal(str)
    test_preflight_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._environments: dict[str, Environment] = {}
        self._current_env_id: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        header = GlassCard()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 18, 16)
        header_layout.setSpacing(10)

        title = QLabel("Environments")
        title.setStyleSheet("font-size: 18px; font-weight: 750;")
        subtitle = QLabel("Saved locally in ~/.midoriai/codex-container-gui/state.json")
        subtitle.setStyleSheet("color: rgba(237, 239, 245, 160);")

        back = QToolButton()
        back.setText("Back")
        back.setToolButtonStyle(Qt.ToolButtonTextOnly)
        back.clicked.connect(self.back_requested.emit)

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle, 1)
        header_layout.addWidget(back, 0, Qt.AlignRight)
        layout.addWidget(header)

        card = GlassCard()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(12)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        self._env_select = QComboBox()
        self._env_select.currentIndexChanged.connect(self._on_env_selected)

        new_btn = QToolButton()
        new_btn.setText("New")
        new_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        new_btn.clicked.connect(self._on_new)

        delete_btn = QToolButton()
        delete_btn.setText("Delete")
        delete_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        delete_btn.clicked.connect(self._on_delete)

        save_btn = QToolButton()
        save_btn.setText("Save")
        save_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        save_btn.clicked.connect(self._on_save)

        test_btn = QToolButton()
        test_btn.setText("Test preflight")
        test_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        test_btn.clicked.connect(self._on_test_preflight)

        top_row.addWidget(QLabel("Environment"))
        top_row.addWidget(self._env_select, 1)
        top_row.addWidget(new_btn)
        top_row.addWidget(delete_btn)
        top_row.addWidget(test_btn)
        top_row.addWidget(save_btn)
        card_layout.addLayout(top_row)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        general_layout.setContentsMargins(0, 16, 0, 12)
        general_layout.setSpacing(10)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setContentsMargins(0, 0, 0, 0)

        self._name = QLineEdit()
        self._color = QComboBox()
        for stain in ALLOWED_STAINS:
            self._color.addItem(stain.title(), stain)

        self._host_codex_dir = QLineEdit()
        self._agent_cli_args = QLineEdit()
        self._agent_cli_args.setPlaceholderText("--model … (optional)")
        self._agent_cli_args.setToolTip(
            "Extra CLI flags appended to the agent command inside the container."
        )

        self._max_agents_running = QLineEdit()
        self._max_agents_running.setPlaceholderText("-1 (unlimited)")
        self._max_agents_running.setToolTip(
            "Maximum agents running at the same time for this environment. Set to -1 for no limit.\n"
            "Tip: For local-folder workspaces, set this to 1 to avoid agents fighting over setup/files."
        )
        self._max_agents_running.setValidator(QIntValidator(-1, 10_000_000, self))
        self._max_agents_running.setMaximumWidth(150)

        browse_codex = QPushButton("Browse…")
        browse_codex.setFixedWidth(100)
        browse_codex.clicked.connect(self._pick_codex_dir)

        grid.addWidget(QLabel("Name"), 0, 0)
        grid.addWidget(self._name, 0, 1, 1, 2)
        grid.addWidget(QLabel("Color"), 1, 0)
        grid.addWidget(self._color, 1, 1, 1, 2)
        grid.addWidget(QLabel("Default Host Config folder"), 2, 0)
        grid.addWidget(self._host_codex_dir, 2, 1)
        grid.addWidget(browse_codex, 2, 2)
        grid.addWidget(QLabel("Agent CLI Flags"), 3, 0)
        grid.addWidget(self._agent_cli_args, 3, 1, 1, 2)

        self._gh_pr_metadata_enabled = QCheckBox("Allow agent to set PR title/body (non-interactive only)")
        self._gh_pr_metadata_enabled.setToolTip(
            "When enabled and Workspace is a GitHub repo (clone), a per-task JSON file is mounted into the container.\n"
            "The agent is prompted to update it with a PR title/body, which will be used when opening the PR."
        )
        self._gh_pr_metadata_enabled.setEnabled(False)
        self._gh_pr_metadata_enabled.setVisible(True)

        max_agents_row = QWidget(general_tab)
        max_agents_row_layout = QHBoxLayout(max_agents_row)
        max_agents_row_layout.setContentsMargins(0, 0, 0, 0)
        max_agents_row_layout.setSpacing(10)
        max_agents_row_layout.addWidget(self._max_agents_running)
        max_agents_row_layout.addStretch(1)

        grid.addWidget(QLabel("Max agents running"), 4, 0)
        grid.addWidget(max_agents_row, 4, 1, 1, 2)

        self._gh_pr_metadata_label = QLabel("PR title/body")
        self._gh_pr_metadata_row = QWidget(general_tab)
        gh_pr_metadata_layout = QHBoxLayout(self._gh_pr_metadata_row)
        gh_pr_metadata_layout.setContentsMargins(0, 0, 0, 0)
        gh_pr_metadata_layout.setSpacing(10)
        gh_pr_metadata_layout.addWidget(self._gh_pr_metadata_enabled)
        gh_pr_metadata_layout.addStretch(1)

        self._gh_pr_metadata_label.setVisible(False)
        self._gh_pr_metadata_row.setVisible(False)
        grid.addWidget(self._gh_pr_metadata_label, 5, 0)
        grid.addWidget(self._gh_pr_metadata_row, 5, 1, 1, 2)

        self._gh_management_mode = QComboBox(general_tab)
        self._gh_management_mode.addItem("Use Settings workdir", GH_MANAGEMENT_NONE)
        self._gh_management_mode.addItem("Lock to local folder", GH_MANAGEMENT_LOCAL)
        self._gh_management_mode.addItem("Lock to GitHub repo (clone)", GH_MANAGEMENT_GITHUB)
        self._gh_management_mode.currentIndexChanged.connect(self._sync_gh_management_controls)

        self._gh_management_target = QLineEdit(general_tab)
        self._gh_management_target.setPlaceholderText("owner/repo, https://github.com/owner/repo, or /path/to/folder")
        self._gh_management_target.textChanged.connect(self._sync_gh_management_controls)

        self._gh_management_browse = QPushButton("Browse…", general_tab)
        self._gh_management_browse.setFixedWidth(100)
        self._gh_management_browse.clicked.connect(self._pick_gh_management_folder)

        self._gh_use_host_cli = QCheckBox("Use host `gh` for clone/PR (if installed)", general_tab)
        self._gh_use_host_cli.setToolTip("When disabled, cloning uses `git` and PR creation is skipped.")
        self._gh_use_host_cli.setVisible(False)

        self._gh_management_hint = QLabel(
            "Creates a per-task branch (midoriaiagents/<task_id>) and can push + open a PR via `gh`.\n"
            "Once saved, the target is locked; create a new environment to change it.",
            general_tab,
        )
        self._gh_management_hint.setStyleSheet("color: rgba(237, 239, 245, 150);")
        self._gh_management_mode.setVisible(False)
        self._gh_management_target.setVisible(False)
        self._gh_management_browse.setVisible(False)
        self._gh_management_hint.setVisible(False)

        general_layout.addLayout(grid)
        general_layout.addStretch(1)

        self._preflight_enabled = QCheckBox("Enable environment preflight bash (runs after Settings preflight)")
        self._preflight_script = QPlainTextEdit()
        self._preflight_script.setPlaceholderText(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "\n"
            "# Runs inside the container before the agent command.\n"
            "# Runs after Settings preflight (if enabled).\n"
        )
        self._preflight_script.setTabChangesFocus(True)
        self._preflight_enabled.toggled.connect(self._preflight_script.setEnabled)
        self._preflight_script.setEnabled(False)

        preflight_tab = QWidget()
        preflight_layout = QVBoxLayout(preflight_tab)
        preflight_layout.setSpacing(10)
        preflight_layout.setContentsMargins(0, 16, 0, 12)
        preflight_layout.addWidget(self._preflight_enabled)
        preflight_layout.addWidget(QLabel("Preflight script"))
        preflight_layout.addWidget(self._preflight_script, 1)

        self._env_vars = QPlainTextEdit()
        self._env_vars.setPlaceholderText("# KEY=VALUE (one per line)\n")
        self._env_vars.setTabChangesFocus(True)
        env_vars_tab = QWidget()
        env_vars_layout = QVBoxLayout(env_vars_tab)
        env_vars_layout.setSpacing(10)
        env_vars_layout.setContentsMargins(0, 16, 0, 12)
        env_vars_layout.addWidget(QLabel("Container env vars"))
        env_vars_layout.addWidget(self._env_vars, 1)

        self._mounts = QPlainTextEdit()
        self._mounts.setPlaceholderText("# host_path:container_path[:ro]\n")
        self._mounts.setTabChangesFocus(True)
        mounts_tab = QWidget()
        mounts_layout = QVBoxLayout(mounts_tab)
        mounts_layout.setSpacing(10)
        mounts_layout.setContentsMargins(0, 16, 0, 12)
        mounts_layout.addWidget(QLabel("Extra bind mounts"))
        mounts_layout.addWidget(self._mounts, 1)

        tabs.addTab(general_tab, "General")
        tabs.addTab(preflight_tab, "Preflight")
        tabs.addTab(env_vars_tab, "Env Vars")
        tabs.addTab(mounts_tab, "Mounts")

        card_layout.addWidget(tabs, 1)

        layout.addWidget(card, 1)

    def set_environments(self, envs: dict[str, Environment], active_id: str) -> None:
        self._environments = dict(envs)
        current = str(self._env_select.currentData() or "")

        self._env_select.blockSignals(True)
        try:
            self._env_select.clear()
            ordered = sorted(self._environments.values(), key=lambda e: (e.name or e.env_id).lower())
            for env in ordered:
                self._env_select.addItem(env.name or env.env_id, env.env_id)
            desired = active_id or current
            idx = self._env_select.findData(desired)
            if idx < 0 and self._env_select.count() > 0:
                idx = 0
            if idx >= 0:
                self._env_select.setCurrentIndex(idx)
        finally:
            self._env_select.blockSignals(False)

        self._load_selected()

    def _load_selected(self) -> None:
        env_id = str(self._env_select.currentData() or "")
        env = self._environments.get(env_id)
        self._current_env_id = env_id if env else None
        if not env:
            self._name.setText("")
            self._host_codex_dir.setText("")
            self._agent_cli_args.setText("")
            self._max_agents_running.setText("-1")
            self._gh_pr_metadata_enabled.setChecked(False)
            self._gh_pr_metadata_enabled.setEnabled(False)
            self._gh_pr_metadata_label.setVisible(False)
            self._gh_pr_metadata_row.setVisible(False)
            self._gh_management_mode.setCurrentIndex(0)
            self._gh_management_target.setText("")
            self._gh_use_host_cli.setChecked(bool(is_gh_available()))
            self._preflight_enabled.setChecked(False)
            self._preflight_script.setPlainText("")
            self._env_vars.setPlainText("")
            self._mounts.setPlainText("")
            self._sync_gh_management_controls()
            return

        self._name.setText(env.name)
        idx = self._color.findData(env.color)
        if idx >= 0:
            self._color.setCurrentIndex(idx)
        self._host_codex_dir.setText(env.host_codex_dir)
        self._agent_cli_args.setText(env.agent_cli_args)
        self._max_agents_running.setText(str(int(getattr(env, "max_agents_running", -1))))
        is_github_env = normalize_gh_management_mode(str(env.gh_management_mode or GH_MANAGEMENT_NONE)) == GH_MANAGEMENT_GITHUB
        self._gh_pr_metadata_enabled.setChecked(bool(getattr(env, "gh_pr_metadata_enabled", False)))
        self._gh_pr_metadata_enabled.setEnabled(is_github_env)
        self._gh_pr_metadata_label.setVisible(is_github_env)
        self._gh_pr_metadata_row.setVisible(is_github_env)
        idx = self._gh_management_mode.findData(normalize_gh_management_mode(env.gh_management_mode))
        if idx >= 0:
            self._gh_management_mode.setCurrentIndex(idx)
        self._gh_management_target.setText(str(env.gh_management_target or ""))
        self._gh_use_host_cli.setChecked(bool(getattr(env, "gh_use_host_cli", True)))
        self._sync_gh_management_controls(env=env)
        self._preflight_enabled.setChecked(bool(env.preflight_enabled))
        self._preflight_script.setEnabled(bool(env.preflight_enabled))
        self._preflight_script.setPlainText(env.preflight_script or "")
        env_lines = "\n".join(f"{k}={v}" for k, v in sorted(env.env_vars.items()))
        self._env_vars.setPlainText(env_lines)
        self._mounts.setPlainText("\n".join(env.extra_mounts))

    def _on_env_selected(self, index: int) -> None:
        self._load_selected()

    def _pick_codex_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select default host Config folder", self._host_codex_dir.text())
        if path:
            self._host_codex_dir.setText(path)

    def _pick_gh_management_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Select locked Workdir folder",
            self._gh_management_target.text() or os.getcwd(),
        )
        if path:
            self._gh_management_target.setText(path)

    def _sync_gh_management_controls(self, *_: object, env: Environment | None = None) -> None:
        if env is None:
            env = self._environments.get(str(self._current_env_id or ""))

        gh_available = bool(is_gh_available())
        mode = normalize_gh_management_mode(str(self._gh_management_mode.currentData() or GH_MANAGEMENT_NONE))
        locked = env is not None
        if locked and env is not None:
            desired_mode = normalize_gh_management_mode(env.gh_management_mode)
            if desired_mode != mode:
                idx = self._gh_management_mode.findData(desired_mode)
                if idx >= 0:
                    self._gh_management_mode.blockSignals(True)
                    try:
                        self._gh_management_mode.setCurrentIndex(idx)
                    finally:
                        self._gh_management_mode.blockSignals(False)
                mode = desired_mode
            desired_target = str(env.gh_management_target or "")
            if (self._gh_management_target.text() or "") != desired_target:
                self._gh_management_target.blockSignals(True)
                try:
                    self._gh_management_target.setText(desired_target)
                finally:
                    self._gh_management_target.blockSignals(False)
            desired_gh = bool(getattr(env, "gh_use_host_cli", True))
            if bool(self._gh_use_host_cli.isChecked()) != desired_gh:
                self._gh_use_host_cli.blockSignals(True)
                try:
                    self._gh_use_host_cli.setChecked(desired_gh)
                finally:
                    self._gh_use_host_cli.blockSignals(False)

        self._gh_management_mode.setEnabled(not locked)
        self._gh_management_target.setEnabled(not locked)
        self._gh_use_host_cli.setVisible(False)
        self._gh_use_host_cli.setEnabled(not locked and gh_available)
        if not gh_available:
            self._gh_use_host_cli.setChecked(False)

        wants_browse = mode == GH_MANAGEMENT_LOCAL
        self._gh_management_browse.setVisible(False)
        self._gh_management_browse.setEnabled(wants_browse and not locked)

    def _on_new(self) -> None:
        name, ok = QInputDialog.getText(self, "New environment", "Name")
        if not ok:
            return
        name = (name or "").strip() or "New environment"

        base = self._environments.get(str(self._env_select.currentData() or ""))
        env_id = f"env-{uuid4().hex[:8]}"
        color = "emerald"
        if base and base.color in ALLOWED_STAINS:
            idx = ALLOWED_STAINS.index(base.color)
            color = ALLOWED_STAINS[(idx + 1) % len(ALLOWED_STAINS)]

        workspace_labels = ["Lock to local folder", "Lock to GitHub repo (clone)"]
        selected_label, ok = QInputDialog.getItem(
            self,
            "Workspace",
            "Workspace type",
            workspace_labels,
            0,
            False,
        )
        if not ok:
            return

        gh_management_mode = GH_MANAGEMENT_LOCAL
        gh_management_target = ""
        gh_pr_metadata_enabled = False
        if selected_label == "Lock to GitHub repo (clone)":
            repo, ok = QInputDialog.getText(self, "GitHub repo", "Repo (owner/repo or URL)")
            if not ok:
                return
            repo = (repo or "").strip()
            if not repo:
                QMessageBox.warning(self, "Missing repo", "Enter a GitHub repo like owner/repo (or a URL).")
                return
            gh_management_mode = GH_MANAGEMENT_GITHUB
            gh_management_target = repo
            gh_pr_metadata_enabled = (
                QMessageBox.question(
                    self,
                    "PR metadata",
                    "Allow the agent to set the PR title/body via a mounted JSON file?\n\n"
                    "This is only used for non-interactive runs.",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                == QMessageBox.Yes
            )
        else:
            folder = QFileDialog.getExistingDirectory(self, "Select workspace folder", os.getcwd())
            if not folder:
                return
            gh_management_target = folder

        gh_use_host_cli = bool(getattr(base, "gh_use_host_cli", True)) if base else True
        if not is_gh_available():
            gh_use_host_cli = False
        try:
            max_agents_running = int(str(getattr(base, "max_agents_running", -1) if base else -1).strip())
        except Exception:
            max_agents_running = -1
        env = Environment(
            env_id=env_id,
            name=name,
            color=color,
            host_workdir="",
            host_codex_dir=base.host_codex_dir if base else "",
            agent_cli_args=base.agent_cli_args if base else "",
            max_agents_running=max_agents_running,
            preflight_enabled=base.preflight_enabled if base else False,
            preflight_script=base.preflight_script if base else "",
            env_vars=dict(base.env_vars) if base else {},
            extra_mounts=list(base.extra_mounts) if base else [],
            gh_management_mode=gh_management_mode,
            gh_management_target=gh_management_target,
            gh_management_locked=True,
            gh_use_host_cli=gh_use_host_cli,
            gh_pr_metadata_enabled=bool(gh_pr_metadata_enabled),
        )
        save_environment(env)
        self.updated.emit(env_id)

    def _on_delete(self) -> None:
        env_id = self._current_env_id
        env = self._environments.get(env_id or "")
        if not env:
            return
        confirm = QMessageBox.question(
            self,
            "Delete environment",
            f"Delete environment '{env.name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        delete_environment(env.env_id)
        self.updated.emit("")

    def _on_save(self) -> None:
        self.try_autosave()

    def try_autosave(self) -> bool:
        env_id = self._current_env_id
        if not env_id:
            return True
        name = (self._name.text() or "").strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Enter an environment name first.")
            return False

        existing = self._environments.get(env_id)
        host_codex_dir = os.path.expanduser((self._host_codex_dir.text() or "").strip())
        agent_cli_args = (self._agent_cli_args.text() or "").strip()
        max_agents_text = str(self._max_agents_running.text() or "-1").strip()
        try:
            max_agents_running = int(max_agents_text)
        except ValueError:
            max_agents_running = -1

        gh_mode = normalize_gh_management_mode(existing.gh_management_mode if existing else GH_MANAGEMENT_NONE)
        gh_target = str(existing.gh_management_target or "").strip() if existing else ""
        gh_locked = True
        gh_use_host_cli = bool(getattr(existing, "gh_use_host_cli", True)) if existing else False
        gh_pr_metadata_enabled = bool(getattr(existing, "gh_pr_metadata_enabled", False)) if existing else False

        if existing and gh_mode == GH_MANAGEMENT_GITHUB:
            gh_pr_metadata_enabled = bool(self._gh_pr_metadata_enabled.isChecked())
        elif gh_mode != GH_MANAGEMENT_GITHUB:
            gh_pr_metadata_enabled = False

        env_vars, errors = parse_env_vars_text(self._env_vars.toPlainText() or "")
        if errors:
            QMessageBox.warning(self, "Invalid env vars", "Fix env vars:\n" + "\n".join(errors[:12]))
            return False

        mounts = parse_mounts_text(self._mounts.toPlainText() or "")
        env = Environment(
            env_id=env_id,
            name=name,
            color=str(self._color.currentData() or "slate"),
            host_workdir="",
            host_codex_dir=host_codex_dir,
            agent_cli_args=agent_cli_args,
            max_agents_running=max_agents_running,
            preflight_enabled=bool(self._preflight_enabled.isChecked()),
            preflight_script=str(self._preflight_script.toPlainText() or ""),
            env_vars=env_vars,
            extra_mounts=mounts,
            gh_management_mode=gh_mode,
            gh_management_target=gh_target,
            gh_management_locked=gh_locked,
            gh_use_host_cli=gh_use_host_cli,
            gh_pr_metadata_enabled=gh_pr_metadata_enabled,
        )
        save_environment(env)
        self.updated.emit(env_id)
        return True

    def selected_environment_id(self) -> str:
        return str(self._env_select.currentData() or "")

    def _draft_environment_from_form(self) -> Environment | None:
        env_id = self._current_env_id
        if not env_id:
            return None

        existing = self._environments.get(env_id)
        host_codex_dir = os.path.expanduser((self._host_codex_dir.text() or "").strip())
        agent_cli_args = (self._agent_cli_args.text() or "").strip()
        max_agents_text = str(self._max_agents_running.text() or "-1").strip()
        try:
            max_agents_running = int(max_agents_text)
        except ValueError:
            max_agents_running = -1

        gh_mode = normalize_gh_management_mode(existing.gh_management_mode if existing else GH_MANAGEMENT_NONE)
        gh_target = str(existing.gh_management_target or "").strip() if existing else ""
        gh_locked = True
        gh_use_host_cli = bool(getattr(existing, "gh_use_host_cli", True)) if existing else False
        gh_pr_metadata_enabled = bool(getattr(existing, "gh_pr_metadata_enabled", False)) if existing else False

        if existing and gh_mode == GH_MANAGEMENT_GITHUB:
            gh_pr_metadata_enabled = bool(self._gh_pr_metadata_enabled.isChecked())
        elif gh_mode != GH_MANAGEMENT_GITHUB:
            gh_pr_metadata_enabled = False

        env_vars, errors = parse_env_vars_text(self._env_vars.toPlainText() or "")
        if errors:
            QMessageBox.warning(self, "Invalid env vars", "Fix env vars:\n" + "\n".join(errors[:12]))
            return None

        mounts = parse_mounts_text(self._mounts.toPlainText() or "")
        name = (self._name.text() or "").strip() or env_id
        return Environment(
            env_id=env_id,
            name=name,
            color=str(self._color.currentData() or "slate"),
            host_workdir="",
            host_codex_dir=host_codex_dir,
            agent_cli_args=agent_cli_args,
            max_agents_running=max_agents_running,
            preflight_enabled=bool(self._preflight_enabled.isChecked()),
            preflight_script=str(self._preflight_script.toPlainText() or ""),
            env_vars=env_vars,
            extra_mounts=mounts,
            gh_management_mode=gh_mode,
            gh_management_target=gh_target,
            gh_management_locked=gh_locked,
            gh_use_host_cli=gh_use_host_cli,
            gh_pr_metadata_enabled=gh_pr_metadata_enabled,
        )

    def _on_test_preflight(self) -> None:
        env = self._draft_environment_from_form()
        if env is None:
            return
        self.test_preflight_requested.emit(env)


class SettingsPage(QWidget):
    back_requested = Signal()
    saved = Signal(dict)
    test_preflight_requested = Signal(dict)
    clean_docker_requested = Signal()
    clean_git_folders_requested = Signal()
    clean_all_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        header = GlassCard()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 18, 16)
        header_layout.setSpacing(10)

        title = QLabel("Settings")
        title.setStyleSheet("font-size: 18px; font-weight: 750;")
        subtitle = QLabel("Saved locally in ~/.midoriai/codex-container-gui/state.json")
        subtitle.setStyleSheet("color: rgba(237, 239, 245, 160);")

        back = QToolButton()
        back.setText("Back")
        back.setToolButtonStyle(Qt.ToolButtonTextOnly)
        back.clicked.connect(self.back_requested.emit)

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle, 1)
        header_layout.addWidget(back, 0, Qt.AlignRight)
        layout.addWidget(header)

        card = GlassCard()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(12)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)

        self._use = QComboBox()
        self._use.addItem("Codex", "codex")
        self._use.addItem("Claude", "claude")
        self._use.addItem("GitHub Copilot", "copilot")

        self._shell = QComboBox()
        for label, value in [
            ("bash", "bash"),
            ("sh", "sh"),
            ("zsh", "zsh"),
            ("fish", "fish"),
            ("tmux", "tmux"),
        ]:
            self._shell.addItem(label, value)

        self._host_codex_dir = QLineEdit()
        self._host_codex_dir.setPlaceholderText(os.path.expanduser("~/.codex"))
        browse_codex = QPushButton("Browse…")
        browse_codex.setFixedWidth(100)
        browse_codex.clicked.connect(self._pick_codex_dir)

        self._host_claude_dir = QLineEdit()
        self._host_claude_dir.setPlaceholderText(os.path.expanduser("~/.claude"))
        browse_claude = QPushButton("Browse…")
        browse_claude.setFixedWidth(100)
        browse_claude.clicked.connect(self._pick_claude_dir)

        self._host_copilot_dir = QLineEdit()
        self._host_copilot_dir.setPlaceholderText(os.path.expanduser("~/.copilot"))
        browse_copilot = QPushButton("Browse…")
        browse_copilot.setFixedWidth(100)
        browse_copilot.clicked.connect(self._pick_copilot_dir)

        self._preflight_enabled = QCheckBox("Enable settings preflight bash (runs on all envs, before env preflight)")
        self._append_pixelarch_context = QCheckBox("Append PixelArch context")
        self._append_pixelarch_context.setToolTip(
            "When enabled, appends a short note to the end of the prompt passed to Run Agent.\n"
            "This never affects Run Interactive."
        )
        self._preflight_script = QPlainTextEdit()
        self._preflight_script.setPlaceholderText(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "\n"
            "# Runs inside the container before the agent command.\n"
            "# Runs on every environment, before environment preflight (if enabled).\n"
            "# This script is mounted read-only and deleted from the host after the task finishes.\n"
        )
        self._preflight_script.setTabChangesFocus(True)
        self._preflight_enabled.toggled.connect(self._preflight_script.setEnabled)
        self._preflight_script.setEnabled(False)

        grid.addWidget(QLabel("Agent CLI"), 0, 0)
        grid.addWidget(self._use, 0, 1)
        grid.addWidget(QLabel("Shell"), 0, 2)
        grid.addWidget(self._shell, 0, 3)
        codex_label = QLabel("Codex Config folder")
        claude_label = QLabel("Claude Config folder")
        copilot_label = QLabel("Copilot Config folder")

        grid.addWidget(codex_label, 1, 0)
        grid.addWidget(self._host_codex_dir, 1, 1, 1, 2)
        grid.addWidget(browse_codex, 1, 3)
        grid.addWidget(claude_label, 2, 0)
        grid.addWidget(self._host_claude_dir, 2, 1, 1, 2)
        grid.addWidget(browse_claude, 2, 3)
        grid.addWidget(copilot_label, 3, 0)
        grid.addWidget(self._host_copilot_dir, 3, 1, 1, 2)
        grid.addWidget(browse_copilot, 3, 3)
        grid.addWidget(self._preflight_enabled, 4, 0, 1, 4)
        grid.addWidget(self._append_pixelarch_context, 5, 0, 1, 4)

        self._agent_config_widgets: dict[str, tuple[QWidget, ...]] = {
            "codex": (codex_label, self._host_codex_dir, browse_codex),
            "claude": (claude_label, self._host_claude_dir, browse_claude),
            "copilot": (copilot_label, self._host_copilot_dir, browse_copilot),
        }
        self._use.currentIndexChanged.connect(self._sync_agent_config_widgets)
        self._sync_agent_config_widgets()

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self._clean_docker = QToolButton()
        self._clean_docker.setText("Clean Docker")
        self._clean_docker.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._clean_docker.setToolTip("Runs `docker system prune -fa` (destructive).")
        self._clean_docker.clicked.connect(self._on_clean_docker)
        self._clean_git_folders = QToolButton()
        self._clean_git_folders.setText("Clean Git Folders")
        self._clean_git_folders.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._clean_git_folders.setToolTip("Deletes the GUI-managed git repo checkouts (destructive).")
        self._clean_git_folders.clicked.connect(self._on_clean_git_folders)
        self._clean_all = QToolButton()
        self._clean_all.setText("Clean All")
        self._clean_all.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._clean_all.setToolTip("Runs all cleanup actions (destructive).")
        self._clean_all.clicked.connect(self._on_clean_all)
        save = QToolButton()
        save.setText("Save")
        save.setToolButtonStyle(Qt.ToolButtonTextOnly)
        save.clicked.connect(self._on_save)
        test = QToolButton()
        test.setText("Test preflights (all envs)")
        test.setToolButtonStyle(Qt.ToolButtonTextOnly)
        test.clicked.connect(self._on_test_preflight)
        buttons.addWidget(self._clean_docker)
        buttons.addWidget(self._clean_git_folders)
        buttons.addWidget(self._clean_all)
        buttons.addWidget(test)
        buttons.addWidget(save)
        buttons.addStretch(1)

        card_layout.addLayout(grid)
        card_layout.addWidget(QLabel("Preflight script"))
        card_layout.addWidget(self._preflight_script, 1)
        card_layout.addLayout(buttons)
        layout.addWidget(card, 1)

    def set_settings(self, settings: dict) -> None:
        use_value = normalize_agent(str(settings.get("use") or "codex"))
        self._set_combo_value(self._use, use_value, fallback="codex")
        self._sync_agent_config_widgets()

        shell_value = str(settings.get("shell") or "bash").strip().lower()
        self._set_combo_value(self._shell, shell_value, fallback="bash")

        host_codex_dir = os.path.expanduser(str(settings.get("host_codex_dir") or "").strip())
        if not host_codex_dir:
            host_codex_dir = os.path.expanduser("~/.codex")
        self._host_codex_dir.setText(host_codex_dir)

        host_claude_dir = os.path.expanduser(str(settings.get("host_claude_dir") or "").strip())
        self._host_claude_dir.setText(host_claude_dir)

        host_copilot_dir = os.path.expanduser(str(settings.get("host_copilot_dir") or "").strip())
        self._host_copilot_dir.setText(host_copilot_dir)

        enabled = bool(settings.get("preflight_enabled") or False)
        self._preflight_enabled.setChecked(enabled)
        self._preflight_script.setEnabled(enabled)
        self._preflight_script.setPlainText(str(settings.get("preflight_script") or ""))

        self._append_pixelarch_context.setChecked(bool(settings.get("append_pixelarch_context") or False))

    def get_settings(self) -> dict:
        return {
            "use": str(self._use.currentData() or "codex"),
            "shell": str(self._shell.currentData() or "bash"),
            "host_codex_dir": os.path.expanduser(str(self._host_codex_dir.text() or "").strip()),
            "host_claude_dir": os.path.expanduser(str(self._host_claude_dir.text() or "").strip()),
            "host_copilot_dir": os.path.expanduser(str(self._host_copilot_dir.text() or "").strip()),
            "preflight_enabled": bool(self._preflight_enabled.isChecked()),
            "preflight_script": str(self._preflight_script.toPlainText() or ""),
            "append_pixelarch_context": bool(self._append_pixelarch_context.isChecked()),
        }

    def _pick_codex_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Host Config folder",
            self._host_codex_dir.text() or os.path.expanduser("~/.codex"),
        )
        if path:
            self._host_codex_dir.setText(path)

    def _pick_claude_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Host Claude Config folder",
            self._host_claude_dir.text() or os.path.expanduser("~/.claude"),
        )
        if path:
            self._host_claude_dir.setText(path)

    def set_clean_state(self, *, docker_busy: bool, git_busy: bool, all_busy: bool) -> None:
        docker_busy = bool(docker_busy)
        git_busy = bool(git_busy)
        all_busy = bool(all_busy)
        self._clean_docker.setEnabled(not docker_busy and not all_busy)
        self._clean_docker.setText("Cleaning…" if docker_busy else "Clean Docker")
        self._clean_git_folders.setEnabled(not git_busy and not all_busy)
        self._clean_git_folders.setText("Cleaning…" if git_busy else "Clean Git Folders")
        self._clean_all.setEnabled(not all_busy and not docker_busy and not git_busy)
        self._clean_all.setText("Cleaning…" if all_busy else "Clean All")

    def _on_clean_docker(self) -> None:
        btn = QMessageBox.question(
            self,
            "Clean Docker",
            "This will run `docker system prune -fa`.\n\n"
            "It will remove unused images, containers, networks, and build cache.\n"
            "This cannot be undone.\n\n"
            "Are you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if btn != QMessageBox.StandardButton.Yes:
            return
        self.clean_docker_requested.emit()

    def _on_clean_git_folders(self) -> None:
        path = managed_repos_dir(data_dir=os.path.dirname(default_state_path()))
        btn = QMessageBox.question(
            self,
            "Clean Git Folders",
            "This will delete the GUI-managed git repo folders on disk:\n\n"
            f"{path}\n\n"
            "This cannot be undone.\n\n"
            "Are you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if btn != QMessageBox.StandardButton.Yes:
            return
        self.clean_git_folders_requested.emit()

    def _on_clean_all(self) -> None:
        path = managed_repos_dir(data_dir=os.path.dirname(default_state_path()))
        btn = QMessageBox.question(
            self,
            "Clean All",
            "This will run all cleanup actions:\n\n"
            "1) `docker system prune -fa`\n"
            "2) delete GUI-managed git folders:\n"
            f"   {path}\n\n"
            "This cannot be undone.\n\n"
            "Are you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if btn != QMessageBox.StandardButton.Yes:
            return
        self.clean_all_requested.emit()

    def _pick_copilot_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Host Copilot Config folder",
            self._host_copilot_dir.text() or os.path.expanduser("~/.copilot"),
        )
        if path:
            self._host_copilot_dir.setText(path)

    def _on_save(self) -> None:
        self.try_autosave()

    def try_autosave(self) -> bool:
        self.saved.emit(self.get_settings())
        return True

    def _on_test_preflight(self) -> None:
        self.test_preflight_requested.emit(self.get_settings())

    def _sync_agent_config_widgets(self) -> None:
        use_value = normalize_agent(str(self._use.currentData() or "codex"))
        for agent, widgets in self._agent_config_widgets.items():
            visible = agent == use_value
            for widget in widgets:
                widget.setVisible(visible)

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: str, fallback: str) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return
        idx = combo.findData(fallback)
        if idx >= 0:
            combo.setCurrentIndex(idx)


class MainWindow(QMainWindow):
    host_log = Signal(str, str)
    host_pr_url = Signal(str, str)
    interactive_finished = Signal(str, int)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(1024, 640)
        self.resize(1280, 720)

        self._settings_data: dict[str, object] = {
            "use": "codex",
            "shell": "bash",
            "preflight_enabled": False,
            "preflight_script": "",
            "host_workdir": os.environ.get("CODEX_HOST_WORKDIR", os.getcwd()),
            "host_codex_dir": os.environ.get("CODEX_HOST_CODEX_DIR", os.path.expanduser("~/.codex")),
            "host_claude_dir": "",
            "host_copilot_dir": "",
            "active_environment_id": "default",
            "interactive_terminal_id": "",
            "interactive_command": "--sandbox danger-full-access",
            "interactive_command_claude": "--add-dir /home/midori-ai/workspace",
            "interactive_command_copilot": "--add-dir /home/midori-ai/workspace",
            "window_w": 1280,
            "window_h": 720,
            "max_agents_running": -1,
            "append_pixelarch_context": False,
        }
        self._environments: dict[str, Environment] = {}
        self._syncing_environment = False
        self._tasks: dict[str, Task] = {}
        self._threads: dict[str, QThread] = {}
        self._bridges: dict[str, TaskRunnerBridge] = {}
        self._run_started_s: dict[str, float] = {}
        self._dashboard_log_refresh_s: dict[str, float] = {}
        self._interactive_watch: dict[str, tuple[str, threading.Event]] = {}
        self._state_path = default_state_path()
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(450)
        self._save_timer.timeout.connect(self._save_state)

        self.host_log.connect(self._on_host_log, Qt.QueuedConnection)
        self.host_pr_url.connect(self._on_host_pr_url, Qt.QueuedConnection)
        self.interactive_finished.connect(self._on_interactive_finished, Qt.QueuedConnection)

        self._dashboard_ticker = QTimer(self)
        self._dashboard_ticker.setInterval(1000)
        self._dashboard_ticker.timeout.connect(self._tick_dashboard_elapsed)
        self._dashboard_ticker.start()

        root = GlassRoot()
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        top = GlassCard()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(14, 12, 14, 12)
        top_layout.setSpacing(10)

        self._btn_home = QToolButton()
        self._btn_home.setText("Home")
        self._btn_home.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn_home.setIcon(self.style().standardIcon(QStyle.SP_DirHomeIcon))
        self._btn_home.clicked.connect(self._show_dashboard)

        self._btn_new = QToolButton()
        self._btn_new.setText("New task")
        self._btn_new.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn_new.setIcon(self.style().standardIcon(QStyle.SP_FileDialogNewFolder))
        self._btn_new.clicked.connect(self._show_new_task)

        self._btn_envs = QToolButton()
        self._btn_envs.setText("Environments")
        self._btn_envs.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn_envs.setIcon(self.style().standardIcon(QStyle.SP_DirIcon))
        self._btn_envs.clicked.connect(self._show_environments)

        self._btn_settings = QToolButton()
        self._btn_settings.setText("Settings")
        self._btn_settings.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn_settings.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self._btn_settings.clicked.connect(self._show_settings)

        top_layout.addWidget(self._btn_home)
        top_layout.addWidget(self._btn_new)
        top_layout.addWidget(self._btn_envs)
        top_layout.addWidget(self._btn_settings)
        top_layout.addStretch(1)

        outer.addWidget(top)

        self._dashboard = DashboardPage()
        self._dashboard.task_selected.connect(self._open_task_details)
        self._dashboard.clean_old_requested.connect(self._clean_old_tasks)
        self._dashboard.task_discard_requested.connect(self._discard_task_from_ui)
        self._new_task = NewTaskPage()
        self._new_task.requested_run.connect(self._start_task_from_ui)
        self._new_task.requested_launch.connect(self._start_interactive_task_from_ui)
        self._new_task.environment_changed.connect(self._on_new_task_env_changed)
        self._new_task.back_requested.connect(self._show_dashboard)
        self._details = TaskDetailsPage()
        self._details.back_requested.connect(self._show_dashboard)
        self._envs_page = EnvironmentsPage()
        self._envs_page.back_requested.connect(self._show_dashboard)
        self._envs_page.updated.connect(self._reload_environments, Qt.QueuedConnection)
        self._envs_page.test_preflight_requested.connect(self._on_environment_test_preflight, Qt.QueuedConnection)
        self._settings = SettingsPage()
        self._settings.back_requested.connect(self._show_dashboard)
        self._settings.saved.connect(self._apply_settings, Qt.QueuedConnection)
        self._settings.test_preflight_requested.connect(self._on_settings_test_preflight, Qt.QueuedConnection)
        self._settings.clean_docker_requested.connect(self._on_settings_clean_docker, Qt.QueuedConnection)
        self._settings.clean_git_folders_requested.connect(self._on_settings_clean_git_folders, Qt.QueuedConnection)
        self._settings.clean_all_requested.connect(self._on_settings_clean_all, Qt.QueuedConnection)
        self._cleanup_threads: dict[str, QThread] = {}
        self._cleanup_bridges: dict[str, HostCleanupBridge] = {}
        self._docker_cleanup_task_id: str | None = None
        self._git_cleanup_task_id: str | None = None
        self._clean_all_queue: list[str] = []

        self._stack = QWidget()
        self._stack_layout = QVBoxLayout(self._stack)
        self._stack_layout.setContentsMargins(0, 0, 0, 0)
        self._stack_layout.setSpacing(0)
        self._stack_layout.addWidget(self._dashboard)
        self._stack_layout.addWidget(self._new_task)
        self._stack_layout.addWidget(self._details)
        self._stack_layout.addWidget(self._envs_page)
        self._stack_layout.addWidget(self._settings)
        self._dashboard.show()
        self._new_task.hide()
        self._details.hide()
        self._envs_page.hide()
        self._settings.hide()
        outer.addWidget(self._stack, 1)

        self._load_state()
        self._apply_window_prefs()
        self._reload_environments()
        self._apply_settings_to_pages()
        self._sync_settings_clean_state()

    def _on_settings_clean_docker(self) -> None:
        if shutil.which("docker") is None:
            QMessageBox.critical(self, "Docker not found", "Could not find `docker` in PATH.")
            return
        if self._docker_cleanup_task_id is not None:
            QMessageBox.information(self, "Clean Docker", "A Docker cleanup is already running.")
            return

        self._docker_cleanup_task_id = self._start_cleanup_task(
            kind="docker",
            label="Clean Docker",
            target=str(self._settings_data.get("host_workdir") or os.getcwd()),
            runner=self._run_docker_prune,
        )
        self._sync_settings_clean_state()

    def _on_settings_clean_git_folders(self) -> None:
        if self._git_cleanup_task_id is not None:
            QMessageBox.information(self, "Clean Git Folders", "A git cleanup is already running.")
            return

        target = managed_repos_dir(data_dir=os.path.dirname(self._state_path))
        self._git_cleanup_task_id = self._start_cleanup_task(
            kind="git",
            label="Clean Git Folders",
            target=target,
            runner=self._run_clean_git_folders,
        )
        self._sync_settings_clean_state()

    def _on_settings_clean_all(self) -> None:
        if self._clean_all_queue:
            QMessageBox.information(self, "Clean All", "A Clean All run is already in progress.")
            return
        if self._docker_cleanup_task_id is not None or self._git_cleanup_task_id is not None:
            QMessageBox.information(
                self,
                "Clean All",
                "Finish the currently running cleanup first.",
            )
            return
        self._clean_all_queue = ["docker", "git"]
        self._sync_settings_clean_state()
        self._start_next_clean_all_step()

    def _sync_settings_clean_state(self) -> None:
        self._settings.set_clean_state(
            docker_busy=self._docker_cleanup_task_id is not None,
            git_busy=self._git_cleanup_task_id is not None,
            all_busy=bool(self._clean_all_queue),
        )

    def _start_next_clean_all_step(self) -> None:
        if not self._clean_all_queue:
            self._sync_settings_clean_state()
            return
        kind = str(self._clean_all_queue[0] or "").strip().lower()
        if kind == "docker":
            self._on_settings_clean_docker()
            return
        if kind == "git":
            self._on_settings_clean_git_folders()
            return
        self._clean_all_queue.pop(0)
        self._start_next_clean_all_step()

    @staticmethod
    def _format_cmd(args: list[str]) -> str:
        return " ".join(shlex.quote(str(a)) for a in args)

    def _start_cleanup_task(
        self,
        *,
        kind: str,
        label: str,
        target: str,
        runner: Callable[[Callable[[str], None], threading.Event], tuple[int, str]],
    ) -> str:
        task_id = uuid4().hex[:10]
        task = Task(
            task_id=task_id,
            prompt=str(label or "Cleanup").strip(),
            image="",
            host_workdir=str(target or "").strip(),
            host_codex_dir="",
            created_at_s=time.time(),
            status="cleaning",
        )
        task.started_at = datetime.now(tz=timezone.utc)
        self._tasks[task_id] = task
        self._dashboard.upsert_task(task, stain="slate")
        self._schedule_save()

        bridge = HostCleanupBridge(runner)
        thread = QThread(self)
        bridge.moveToThread(thread)
        thread.started.connect(bridge.run)

        bridge.log.connect(lambda line, tid=task_id: self.host_log.emit(tid, line), Qt.QueuedConnection)
        bridge.done.connect(
            lambda code, output, tid=task_id, k=kind: self._on_cleanup_done(tid, k, int(code), str(output or "")),
            Qt.QueuedConnection,
        )

        bridge.done.connect(thread.quit, Qt.QueuedConnection)
        bridge.done.connect(bridge.deleteLater, Qt.QueuedConnection)
        thread.finished.connect(thread.deleteLater)

        self._cleanup_threads[task_id] = thread
        self._cleanup_bridges[task_id] = bridge

        thread.start()
        self._show_dashboard()
        return task_id

    def _finalize_cleanup_task(self, task_id: str, exit_code: int, *, error: str | None = None) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        task.exit_code = int(exit_code)
        task.error = str(error) if error else None
        task.status = "done" if int(exit_code) == 0 else "failed"
        task.finished_at = datetime.now(tz=timezone.utc)
        self._dashboard.upsert_task(task)
        self._details.update_task(task)
        self._schedule_save()

    def _on_cleanup_done(self, task_id: str, kind: str, exit_code: int, output: str) -> None:
        kind = str(kind or "").strip().lower()
        self._cleanup_threads.pop(task_id, None)
        self._cleanup_bridges.pop(task_id, None)

        output = str(output or "").strip()
        if not output:
            output = f"Command exited with code {int(exit_code)}."

        self._finalize_cleanup_task(task_id, int(exit_code))

        if kind == "docker":
            self._docker_cleanup_task_id = None
            title = "Docker cleaned" if int(exit_code) == 0 else "Docker cleanup failed"
        else:
            self._git_cleanup_task_id = None
            title = "Git folders cleaned" if int(exit_code) == 0 else "Git folders cleanup failed"

        self._sync_settings_clean_state()

        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(title)
        box.setDetailedText(output)
        box.setIcon(QMessageBox.Icon.Information if int(exit_code) == 0 else QMessageBox.Icon.Critical)
        box.exec()

        if self._clean_all_queue and self._clean_all_queue[0] == kind:
            self._clean_all_queue.pop(0)
            self._sync_settings_clean_state()
            self._start_next_clean_all_step()

    def _run_docker_prune(
        self,
        log: Callable[[str], None],
        stop: threading.Event,
    ) -> tuple[int, str]:
        docker_args = ["docker", "system", "prune", "-f", "-a"]
        args = ["sudo", "-n", *docker_args] if shutil.which("sudo") else docker_args
        log(f"$ {self._format_cmd(args)}")
        output_lines: list[str] = []
        try:
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except Exception as exc:
            return 1, str(exc)
        assert proc.stdout is not None
        for raw in proc.stdout:
            if stop.is_set():
                try:
                    proc.terminate()
                except Exception:
                    pass
                break
            line = str(raw or "").rstrip("\n")
            if line:
                log(line)
                output_lines.append(line)
        try:
            exit_code = int(proc.wait(timeout=60.0))
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
            exit_code = 1
        output = "\n".join(output_lines).strip()
        if not output:
            output = f"Command exited with code {exit_code}."
        return exit_code, output

    def _run_clean_git_folders(
        self,
        log: Callable[[str], None],
        stop: threading.Event,
    ) -> tuple[int, str]:
        data_dir = os.path.dirname(self._state_path)
        target = managed_repos_dir(data_dir=data_dir)
        log(f"Target: {target}")

        target_real = os.path.realpath(target)
        data_real = os.path.realpath(data_dir)
        if not (target_real == data_real or target_real.startswith(data_real + os.sep)):
            msg = f"Refusing to delete unexpected path: {target_real}"
            log(msg)
            return 1, msg

        if not os.path.exists(target):
            msg = "Nothing to clean."
            log(msg)
            return 0, msg

        if stop.is_set():
            return 1, "Cancelled."

        args = ["sudo", "-n", "rm", "-rf", target] if shutil.which("sudo") else ["rm", "-rf", target]
        log(f"$ {self._format_cmd(args)}")
        try:
            proc = subprocess.run(args, capture_output=True, text=True, check=False)
        except Exception as exc:
            return 1, str(exc)

        output = "\n".join([str(proc.stdout or "").strip(), str(proc.stderr or "").strip()]).strip()
        if not output:
            output = f"Command exited with code {proc.returncode}."
        return int(proc.returncode), output

    def _count_running_agents(self, env_id: str | None = None) -> int:
        count = 0
        env_id = str(env_id or "").strip() or None
        for task in self._tasks.values():
            if env_id and str(getattr(task, "environment_id", "") or "") != env_id:
                continue
            if task.status.lower() in {"pulling", "created", "running", "starting"}:
                count += 1
        return count

    def _max_agents_running_for_env(self, env_id: str | None) -> int:
        env_id = str(env_id or "").strip()
        env = self._environments.get(env_id) if env_id else None
        if env is not None:
            try:
                return int(getattr(env, "max_agents_running", -1))
            except Exception:
                return -1
        try:
            return int(self._settings_data.get("max_agents_running", -1))
        except Exception:
            return -1

    def _can_start_new_agent_for_env(self, env_id: str | None) -> bool:
        max_agents = self._max_agents_running_for_env(env_id)
        if max_agents < 0:
            return True
        return self._count_running_agents(env_id) < max_agents

    def _try_start_queued_tasks(self) -> None:
        queued = [t for t in self._tasks.values() if t.status.lower() == "queued"]
        if not queued:
            return
        queued.sort(key=lambda t: t.created_at_s)
        for task in queued:
            if not self._can_start_new_agent_for_env(getattr(task, "environment_id", "")):
                continue
            self._actually_start_task(task)

    def _apply_window_prefs(self) -> None:
        try:
            w = int(self._settings_data.get("window_w") or 1280)
            h = int(self._settings_data.get("window_h") or 720)
        except Exception:
            w, h = 1280, 720
        w = max(int(self.minimumWidth()), w)
        h = max(int(self.minimumHeight()), h)
        self.resize(w, h)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._settings_data["window_w"] = int(self.width())
        self._settings_data["window_h"] = int(self.height())
        if hasattr(self, "_save_timer"):
            self._schedule_save()

    def _show_dashboard(self) -> None:
        if not self._try_autosave_before_navigation():
            return
        self._new_task.hide()
        self._details.hide()
        self._envs_page.hide()
        self._settings.hide()
        self._dashboard.show()

    def _show_new_task(self) -> None:
        if not self._try_autosave_before_navigation():
            return
        self._dashboard.hide()
        self._details.hide()
        self._envs_page.hide()
        self._settings.hide()
        self._new_task.focus_prompt()
        self._new_task.show()

    def _show_task_details(self) -> None:
        if not self._try_autosave_before_navigation():
            return
        self._dashboard.hide()
        self._new_task.hide()
        self._envs_page.hide()
        self._settings.hide()
        self._details.show()

    def _show_environments(self) -> None:
        if self._envs_page.isVisible():
            return
        if not self._try_autosave_before_navigation():
            return
        self._dashboard.hide()
        self._new_task.hide()
        self._details.hide()
        self._settings.hide()
        self._envs_page.set_environments(self._environments, self._active_environment_id())
        self._envs_page.show()

    def _show_settings(self) -> None:
        if self._settings.isVisible():
            return
        if not self._try_autosave_before_navigation():
            return
        self._dashboard.hide()
        self._new_task.hide()
        self._details.hide()
        self._envs_page.hide()
        self._settings.set_settings(self._settings_data)
        self._settings.show()

    def _try_autosave_before_navigation(self) -> bool:
        if self._envs_page.isVisible() and not self._envs_page.try_autosave():
            return False
        if self._settings.isVisible() and not self._settings.try_autosave():
            return False
        return True

    def _apply_settings_to_pages(self) -> None:
        self._settings.set_settings(self._settings_data)
        self._apply_active_environment_to_new_task()

    def _apply_settings(self, settings: dict) -> None:
        merged = dict(self._settings_data)
        merged.update(settings or {})
        merged["use"] = normalize_agent(str(merged.get("use") or "codex"))

        shell_value = str(merged.get("shell") or "bash").lower()
        if shell_value not in {"bash", "sh", "zsh", "fish", "tmux"}:
            shell_value = "bash"
        merged["shell"] = shell_value

        host_codex_dir = os.path.expanduser(str(merged.get("host_codex_dir") or "").strip())
        if not host_codex_dir:
            host_codex_dir = os.path.expanduser("~/.codex")
        merged["host_codex_dir"] = host_codex_dir

        merged["host_claude_dir"] = os.path.expanduser(str(merged.get("host_claude_dir") or "").strip())
        merged["host_copilot_dir"] = os.path.expanduser(str(merged.get("host_copilot_dir") or "").strip())

        merged["preflight_enabled"] = bool(merged.get("preflight_enabled") or False)
        merged["preflight_script"] = str(merged.get("preflight_script") or "")
        merged["interactive_command"] = str(merged.get("interactive_command") or "--sandbox danger-full-access")
        merged["interactive_command_claude"] = str(merged.get("interactive_command_claude") or "")
        merged["interactive_command_copilot"] = str(merged.get("interactive_command_copilot") or "")
        for key in ("interactive_command", "interactive_command_claude", "interactive_command_copilot"):
            merged[key] = self._sanitize_interactive_command_value(key, merged.get(key))
        merged["append_pixelarch_context"] = bool(merged.get("append_pixelarch_context") or False)

        try:
            merged["max_agents_running"] = int(str(merged.get("max_agents_running", -1)).strip())
        except Exception:
            merged["max_agents_running"] = -1
        self._settings_data = merged
        self._apply_settings_to_pages()
        self._schedule_save()

    def _interactive_command_key(self, agent_cli: str) -> str:
        agent_cli = normalize_agent(agent_cli)
        if agent_cli == "claude":
            return "interactive_command_claude"
        if agent_cli == "copilot":
            return "interactive_command_copilot"
        return "interactive_command"

    def _host_config_dir_key(self, agent_cli: str) -> str:
        agent_cli = normalize_agent(agent_cli)
        if agent_cli == "claude":
            return "host_claude_dir"
        if agent_cli == "copilot":
            return "host_copilot_dir"
        return "host_codex_dir"

    def _default_interactive_command(self, agent_cli: str) -> str:
        agent_cli = normalize_agent(agent_cli)
        if agent_cli == "claude":
            return "--add-dir /home/midori-ai/workspace"
        if agent_cli == "copilot":
            return "--add-dir /home/midori-ai/workspace"
        return "--sandbox danger-full-access"

    def _sanitize_interactive_command_value(self, key: str, raw: object) -> str:
        value = str(raw or "").strip()
        if not value:
            return ""

        try:
            cmd_parts = shlex.split(value)
        except ValueError:
            cmd_parts = []
        if cmd_parts and cmd_parts[0] in {"codex", "claude", "copilot"}:
            head = cmd_parts.pop(0)
            if head == "codex" and cmd_parts and cmd_parts[0] == "exec":
                cmd_parts.pop(0)
            value = " ".join(shlex.quote(part) for part in cmd_parts)

        if _looks_like_agent_help_command(value):
            agent_cli = "codex"
            if str(key or "").endswith("_claude"):
                agent_cli = "claude"
            elif str(key or "").endswith("_copilot"):
                agent_cli = "copilot"
            return self._default_interactive_command(agent_cli)

        return value

    @staticmethod
    def _is_agent_help_interactive_launch(prompt: str, command: str) -> bool:
        prompt = str(prompt or "").strip().lower()
        if prompt.startswith("get agent help"):
            return True
        return _looks_like_agent_help_command(command)

    def _effective_host_config_dir(
        self,
        *,
        agent_cli: str,
        env: Environment | None,
        settings: dict[str, object] | None = None,
    ) -> str:
        agent_cli = normalize_agent(agent_cli)
        settings = settings or self._settings_data

        config_dir = ""
        if agent_cli == "claude":
            config_dir = str(settings.get("host_claude_dir") or "")
        elif agent_cli == "copilot":
            config_dir = str(settings.get("host_copilot_dir") or "")
        else:
            config_dir = str(
                settings.get("host_codex_dir")
                or os.environ.get("CODEX_HOST_CODEX_DIR", os.path.expanduser("~/.codex"))
            )
        if env and env.host_codex_dir:
            config_dir = env.host_codex_dir
        return os.path.expanduser(str(config_dir or "").strip())

    def _ensure_agent_config_dir(self, agent_cli: str, host_config_dir: str) -> bool:
        agent_cli = normalize_agent(agent_cli)
        host_config_dir = os.path.expanduser(str(host_config_dir or "").strip())
        if agent_cli in {"claude", "copilot"} and not host_config_dir:
            agent_label = "Claude" if agent_cli == "claude" else "Copilot"
            QMessageBox.warning(
                self,
                "Missing config folder",
                f"Set the {agent_label} Config folder in Settings (or override it per-environment).",
            )
            return False
        if not host_config_dir:
            return False
        if os.path.exists(host_config_dir) and not os.path.isdir(host_config_dir):
            QMessageBox.warning(self, "Invalid config folder", "Config folder path is not a directory.")
            return False
        try:
            os.makedirs(host_config_dir, exist_ok=True)
        except Exception as exc:
            QMessageBox.warning(self, "Invalid config folder", str(exc))
            return False
        return True

    def _active_environment_id(self) -> str:
        return str(self._settings_data.get("active_environment_id") or "default")

    def _environment_list(self) -> list[Environment]:
        return sorted(self._environments.values(), key=lambda e: (e.name or e.env_id).lower())

    def _environment_effective_workdir(self, env: Environment | None, fallback: str) -> str:
        fallback = os.path.expanduser(str(fallback or "").strip()) or os.getcwd()
        if env is None:
            return fallback
        gh_mode = normalize_gh_management_mode(str(env.gh_management_mode or GH_MANAGEMENT_NONE))
        if gh_mode == GH_MANAGEMENT_LOCAL:
            return os.path.expanduser(str(env.gh_management_target or "").strip())
        if gh_mode == GH_MANAGEMENT_GITHUB:
            workdir = managed_repo_checkout_path(env.env_id, data_dir=os.path.dirname(self._state_path))
            try:
                os.makedirs(workdir, exist_ok=True)
            except Exception:
                pass
            return workdir
        return fallback

    def _new_task_workspace(self, env: Environment | None) -> tuple[str, bool, str]:
        if env is None:
            return "—", False, "Pick an environment first."

        gh_mode = normalize_gh_management_mode(str(env.gh_management_mode or GH_MANAGEMENT_NONE))
        if gh_mode == GH_MANAGEMENT_LOCAL:
            path = os.path.expanduser(str(env.gh_management_target or "").strip())
            if not path:
                return "—", False, "Set Workspace to a local folder in Environments."
            if not os.path.isdir(path):
                return path, False, f"Local folder does not exist: {path}"
            return path, True, ""

        if gh_mode == GH_MANAGEMENT_GITHUB:
            path = managed_repo_checkout_path(env.env_id, data_dir=os.path.dirname(self._state_path))
            target = str(env.gh_management_target or "").strip()
            if not target:
                return path, False, "Set Workspace to a GitHub repo in Environments."
            return path, True, ""

        return "—", False, "Set Workspace to a local folder or GitHub repo in Environments."

    def _sync_new_task_repo_controls(self, env: Environment | None) -> None:
        workdir, ready, _ = self._new_task_workspace(env)
        if not ready:
            self._new_task.set_repo_controls_visible(False)
            self._new_task.set_repo_branches([])
            return

        gh_mode = normalize_gh_management_mode(str(env.gh_management_mode or GH_MANAGEMENT_NONE)) if env else GH_MANAGEMENT_NONE
        has_repo = bool(gh_mode == GH_MANAGEMENT_GITHUB)
        if gh_mode == GH_MANAGEMENT_NONE or not has_repo:
            self._new_task.set_repo_controls_visible(False)
            self._new_task.set_repo_branches([])
            return

        branches: list[str] = []
        if gh_mode == GH_MANAGEMENT_GITHUB and env:
            branches = git_list_remote_heads(str(env.gh_management_target or ""))

        self._new_task.set_repo_controls_visible(True)
        self._new_task.set_repo_branches(branches)

    def _populate_environment_pickers(self) -> None:
        active_id = self._active_environment_id()
        envs = self._environment_list()
        stains = {e.env_id: e.color for e in envs}

        self._new_task.set_environment_stains(stains)
        self._dashboard.set_environment_filter_options([(e.env_id, e.name or e.env_id) for e in envs])

        self._syncing_environment = True
        try:
            self._new_task.set_environments([(e.env_id, e.name or e.env_id) for e in envs], active_id=active_id)
            self._new_task.set_environment_id(active_id)
        finally:
            self._syncing_environment = False

    def _apply_active_environment_to_new_task(self) -> None:
        env = self._environments.get(self._active_environment_id())
        agent_cli = normalize_agent(str(self._settings_data.get("use") or "codex"))
        host_codex = self._effective_host_config_dir(agent_cli=agent_cli, env=env)
        workdir, ready, message = self._new_task_workspace(env)
        self._new_task.set_defaults(host_codex=host_codex)
        self._new_task.set_workspace_status(path=workdir, ready=ready, message=message)
        self._sync_new_task_repo_controls(env)
        interactive_key = self._interactive_command_key(agent_cli)
        interactive_command = str(self._settings_data.get(interactive_key) or "").strip()
        if not interactive_command:
            interactive_command = self._default_interactive_command(agent_cli)
        self._new_task.set_interactive_defaults(
            terminal_id=str(self._settings_data.get("interactive_terminal_id") or ""),
            command=interactive_command,
        )
        self._populate_environment_pickers()

    def _on_new_task_env_changed(self, env_id: str) -> None:
        if self._syncing_environment:
            return
        env_id = str(env_id or "")
        if env_id and env_id in self._environments:
            self._settings_data["active_environment_id"] = env_id
            self._apply_active_environment_to_new_task()
            self._schedule_save()

    def _refresh_task_rows(self) -> None:
        for task in self._tasks.values():
            env = self._environments.get(task.environment_id)
            stain = env.color if env else None
            spinner = _stain_color(env.color) if env else None
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)

    def _tick_dashboard_elapsed(self) -> None:
        if not self._dashboard.isVisible():
            return
        for task in self._tasks.values():
            if not task.is_active():
                continue
            env = self._environments.get(task.environment_id)
            stain = env.color if env else None
            spinner = _stain_color(env.color) if env else None
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)

    def _reload_environments(self, preferred_env_id: str = "") -> None:
        envs = load_environments()
        if not envs:
            active_workdir = str(self._settings_data.get("host_workdir") or os.getcwd())
            active_codex = str(self._settings_data.get("host_codex_dir") or os.path.expanduser("~/.codex"))
            try:
                max_agents_running = int(str(self._settings_data.get("max_agents_running", -1)).strip())
            except Exception:
                max_agents_running = -1
            env = Environment(
                env_id="default",
                name="Default",
                color="emerald",
                host_workdir="",
                host_codex_dir=active_codex,
                max_agents_running=max_agents_running,
                preflight_enabled=False,
                preflight_script="",
                gh_management_mode=GH_MANAGEMENT_LOCAL,
                gh_management_target=os.path.expanduser(active_workdir),
                gh_management_locked=True,
                gh_use_host_cli=bool(is_gh_available()),
            )
            save_environment(env)
            envs = load_environments()

        for env in envs.values():
            gh_mode = normalize_gh_management_mode(str(env.gh_management_mode or GH_MANAGEMENT_NONE))
            if gh_mode != GH_MANAGEMENT_NONE:
                continue
            legacy_workdir = os.path.expanduser(str(env.host_workdir or "").strip())
            if legacy_workdir:
                env.gh_management_mode = GH_MANAGEMENT_LOCAL
                env.gh_management_target = legacy_workdir
                env.gh_management_locked = True

        self._environments = dict(envs)
        active_id = self._active_environment_id()
        if active_id not in self._environments:
            if "default" in self._environments:
                self._settings_data["active_environment_id"] = "default"
            else:
                ordered = self._environment_list()
                if ordered:
                    self._settings_data["active_environment_id"] = ordered[0].env_id
        for task in self._tasks.values():
            if not task.environment_id:
                task.environment_id = self._active_environment_id()
        if self._envs_page.isVisible():
            selected = preferred_env_id or self._envs_page.selected_environment_id() or self._active_environment_id()
            self._envs_page.set_environments(self._environments, selected)
        self._apply_active_environment_to_new_task()
        self._refresh_task_rows()
        self._schedule_save()

    def _clean_old_tasks(self) -> None:
        to_remove: set[str] = set()
        for task_id, task in self._tasks.items():
            status = (task.status or "").lower()
            if status in {"done", "failed", "error"} and not task.is_active():
                to_remove.add(task_id)
        if not to_remove:
            return
        self._dashboard.remove_tasks(to_remove)
        for task_id in to_remove:
            self._tasks.pop(task_id, None)
            self._threads.pop(task_id, None)
            self._bridges.pop(task_id, None)
            self._run_started_s.pop(task_id, None)
            self._dashboard_log_refresh_s.pop(task_id, None)
        self._schedule_save()

    def _start_task_from_ui(
        self,
        prompt: str,
        host_codex: str,
        env_id: str,
        base_branch: str,
    ) -> None:
        if shutil.which("docker") is None:
            QMessageBox.critical(self, "Docker not found", "Could not find `docker` in PATH.")
            return
        prompt = sanitize_prompt((prompt or "").strip())

        agent_cli = normalize_agent(str(self._settings_data.get("use") or "codex"))

        task_id = uuid4().hex[:10]
        env_id = str(env_id or "").strip() or self._active_environment_id()
        if env_id not in self._environments:
            QMessageBox.warning(self, "Unknown environment", "Pick an environment first.")
            return
        self._settings_data["active_environment_id"] = env_id
        env = self._environments.get(env_id)

        gh_mode = normalize_gh_management_mode(str(env.gh_management_mode or GH_MANAGEMENT_NONE)) if env else GH_MANAGEMENT_NONE
        effective_workdir, ready, message = self._new_task_workspace(env)
        if not ready:
            QMessageBox.warning(self, "Workspace not configured", message)
            return
        if gh_mode == GH_MANAGEMENT_GITHUB:
            try:
                os.makedirs(effective_workdir, exist_ok=True)
            except Exception:
                pass
        elif not os.path.isdir(effective_workdir):
            QMessageBox.warning(self, "Invalid Workdir", "Host Workdir does not exist.")
            return

        self._settings_data["host_workdir"] = effective_workdir
        host_codex = os.path.expanduser(str(host_codex or "").strip())
        if not host_codex:
            host_codex = self._effective_host_config_dir(agent_cli=agent_cli, env=env)
        if not self._ensure_agent_config_dir(agent_cli, host_codex):
            return
        self._settings_data[self._host_config_dir_key(agent_cli)] = host_codex

        image = PIXELARCH_EMERALD_IMAGE

        agent_cli_args: list[str] = []
        if env and env.agent_cli_args.strip():
            try:
                agent_cli_args = shlex.split(env.agent_cli_args)
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid agent CLI flags", str(exc))
                return

        settings_preflight_script: str | None = None
        if self._settings_data.get("preflight_enabled") and str(self._settings_data.get("preflight_script") or "").strip():
            settings_preflight_script = str(self._settings_data.get("preflight_script") or "")

        environment_preflight_script: str | None = None
        if env and env.preflight_enabled and (env.preflight_script or "").strip():
            environment_preflight_script = env.preflight_script

        task = Task(
            task_id=task_id,
            prompt=prompt,
            image=image,
            host_workdir=effective_workdir,
            host_codex_dir=host_codex,
            environment_id=env_id,
            created_at_s=time.time(),
            status="queued",
            gh_management_mode=gh_mode,
            agent_cli=agent_cli,
            agent_cli_args=" ".join(agent_cli_args),
        )
        self._tasks[task_id] = task
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._schedule_save()

        use_host_gh = bool(getattr(env, "gh_use_host_cli", True)) if env else True
        use_host_gh = bool(use_host_gh and is_gh_available())
        task.gh_use_host_cli = use_host_gh

        if gh_mode == GH_MANAGEMENT_GITHUB and env:
            self._on_task_log(task_id, f"[gh] cloning {env.gh_management_target} -> {effective_workdir}")
            try:
                ensure_github_clone(
                    str(env.gh_management_target or ""),
                    effective_workdir,
                    prefer_gh=use_host_gh,
                    recreate_if_needed=True,
                )
            except GhManagementError as exc:
                task.status = "failed"
                task.error = str(exc)
                task.exit_code = 1
                task.finished_at = datetime.now(tz=timezone.utc)
                self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
                self._details.update_task(task)
                self._schedule_save()
                QMessageBox.warning(self, "Failed to clone repo", str(exc))
                return

        desired_base = str(base_branch or "").strip()
        if gh_mode == GH_MANAGEMENT_GITHUB and is_git_repo(effective_workdir):
            plan = plan_repo_task(effective_workdir, task_id=task_id, base_branch=desired_base or None)
            if plan is not None:
                self._on_task_log(task_id, f"[gh] creating branch {plan.branch} (base {plan.base_branch})")
                try:
                    base_branch, branch = prepare_branch_for_task(
                        plan.repo_root,
                        branch=plan.branch,
                        base_branch=plan.base_branch,
                    )
                except GhManagementError as exc:
                    task.status = "failed"
                    task.error = str(exc)
                    task.exit_code = 1
                    task.finished_at = datetime.now(tz=timezone.utc)
                    self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
                    self._details.update_task(task)
                    self._schedule_save()
                    QMessageBox.warning(self, "Failed to create branch", str(exc))
                    return
                task.gh_repo_root = plan.repo_root
                task.gh_base_branch = base_branch
                task.gh_branch = branch
                self._schedule_save()
        elif gh_mode == GH_MANAGEMENT_GITHUB:
            self._on_task_log(task_id, "[gh] not a git repo; skipping branch/PR")

        runner_prompt = prompt
        if bool(self._settings_data.get("append_pixelarch_context") or False):
            runner_prompt = f"{runner_prompt.rstrip()}{PIXELARCH_AGENT_CONTEXT_SUFFIX}"
        env_vars_for_task = dict(env.env_vars) if env else {}
        extra_mounts_for_task = list(env.extra_mounts) if env else []
        if (
            env
            and gh_mode == GH_MANAGEMENT_GITHUB
            and bool(getattr(env, "gh_pr_metadata_enabled", False))
            and task.gh_repo_root
            and task.gh_branch
        ):
            host_path = pr_metadata_host_path(os.path.dirname(self._state_path), task_id)
            container_path = pr_metadata_container_path(task_id)
            try:
                ensure_pr_metadata_file(host_path, task_id=task_id)
            except Exception as exc:
                self._on_task_log(task_id, f"[gh] failed to prepare PR metadata file: {exc}")
            else:
                task.gh_pr_metadata_path = host_path
                extra_mounts_for_task.append(f"{host_path}:{container_path}:rw")
                env_vars_for_task.setdefault("CODEX_PR_METADATA_PATH", container_path)
                runner_prompt = f"{runner_prompt}{pr_metadata_prompt_instructions(container_path)}"
                self._on_task_log(task_id, f"[gh] PR metadata enabled; mounted -> {container_path}")

        if self._can_start_new_agent_for_env(env_id):
            config = DockerRunnerConfig(
                task_id=task_id,
                image=image,
                host_codex_dir=host_codex,
                host_workdir=effective_workdir,
                agent_cli=agent_cli,
                auto_remove=True,
                pull_before_run=True,
                settings_preflight_script=settings_preflight_script,
                environment_preflight_script=environment_preflight_script,
                env_vars=env_vars_for_task,
                extra_mounts=extra_mounts_for_task,
                agent_cli_args=agent_cli_args,
            )
            task._runner_config = config
            task._runner_prompt = runner_prompt
            self._actually_start_task(task)
        else:
            config = DockerRunnerConfig(
                task_id=task_id,
                image=image,
                host_codex_dir=host_codex,
                host_workdir=effective_workdir,
                agent_cli=agent_cli,
                auto_remove=True,
                pull_before_run=True,
                settings_preflight_script=settings_preflight_script,
                environment_preflight_script=environment_preflight_script,
                env_vars=env_vars_for_task,
                extra_mounts=extra_mounts_for_task,
                agent_cli_args=agent_cli_args,
            )
            task._runner_config = config
            task._runner_prompt = runner_prompt
            self._on_task_log(task_id, "[queue] Waiting for available slot...")
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
            self._schedule_save()

        self._show_dashboard()
        self._new_task.reset_for_new_run()

    def _actually_start_task(self, task: Task) -> None:
        config = getattr(task, "_runner_config", None)
        prompt = getattr(task, "_runner_prompt", None)
        if config is None or prompt is None:
            return

        task.status = "pulling"
        env = self._environments.get(task.environment_id)
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)

        bridge = TaskRunnerBridge(task_id=task.task_id, config=config, prompt=prompt)
        thread = QThread(self)
        bridge.moveToThread(thread)
        thread.started.connect(bridge.run)

        bridge.state.connect(self._on_bridge_state, Qt.QueuedConnection)
        bridge.log.connect(self._on_bridge_log, Qt.QueuedConnection)
        bridge.done.connect(self._on_bridge_done, Qt.QueuedConnection)

        bridge.done.connect(thread.quit, Qt.QueuedConnection)
        bridge.done.connect(bridge.deleteLater, Qt.QueuedConnection)
        thread.finished.connect(thread.deleteLater)

        self._bridges[task.task_id] = bridge
        self._threads[task.task_id] = thread
        self._run_started_s[task.task_id] = time.time()

        thread.start()
        self._schedule_save()

    def _start_interactive_task_from_ui(
        self,
        prompt: str,
        command: str,
        host_codex: str,
        env_id: str,
        terminal_id: str,
        base_branch: str,
        extra_preflight_script: str,
    ) -> None:
        if shutil.which("docker") is None:
            QMessageBox.critical(self, "Docker not found", "Could not find `docker` in PATH.")
            return

        prompt = sanitize_prompt((prompt or "").strip())
        host_codex = os.path.expanduser((host_codex or "").strip())

        options = {opt.terminal_id: opt for opt in detect_terminal_options()}
        opt = options.get(str(terminal_id or "").strip())
        if opt is None:
            QMessageBox.warning(
                self,
                "Terminal not available",
                "The selected terminal could not be found. Click Refresh next to Terminal and pick again.",
            )
            return

        env_id = str(env_id or "").strip() or self._active_environment_id()
        if env_id not in self._environments:
            QMessageBox.warning(self, "Unknown environment", "Pick an environment first.")
            return
        env = self._environments.get(env_id)
        gh_mode = normalize_gh_management_mode(str(env.gh_management_mode or GH_MANAGEMENT_NONE)) if env else GH_MANAGEMENT_NONE
        host_workdir, ready, message = self._new_task_workspace(env)
        if not ready:
            QMessageBox.warning(self, "Workspace not configured", message)
            return

        task_id = uuid4().hex[:10]
        task_token = f"interactive-{task_id}"
        if gh_mode != GH_MANAGEMENT_GITHUB and not os.path.isdir(host_workdir):
            QMessageBox.warning(self, "Invalid Workdir", "Host Workdir does not exist.")
            return

        desired_base = str(base_branch or "").strip()

        agent_cli = normalize_agent(str(self._settings_data.get("use") or "codex"))
        if not host_codex:
            host_codex = self._effective_host_config_dir(agent_cli=agent_cli, env=env)
        if not self._ensure_agent_config_dir(agent_cli, host_codex):
            return

        agent_cli_args: list[str] = []
        if env and env.agent_cli_args.strip():
            try:
                agent_cli_args = shlex.split(env.agent_cli_args)
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid agent CLI flags", str(exc))
                return

        raw_command = str(command or "").strip()
        if not raw_command:
            interactive_key = self._interactive_command_key(agent_cli)
            raw_command = str(self._settings_data.get(interactive_key) or "").strip()
            if not raw_command:
                raw_command = self._default_interactive_command(agent_cli)
        command = raw_command
        is_help_launch = self._is_agent_help_interactive_launch(prompt=prompt, command=command)
        if is_help_launch:
            prompt = "\n".join(
                [
                    f"Agent: {agent_cli}",
                    "",
                    str(prompt or "").strip(),
                ]
            ).strip()
        try:
            if command.startswith("-"):
                cmd_parts = [agent_cli, *shlex.split(command)]
            else:
                cmd_parts = shlex.split(command)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid container command", str(exc))
            return
        if not cmd_parts:
            cmd_parts = ["bash"]

        def _move_positional_to_end(parts: list[str], value: str) -> None:
            value = str(value or "")
            if not value:
                return
            for idx in range(len(parts) - 1, 0, -1):
                if parts[idx] != value:
                    continue
                prev = parts[idx - 1]
                if prev != "--" and prev.startswith("-"):
                    continue
                parts.pop(idx)
                break
            parts.append(value)

        def _move_flag_value_to_end(parts: list[str], flags: set[str]) -> None:
            for idx in range(len(parts) - 2, -1, -1):
                if parts[idx] in flags:
                    flag = parts.pop(idx)
                    value = parts.pop(idx)
                    parts.extend([flag, value])
                    return

        if cmd_parts[0] == "codex":
            if len(cmd_parts) >= 2 and cmd_parts[1] == "exec":
                cmd_parts.pop(1)
            if agent_cli_args:
                cmd_parts.extend(agent_cli_args)
            if prompt:
                _move_positional_to_end(cmd_parts, prompt)
        elif cmd_parts[0] == "claude":
            if agent_cli_args:
                cmd_parts.extend(agent_cli_args)
            if "--add-dir" not in cmd_parts:
                cmd_parts[1:1] = ["--add-dir", "/home/midori-ai/workspace"]
            if prompt:
                _move_positional_to_end(cmd_parts, prompt)
        elif cmd_parts[0] == "copilot":
            if agent_cli_args:
                cmd_parts.extend(agent_cli_args)
            if "--add-dir" not in cmd_parts:
                cmd_parts[1:1] = ["--add-dir", "/home/midori-ai/workspace"]
            if prompt:
                has_interactive = "-i" in cmd_parts or "--interactive" in cmd_parts
                has_prompt = "-p" in cmd_parts or "--prompt" in cmd_parts
                if has_prompt:
                    _move_flag_value_to_end(cmd_parts, {"-p", "--prompt"})
                elif not has_interactive:
                    cmd_parts.extend(["-i", prompt])

        image = PIXELARCH_EMERALD_IMAGE

        settings_preflight_script: str | None = None
        if self._settings_data.get("preflight_enabled") and str(self._settings_data.get("preflight_script") or "").strip():
            settings_preflight_script = str(self._settings_data.get("preflight_script") or "")

        environment_preflight_script: str | None = None
        if env and env.preflight_enabled and (env.preflight_script or "").strip():
            environment_preflight_script = env.preflight_script

        container_name = f"codex-gui-it-{task_id}"
        container_agent_dir = container_config_dir(agent_cli)
        config_extra_mounts = additional_config_mounts(agent_cli, host_codex)
        container_workdir = "/home/midori-ai/workspace"

        task = Task(
            task_id=task_id,
            prompt=prompt,
            image=image,
            host_workdir=host_workdir,
            host_codex_dir=host_codex,
            environment_id=env_id,
            created_at_s=time.time(),
            status="starting",
            container_id=container_name,
            gh_management_mode=gh_mode,
            gh_use_host_cli=bool(getattr(env, "gh_use_host_cli", True)) if env else True,
        )
        self._tasks[task_id] = task
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._schedule_save()

        task.gh_use_host_cli = bool(task.gh_use_host_cli and is_gh_available())
        if gh_mode == GH_MANAGEMENT_GITHUB and env:
            self._on_task_log(task_id, f"[gh] cloning {env.gh_management_target} -> {host_workdir}")
            try:
                os.makedirs(host_workdir, exist_ok=True)
            except Exception:
                pass
            try:
                ensure_github_clone(
                    str(env.gh_management_target or ""),
                    host_workdir,
                    prefer_gh=bool(task.gh_use_host_cli),
                    recreate_if_needed=True,
                )
            except GhManagementError as exc:
                task.status = "failed"
                task.error = str(exc)
                task.exit_code = 1
                task.finished_at = datetime.now(tz=timezone.utc)
                self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
                self._details.update_task(task)
                self._schedule_save()
                QMessageBox.warning(self, "Failed to clone repo", str(exc))
                return

        if gh_mode == GH_MANAGEMENT_GITHUB and is_git_repo(host_workdir):
            plan = plan_repo_task(host_workdir, task_id=task_id, base_branch=desired_base or None)
            if plan is not None:
                self._on_task_log(task_id, f"[gh] creating branch {plan.branch} (base {plan.base_branch})")
                try:
                    base_branch, branch = prepare_branch_for_task(
                        plan.repo_root,
                        branch=plan.branch,
                        base_branch=plan.base_branch,
                    )
                except GhManagementError as exc:
                    task.status = "failed"
                    task.error = str(exc)
                    task.exit_code = 1
                    task.finished_at = datetime.now(tz=timezone.utc)
                    self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
                    self._details.update_task(task)
                    self._schedule_save()
                    QMessageBox.warning(self, "Failed to create branch", str(exc))
                    return
                task.gh_repo_root = plan.repo_root
                task.gh_base_branch = base_branch
                task.gh_branch = branch
                self._schedule_save()
        elif gh_mode == GH_MANAGEMENT_GITHUB and desired_base and is_git_repo(host_workdir):
            proc = subprocess.run(
                ["git", "-C", host_workdir, "checkout", desired_base],
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                msg = (proc.stderr or proc.stdout or "").strip() or f"git checkout {desired_base} failed"
                task.status = "failed"
                task.error = msg
                task.exit_code = 1
                task.finished_at = datetime.now(tz=timezone.utc)
                self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
                self._details.update_task(task)
                self._schedule_save()
                QMessageBox.warning(self, "Failed to checkout base branch", msg)
                return

        settings_tmp_path = ""
        env_tmp_path = ""
        helpme_tmp_path = ""

        preflight_clause = ""
        preflight_mounts: list[str] = []
        settings_container_path = f"/tmp/codex-preflight-settings-{task_token}.sh"
        environment_container_path = f"/tmp/codex-preflight-environment-{task_token}.sh"
        helpme_container_path = f"/tmp/codex-preflight-helpme-{task_token}.sh"

        def _write_preflight_script(script: str, label: str) -> str:
            fd, tmp_path = tempfile.mkstemp(prefix=f"codex-preflight-{label}-{task_token}-", suffix=".sh")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    if not script.endswith("\n"):
                        script += "\n"
                    f.write(script)
            except Exception:
                try:
                    os.close(fd)
                except Exception:
                    pass
                raise
            return tmp_path

        try:
            if (settings_preflight_script or "").strip():
                settings_tmp_path = _write_preflight_script(str(settings_preflight_script or ""), "settings")
                preflight_mounts.extend(["-v", f"{settings_tmp_path}:{settings_container_path}:ro"])
                preflight_clause += (
                    f'PREFLIGHT_SETTINGS={shlex.quote(settings_container_path)}; '
                    'echo "[preflight] settings: running"; '
                    '/bin/bash "${PREFLIGHT_SETTINGS}"; '
                    'echo "[preflight] settings: done"; '
                )

            if (environment_preflight_script or "").strip():
                env_tmp_path = _write_preflight_script(str(environment_preflight_script or ""), "environment")
                preflight_mounts.extend(["-v", f"{env_tmp_path}:{environment_container_path}:ro"])
                preflight_clause += (
                    f'PREFLIGHT_ENV={shlex.quote(environment_container_path)}; '
                    'echo "[preflight] environment: running"; '
                    '/bin/bash "${PREFLIGHT_ENV}"; '
                    'echo "[preflight] environment: done"; '
                )

            if str(extra_preflight_script or "").strip():
                helpme_tmp_path = _write_preflight_script(str(extra_preflight_script or ""), "helpme")
                preflight_mounts.extend(["-v", f"{helpme_tmp_path}:{helpme_container_path}:ro"])
                preflight_clause += (
                    f'PREFLIGHT_HELP={shlex.quote(helpme_container_path)}; '
                    'echo "[preflight] helpme: running"; '
                    '/bin/bash "${PREFLIGHT_HELP}"; '
                    'echo "[preflight] helpme: done"; '
                )
        except Exception as exc:
            for tmp in (settings_tmp_path, env_tmp_path, helpme_tmp_path):
                try:
                    if tmp and os.path.exists(tmp):
                        os.unlink(tmp)
                except Exception:
                    pass
            task.status = "failed"
            task.error = str(exc)
            task.exit_code = 1
            task.finished_at = datetime.now(tz=timezone.utc)
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
            self._details.update_task(task)
            self._schedule_save()
            QMessageBox.warning(self, "Failed to prepare preflight scripts", str(exc))
            return

        try:
            env_args: list[str] = []
            for key, value in sorted((env.env_vars or {}).items() if env else []):
                k = str(key).strip()
                if not k:
                    continue
                env_args.extend(["-e", f"{k}={value}"])

            extra_mount_args: list[str] = []
            for mount in (env.extra_mounts or []) if env else []:
                m = str(mount).strip()
                if not m:
                    continue
                extra_mount_args.extend(["-v", m])
            for mount in config_extra_mounts:
                m = str(mount).strip()
                if not m:
                    continue
                extra_mount_args.extend(["-v", m])

            target_cmd = " ".join(shlex.quote(part) for part in cmd_parts)
            verify_clause = ""
            if cmd_parts[0] in {"codex", "claude", "copilot"}:
                verify_clause = verify_cli_clause(cmd_parts[0])

            container_script = "set -euo pipefail; " f"{preflight_clause}{verify_clause}{target_cmd}"

            forward_gh_token = bool(cmd_parts and cmd_parts[0] == "copilot")
            docker_env_passthrough: list[str] = []
            if forward_gh_token:
                docker_env_passthrough = ["-e", "GH_TOKEN", "-e", "GITHUB_TOKEN"]

            docker_platform_args = docker_platform_args_for_pixelarch()
            docker_args = [
                "docker",
                "run",
                *docker_platform_args,
                "-it",
                "--name",
                container_name,
                "-v",
                f"{host_codex}:{container_agent_dir}",
                "-v",
                f"{host_workdir}:{container_workdir}",
                *extra_mount_args,
                *preflight_mounts,
                *env_args,
                *docker_env_passthrough,
                "-w",
                container_workdir,
                image,
                "/bin/bash",
                "-lc",
                container_script,
            ]
            docker_cmd = " ".join(shlex.quote(part) for part in docker_args)

            finish_dir = os.path.dirname(self._state_path)
            os.makedirs(finish_dir, exist_ok=True)
            finish_path = os.path.join(finish_dir, f"interactive-finish-{task_id}.txt")
            try:
                if os.path.exists(finish_path):
                    os.unlink(finish_path)
            except Exception:
                pass

            gh_token_snippet = ""
            if forward_gh_token:
                gh_token_snippet = (
                    'if [ -z "${GH_TOKEN:-}" ] && [ -z "${GITHUB_TOKEN:-}" ] && command -v gh >/dev/null 2>&1; then '
                    'TOKEN="$(gh auth token -h github.com 2>/dev/null || true)"; '
                    'TOKEN="$(printf "%s" "$TOKEN" | tr -d "\\r\\n")"; '
                    'if [ -n "$TOKEN" ]; then export GH_TOKEN="$TOKEN"; export GITHUB_TOKEN="$TOKEN"; fi; '
                    "fi"
                )

            rosetta_snippet = ""
            if has_rosetta() is False:
                rosetta_snippet = (
                    f'echo "[host] Rosetta 2 not detected; install with: {ROSETTA_INSTALL_COMMAND}"'
                )

            docker_pull_parts = ["docker", "pull", *docker_platform_args, image]
            docker_pull_cmd = " ".join(shlex.quote(part) for part in docker_pull_parts)

            host_script_parts = [
                    f'CONTAINER_NAME={shlex.quote(container_name)}',
                    f'TMP_SETTINGS={shlex.quote(settings_tmp_path)}',
                    f'TMP_ENV={shlex.quote(env_tmp_path)}',
                    f'TMP_HELPME={shlex.quote(helpme_tmp_path)}',
                    f'FINISH_FILE={shlex.quote(finish_path)}',
                    'write_finish() { STATUS="${1:-0}"; printf "%s\\n" "$STATUS" >"$FINISH_FILE" 2>/dev/null || true; }',
                    'cleanup() { docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true; '
                    'if [ -n "$TMP_SETTINGS" ]; then rm -f -- "$TMP_SETTINGS" >/dev/null 2>&1 || true; fi; '
                    'if [ -n "$TMP_ENV" ]; then rm -f -- "$TMP_ENV" >/dev/null 2>&1 || true; fi; '
                    'if [ -n "$TMP_HELPME" ]; then rm -f -- "$TMP_HELPME" >/dev/null 2>&1 || true; fi; }',
                    'finish() { STATUS=$?; if [ ! -e "$FINISH_FILE" ]; then write_finish "$STATUS"; fi; cleanup; }',
                    "trap finish EXIT",
                ]
            if gh_token_snippet:
                host_script_parts.append(gh_token_snippet)
            if rosetta_snippet:
                host_script_parts.append(rosetta_snippet)
            host_script_parts.extend(
                [
                    f"{docker_pull_cmd} || {{ STATUS=$?; echo \"[host] docker pull failed (exit $STATUS)\"; write_finish \"$STATUS\"; read -r -p \"Press Enter to close...\"; exit $STATUS; }}",
                    f"{docker_cmd}; STATUS=$?; if [ $STATUS -ne 0 ]; then echo \"[host] container command failed (exit $STATUS)\"; fi; write_finish \"$STATUS\"; if [ $STATUS -ne 0 ]; then read -r -p \"Press Enter to close...\"; fi; exit $STATUS",
                ]
            )
            host_script = " ; ".join(host_script_parts)

            self._settings_data["host_workdir"] = host_workdir
            self._settings_data[self._host_config_dir_key(agent_cli)] = host_codex
            self._settings_data["active_environment_id"] = env_id
            self._settings_data["interactive_terminal_id"] = str(terminal_id or "")
            interactive_key = self._interactive_command_key(agent_cli)
            if not self._is_agent_help_interactive_launch(prompt=prompt, command=command):
                self._settings_data[interactive_key] = self._sanitize_interactive_command_value(interactive_key, command)
            self._apply_active_environment_to_new_task()
            self._schedule_save()

            task.status = "running"
            task.started_at = datetime.now(tz=timezone.utc)
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
            self._details.update_task(task)
            self._schedule_save()
            self._start_interactive_finish_watch(task_id, finish_path)
            self._on_task_log(task_id, f"[interactive] launched in {opt.label}")

            launch_in_terminal(opt, host_script, cwd=host_workdir)
            self._show_dashboard()
            self._new_task.reset_for_new_run()
        except Exception as exc:
            for tmp in (settings_tmp_path, env_tmp_path, helpme_tmp_path):
                try:
                    if tmp and os.path.exists(tmp):
                        os.unlink(tmp)
                except Exception:
                    pass
            task.status = "failed"
            task.error = str(exc)
            task.exit_code = 1
            task.finished_at = datetime.now(tz=timezone.utc)
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
            self._details.update_task(task)
            self._schedule_save()
            QMessageBox.warning(self, "Failed to launch terminal", str(exc))

    def _start_interactive_finish_watch(self, task_id: str, finish_path: str) -> None:
        task_id = str(task_id or "").strip()
        finish_path = os.path.abspath(os.path.expanduser(str(finish_path or "").strip()))
        if not task_id or not finish_path:
            return

        existing = self._interactive_watch.get(task_id)
        if existing is not None:
            _, stop = existing
            stop.set()

        stop_event = threading.Event()
        self._interactive_watch[task_id] = (finish_path, stop_event)

        def _worker() -> None:
            while not stop_event.is_set():
                if os.path.exists(finish_path):
                    break
                time.sleep(0.35)
            if stop_event.is_set():
                return
            exit_code = 0
            for _ in range(6):
                try:
                    with open(finish_path, "r", encoding="utf-8") as f:
                        raw = (f.read() or "").strip().splitlines()[0] if f else ""
                    exit_code = int(raw or "0")
                    break
                except Exception:
                    time.sleep(0.2)
            self.interactive_finished.emit(task_id, int(exit_code))

        threading.Thread(target=_worker, daemon=True).start()

    @Slot(str, int)
    def _on_interactive_finished(self, task_id: str, exit_code: int) -> None:
        task_id = str(task_id or "").strip()
        watch = self._interactive_watch.pop(task_id, None)
        if watch is not None:
            _, stop = watch
            stop.set()

        task = self._tasks.get(task_id)
        if task is None:
            return

        try:
            task.exit_code = int(exit_code)
        except Exception:
            task.exit_code = 1
        task.finished_at = datetime.now(tz=timezone.utc)
        task.status = "done" if (task.exit_code or 0) == 0 else "failed"

        env = self._environments.get(task.environment_id)
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._details.update_task(task)
        self._schedule_save()
        QApplication.beep()
        self._on_task_log(task_id, f"[interactive] exited with {task.exit_code}")

        if (
            normalize_gh_management_mode(task.gh_management_mode) == GH_MANAGEMENT_GITHUB
            and task.gh_repo_root
            and task.gh_branch
            and not task.gh_pr_url
        ):
            base = task.gh_base_branch or "main"
            message = f"Interactive run finished.\n\nCreate a PR from {task.gh_branch} -> {base}?"
            if QMessageBox.question(self, "Create pull request?", message) == QMessageBox.StandardButton.Yes:
                threading.Thread(
                    target=self._finalize_gh_management_worker,
                    args=(
                        task_id,
                        str(task.gh_repo_root or "").strip(),
                        str(task.gh_branch or "").strip(),
                        str(base).strip(),
                        str(task.prompt or ""),
                        str(task.task_id or task_id),
                        bool(task.gh_use_host_cli),
                        None,
                        str(task.agent_cli or "").strip(),
                        str(task.agent_cli_args or "").strip(),
                    ),
                    daemon=True,
                ).start()

    def _start_preflight_task(
        self,
        *,
        label: str,
        env: Environment,
        agent_cli: str | None,
        host_workdir: str,
        host_codex: str,
        settings_preflight_script: str | None,
        environment_preflight_script: str | None,
    ) -> None:
        if shutil.which("docker") is None:
            QMessageBox.critical(self, "Docker not found", "Could not find `docker` in PATH.")
            return

        if not os.path.isdir(host_workdir):
            QMessageBox.warning(self, "Invalid Workdir", "Host Workdir does not exist.")
            return

        if not (settings_preflight_script or "").strip() and not (environment_preflight_script or "").strip():
            QMessageBox.information(self, "Nothing to test", "No preflight scripts are enabled.")
            return

        agent_cli = normalize_agent(str(agent_cli or self._settings_data.get("use") or "codex"))
        host_codex = os.path.expanduser(str(host_codex or "").strip())
        if not host_codex:
            host_codex = self._effective_host_config_dir(agent_cli=agent_cli, env=env)
        if not self._ensure_agent_config_dir(agent_cli, host_codex):
            return

        task_id = uuid4().hex[:10]
        image = PIXELARCH_EMERALD_IMAGE

        task = Task(
            task_id=task_id,
            prompt=label,
            image=image,
            host_workdir=host_workdir,
            host_codex_dir=host_codex,
            environment_id=env.env_id,
            created_at_s=time.time(),
            status="pulling",
        )
        self._tasks[task_id] = task
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._schedule_save()

        config = DockerRunnerConfig(
            task_id=task_id,
            image=image,
            host_codex_dir=host_codex,
            host_workdir=host_workdir,
            agent_cli=agent_cli,
            auto_remove=True,
            pull_before_run=True,
            settings_preflight_script=settings_preflight_script,
            environment_preflight_script=environment_preflight_script,
            env_vars=dict(env.env_vars) if env else {},
            extra_mounts=list(env.extra_mounts) if env else [],
            agent_cli_args=[],
        )
        bridge = TaskRunnerBridge(task_id=task_id, config=config, mode="preflight")
        thread = QThread(self)
        bridge.moveToThread(thread)
        thread.started.connect(bridge.run)

        bridge.state.connect(self._on_bridge_state, Qt.QueuedConnection)
        bridge.log.connect(self._on_bridge_log, Qt.QueuedConnection)
        bridge.done.connect(self._on_bridge_done, Qt.QueuedConnection)

        bridge.done.connect(thread.quit, Qt.QueuedConnection)
        bridge.done.connect(bridge.deleteLater, Qt.QueuedConnection)
        thread.finished.connect(thread.deleteLater)

        self._bridges[task_id] = bridge
        self._threads[task_id] = thread
        self._run_started_s[task_id] = time.time()

        thread.start()
        self._show_dashboard()
        self._schedule_save()

    def _on_settings_test_preflight(self, settings: dict) -> None:
        settings_enabled = bool(settings.get("preflight_enabled") or False)
        settings_script: str | None = None
        if settings_enabled:
            candidate = str(settings.get("preflight_script") or "")
            if candidate.strip():
                settings_script = candidate

        host_workdir_base = str(self._settings_data.get("host_workdir") or os.getcwd())
        agent_cli = normalize_agent(str(settings.get("use") or self._settings_data.get("use") or "codex"))
        host_codex_base = self._effective_host_config_dir(agent_cli=agent_cli, env=None, settings=settings)

        if settings_script is None:
            has_env_preflights = any(
                e.preflight_enabled and (e.preflight_script or "").strip() for e in self._environment_list()
            )
            if not has_env_preflights:
                if not settings_enabled:
                    return
                QMessageBox.information(self, "Nothing to test", "No preflight scripts are enabled.")
                return

        skipped: list[str] = []
        started = 0
        for env in self._environment_list():
            env_script: str | None = None
            candidate = str(env.preflight_script or "")
            if env.preflight_enabled and candidate.strip():
                env_script = candidate

            if settings_script is None and env_script is None:
                continue

            host_workdir = self._environment_effective_workdir(env, fallback=host_workdir_base)
            host_codex = env.host_codex_dir or host_codex_base
            if not os.path.isdir(host_workdir):
                skipped.append(f"{env.name or env.env_id} ({host_workdir})")
                continue
            self._start_preflight_task(
                label=f"Preflight test (all): {env.name or env.env_id}",
                env=env,
                agent_cli=agent_cli,
                host_workdir=host_workdir,
                host_codex=host_codex,
                settings_preflight_script=settings_script,
                environment_preflight_script=env_script,
            )
            started += 1

        if started == 0 and not skipped:
            if not settings_enabled:
                return
            QMessageBox.information(self, "Nothing to test", "No preflight scripts are enabled.")
            return

        if skipped:
            QMessageBox.warning(
                self,
                "Skipped environments",
                "Skipped environments with missing Workdir:\n" + "\n".join(skipped[:20]),
            )

    def _on_environment_test_preflight(self, env: object) -> None:
        if not isinstance(env, Environment):
            return

        settings_preflight_script: str | None = None
        if self._settings_data.get("preflight_enabled") and str(self._settings_data.get("preflight_script") or "").strip():
            settings_preflight_script = str(self._settings_data.get("preflight_script") or "")

        environment_preflight_script: str | None = None
        if env.preflight_enabled and (env.preflight_script or "").strip():
            environment_preflight_script = env.preflight_script

        host_workdir_base = str(self._settings_data.get("host_workdir") or os.getcwd())
        agent_cli = normalize_agent(str(self._settings_data.get("use") or "codex"))
        host_codex_base = self._effective_host_config_dir(agent_cli=agent_cli, env=None)
        host_workdir = self._environment_effective_workdir(env, fallback=host_workdir_base)
        host_codex = env.host_codex_dir or host_codex_base

        self._start_preflight_task(
            label=f"Preflight test: {env.name or env.env_id}",
            env=env,
            agent_cli=agent_cli,
            host_workdir=host_workdir,
            host_codex=host_codex,
            settings_preflight_script=settings_preflight_script,
            environment_preflight_script=environment_preflight_script,
        )

    def _open_task_details(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if not task:
            return
        self._details.show_task(task)
        self._show_task_details()

    def _discard_task_from_ui(self, task_id: str) -> None:
        task_id = str(task_id or "").strip()
        task = self._tasks.get(task_id)
        if task is None:
            return

        prompt = task.prompt_one_line()
        message = (
            f"Discard task {task_id}?\n\n"
            f"{prompt}\n\n"
            "This removes it from the list and will attempt to stop/remove any running container."
        )
        if QMessageBox.question(self, "Discard task?", message) != QMessageBox.StandardButton.Yes:
            return

        bridge = self._bridges.get(task_id)
        thread = self._threads.get(task_id)
        container_id = task.container_id or (bridge.container_id if bridge is not None else None)
        watch = self._interactive_watch.get(task_id)
        if watch is not None:
            _, stop = watch
            stop.set()

        if bridge is not None:
            try:
                QMetaObject.invokeMethod(bridge, "request_stop", Qt.QueuedConnection)
            except Exception:
                pass
        if thread is not None:
            try:
                thread.quit()
            except Exception:
                pass

        self._dashboard.remove_tasks({task_id})
        self._tasks.pop(task_id, None)
        self._threads.pop(task_id, None)
        self._bridges.pop(task_id, None)
        self._run_started_s.pop(task_id, None)
        self._dashboard_log_refresh_s.pop(task_id, None)
        self._interactive_watch.pop(task_id, None)
        self._schedule_save()

        if self._details.isVisible() and self._details.current_task_id() == task_id:
            self._show_dashboard()

        if container_id:
            threading.Thread(
                target=self._force_remove_container,
                args=(container_id,),
                daemon=True,
            ).start()

    @staticmethod
    def _force_remove_container(container_id: str) -> None:
        container_id = str(container_id or "").strip()
        if not container_id:
            return
        try:
            subprocess.run(
                ["docker", "rm", "-f", container_id],
                check=False,
                capture_output=True,
                text=True,
                timeout=25.0,
            )
        except Exception:
            pass

    def _on_bridge_state(self, state: dict) -> None:
        bridge = self.sender()
        if isinstance(bridge, TaskRunnerBridge):
            self._on_task_state(bridge.task_id, state)

    def _on_bridge_log(self, line: str) -> None:
        bridge = self.sender()
        if isinstance(bridge, TaskRunnerBridge):
            self._on_task_log(bridge.task_id, line)

    def _on_bridge_done(self, exit_code: int, error: object) -> None:
        bridge = self.sender()
        if isinstance(bridge, TaskRunnerBridge):
            self._on_task_done(bridge.task_id, exit_code, error)

    @Slot(str, str)
    def _on_host_log(self, task_id: str, line: str) -> None:
        self._on_task_log(task_id, line)

    @Slot(str, str)
    def _on_host_pr_url(self, task_id: str, pr_url: str) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        task.gh_pr_url = str(pr_url or "").strip()
        env = self._environments.get(task.environment_id)
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._details.update_task(task)
        self._schedule_save()

    def _on_task_log(self, task_id: str, line: str) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        cleaned = prettify_log_line(line)
        task.logs.append(cleaned)
        if len(task.logs) > 6000:
            task.logs = task.logs[-5000:]
        self._details.append_log(task_id, cleaned)
        self._schedule_save()
        if cleaned and self._dashboard.isVisible() and task.is_active():
            now_s = time.time()
            last_s = float(self._dashboard_log_refresh_s.get(task_id) or 0.0)
            if now_s - last_s >= 0.25:
                self._dashboard_log_refresh_s[task_id] = now_s
                env = self._environments.get(task.environment_id)
                stain = env.color if env else None
                spinner = _stain_color(env.color) if env else None
                self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        if "docker pull" in cleaned and (task.status or "").lower() != "pulling":
            task.status = "pulling"
            env = self._environments.get(task.environment_id)
            stain = env.color if env else None
            spinner = _stain_color(env.color) if env else None
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
            self._schedule_save()

    def _on_task_state(self, task_id: str, state: dict) -> None:
        task = self._tasks.get(task_id)
        bridge = self._bridges.get(task_id)
        if task is None:
            return

        current = (task.status or "").lower()
        incoming = str(state.get("Status") or task.status or "—").lower()
        if current not in {"done", "failed"}:
            task.status = incoming
        if bridge and bridge.container_id:
            task.container_id = bridge.container_id

        started_at = _parse_docker_time(state.get("StartedAt"))
        finished_at = _parse_docker_time(state.get("FinishedAt"))
        if started_at:
            task.started_at = started_at
        if finished_at:
            task.finished_at = finished_at

        exit_code = state.get("ExitCode")
        if exit_code is not None:
            try:
                task.exit_code = int(exit_code)
            except Exception:
                pass

        env = self._environments.get(task.environment_id)
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._details.update_task(task)
        self._schedule_save()

    def _on_task_done(self, task_id: str, exit_code: int, error: object) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return

        if task.started_at is None:
            started_s = self._run_started_s.get(task_id)
            if started_s is not None:
                task.started_at = datetime.fromtimestamp(started_s, tz=timezone.utc)
        if task.finished_at is None:
            task.finished_at = datetime.now(tz=timezone.utc)

        if error:
            task.status = "failed"
            task.error = str(error)
        else:
            task.exit_code = int(exit_code)
            task.status = "done" if int(exit_code) == 0 else "failed"

        env = self._environments.get(task.environment_id)
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._details.update_task(task)
        self._schedule_save()
        QApplication.beep()

        self._try_start_queued_tasks()

        if (
            normalize_gh_management_mode(task.gh_management_mode) != GH_MANAGEMENT_NONE
            and task.gh_repo_root
            and task.gh_branch
        ):
            repo_root = str(task.gh_repo_root or "").strip()
            branch = str(task.gh_branch or "").strip()
            base_branch = str(task.gh_base_branch or "").strip() or "main"
            prompt_text = str(task.prompt or "")
            task_token = str(task.task_id or task_id)
            pr_metadata_path = str(task.gh_pr_metadata_path or "").strip() or None
            threading.Thread(
                target=self._finalize_gh_management_worker,
                args=(
                    task_id,
                    repo_root,
                    branch,
                    base_branch,
                    prompt_text,
                    task_token,
                    bool(task.gh_use_host_cli),
                    pr_metadata_path,
                    str(task.agent_cli or "").strip(),
                    str(task.agent_cli_args or "").strip(),
                ),
                daemon=True,
            ).start()

    def _finalize_gh_management_worker(
        self,
        task_id: str,
        repo_root: str,
        branch: str,
        base_branch: str,
        prompt_text: str,
        task_token: str,
        use_gh: bool,
        pr_metadata_path: str | None = None,
        agent_cli: str = "",
        agent_cli_args: str = "",
    ) -> None:
        if not repo_root or not branch:
            return

        prompt_line = (prompt_text or "").strip().splitlines()[0] if prompt_text else ""
        default_title = f"codex: {prompt_line or task_id}"
        default_title = normalize_pr_title(default_title, fallback=default_title)
        default_body = (
            f"Automated by {APP_TITLE}.\n\n"
            f"Task: {task_token}\n\n"
            "Prompt:\n"
            f"{(prompt_text or '').strip()}\n"
        )
        metadata = load_pr_metadata(pr_metadata_path or "") if pr_metadata_path else None
        if metadata is not None and (metadata.title or metadata.body):
            self.host_log.emit(task_id, f"[gh] using PR metadata from {pr_metadata_path}")
        title = (
            normalize_pr_title(str(metadata.title or ""), fallback=default_title)
            if metadata is not None
            else default_title
        )
        body = str(metadata.body or "").strip() if metadata is not None else ""
        if not body:
            body = default_body

        self.host_log.emit(task_id, f"[gh] preparing PR from {branch} -> {base_branch}")
        try:
            pr_url = commit_push_and_pr(
                repo_root,
                branch=branch,
                base_branch=base_branch,
                title=title,
                body=body,
                use_gh=bool(use_gh),
                agent_cli=agent_cli,
                agent_cli_args=agent_cli_args,
            )
        except GhManagementError as exc:
            self.host_log.emit(task_id, f"[gh] failed: {exc}")
            return
        except Exception as exc:
            self.host_log.emit(task_id, f"[gh] failed: {exc}")
            return

        if pr_url is None:
            self.host_log.emit(task_id, "[gh] no changes to commit; skipping PR")
            return
        if pr_url == "":
            self.host_log.emit(task_id, "[gh] pushed branch; PR creation skipped (gh disabled or missing)")
            return
        self.host_pr_url.emit(task_id, pr_url)
        self.host_log.emit(task_id, f"[gh] PR: {pr_url}")

    def closeEvent(self, event) -> None:
        try:
            self._save_state()
        except Exception:
            pass
        super().closeEvent(event)

    def _schedule_save(self) -> None:
        self._save_timer.start()

    def _save_state(self) -> None:
        tasks = sorted(self._tasks.values(), key=lambda t: t.created_at_s)
        environments = [serialize_environment(env) for env in self._environment_list()]
        payload = {"tasks": [serialize_task(t) for t in tasks], "settings": dict(self._settings_data), "environments": environments}
        save_state(self._state_path, payload)

    def _load_state(self) -> None:
        try:
            payload = load_state(self._state_path)
        except Exception:
            return
        settings = payload.get("settings")
        if isinstance(settings, dict):
            self._settings_data.update(settings)
        self._settings_data["use"] = normalize_agent(str(self._settings_data.get("use") or "codex"))
        try:
            self._settings_data["max_agents_running"] = int(str(self._settings_data.get("max_agents_running", -1)).strip())
        except Exception:
            self._settings_data["max_agents_running"] = -1
        self._settings_data.setdefault("host_claude_dir", "")
        self._settings_data.setdefault("host_copilot_dir", "")
        self._settings_data.setdefault("interactive_command_claude", "--add-dir /home/midori-ai/workspace")
        self._settings_data.setdefault("interactive_command_copilot", "--add-dir /home/midori-ai/workspace")
        host_codex_dir = os.path.normpath(os.path.expanduser(str(self._settings_data.get("host_codex_dir") or "").strip()))
        if host_codex_dir == os.path.expanduser("~/.midoriai"):
            self._settings_data["host_codex_dir"] = os.path.expanduser("~/.codex")
        for key in ("interactive_command", "interactive_command_claude", "interactive_command_copilot"):
            raw = str(self._settings_data.get(key) or "").strip()
            if not raw:
                continue
            self._settings_data[key] = self._sanitize_interactive_command_value(key, raw)
        items = payload.get("tasks") or []
        loaded: list[Task] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            task = deserialize_task(Task, item)
            if not task.task_id:
                continue
            if task.logs:
                task.logs = [prettify_log_line(line) for line in task.logs if isinstance(line, str)]
            loaded.append(task)
        loaded.sort(key=lambda t: t.created_at_s)
        for task in loaded:
            active = (task.status or "").lower() in {"queued", "pulling", "created", "running", "starting"}
            if active:
                task.status = "unknown"
            self._tasks[task.task_id] = task
            env = self._environments.get(task.environment_id)
            stain = env.color if env else None
            spinner = _stain_color(env.color) if env else None
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)


def run_app(argv: list[str]) -> None:
    app = QApplication(argv)
    app.setApplicationDisplayName(APP_TITLE)
    app.setApplicationName(APP_TITLE)
    icon = _app_icon()
    if icon is not None:
        app.setWindowIcon(icon)
    app.setStyleSheet(app_stylesheet())

    window = MainWindow()
    if icon is not None:
        window.setWindowIcon(icon)
    window.show()
    sys.exit(app.exec())
