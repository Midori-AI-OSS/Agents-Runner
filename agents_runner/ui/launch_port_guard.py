from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QWidget

from agents_runner.port_launch_guard import PortConflict
from agents_runner.port_launch_guard import PortRemap
from agents_runner.port_launch_guard import apply_port_remaps
from agents_runner.port_launch_guard import build_random_host_remaps
from agents_runner.port_launch_guard import detect_port_conflicts
from agents_runner.port_launch_guard import normalize_port_specs


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

    ports_for_task = list(normalized)
    accepted_remaps: list[PortRemap] = []
    for conflict in conflicts:
        remaps = build_random_host_remaps(ports_for_task, [conflict])
        if not remaps:
            continue
        remap = remaps[0]
        reply = QMessageBox.question(
            parent,
            "Host port conflict",
            (
                f"`{remap.original_publish}` is already in use.\n\n"
                "Use random free host ports for this conflict?"
            ),
        )
        if reply != QMessageBox.StandardButton.Yes:
            return LaunchPortDecision(
                outcome="conflict_cancel",
                ports_for_task=normalized,
                conflicts=conflicts,
                remaps=accepted_remaps,
            )
        ports_for_task = apply_port_remaps(ports_for_task, [remap])
        accepted_remaps.append(remap)

    return LaunchPortDecision(
        outcome="conflict_remap",
        ports_for_task=ports_for_task,
        conflicts=conflicts,
        remaps=accepted_remaps,
    )
