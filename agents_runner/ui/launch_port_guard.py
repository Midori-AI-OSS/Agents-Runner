from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from PySide6.QtWidgets import QWidget

from agents_runner.port_launch_guard import PortConflict
from agents_runner.port_launch_guard import PortRemap
from agents_runner.port_launch_guard import apply_port_remaps
from agents_runner.port_launch_guard import build_random_host_remaps
from agents_runner.port_launch_guard import detect_port_conflicts
from agents_runner.port_launch_guard import normalize_port_specs
from agents_runner.ui.dialogs.port_conflict_dialog import PortConflictDialog
from agents_runner.ui.dialogs.port_conflict_dialog import PORT_CONFLICT_CANCEL


LaunchPortDecisionKind = Literal[
    "no_conflict",
    "conflict_cancel",
    "conflict_remap",
]


@dataclass(frozen=True)
class LaunchPortDecision:
    """Launch-time runtime port decision."""

    outcome: LaunchPortDecisionKind
    ports_for_task: list[str]
    conflicts: list[PortConflict]
    remaps: list[PortRemap]


def resolve_launch_port_decision(
    *,
    parent: QWidget,
    port_specs: Sequence[str] | None,
) -> LaunchPortDecision:
    """Resolve launch-time runtime ports with user choice on conflict."""
    normalized = normalize_port_specs(port_specs)
    conflicts = detect_port_conflicts(normalized)
    if not conflicts:
        return LaunchPortDecision(
            outcome="no_conflict",
            ports_for_task=normalized,
            conflicts=[],
            remaps=[],
        )

    remaps = build_random_host_remaps(normalized, conflicts)
    preview_lines = [
        f"{remap.original_publish} -> {remap.remapped_publish}" for remap in remaps
    ]

    dialog = PortConflictDialog(parent, preview_lines=preview_lines)
    dialog.exec()
    if dialog.choice() == PORT_CONFLICT_CANCEL:
        return LaunchPortDecision(
            outcome="conflict_cancel",
            ports_for_task=normalized,
            conflicts=conflicts,
            remaps=remaps,
        )

    return LaunchPortDecision(
        outcome="conflict_remap",
        ports_for_task=apply_port_remaps(normalized, remaps),
        conflicts=conflicts,
        remaps=remaps,
    )
