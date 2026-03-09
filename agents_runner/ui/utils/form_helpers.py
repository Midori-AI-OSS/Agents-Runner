from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

from PySide6.QtWidgets import QHBoxLayout

from agents_runner.ui.constants import BUTTON_ROW_SPACING


def create_stretch_row(
    *widgets: QWidget,
    stretch_index: int = 0,
) -> QWidget:
    """Create a row widget with horizontal layout and stretch spacing.

    Args:
        *widgets: Widgets to add to the row, left to right.
        stretch_index: Index where to insert stretch (0=before first widget,
            1=after first widget, etc.). Use len(widgets) to add stretch at end.

    Returns:
        QWidget container with the horizontal layout applied.

    Example:
        >>> row = create_stretch_row(
        ...     QLabel("Setting:"),
        ...     combo_box,
        ...     stretch_index=1,  # Label left, combo+stretch right
        ... )
    """
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(BUTTON_ROW_SPACING)

    for i, widget in enumerate(widgets):
        if i == stretch_index:
            layout.addStretch(1)
        layout.addWidget(widget)

    # Add stretch at end if stretch_index == len(widgets)
    if stretch_index >= len(widgets):
        layout.addStretch(1)

    return row


def add_grid_row(
    grid: QGridLayout,
    row: int,
    label: QLabel | str,
    *controls: QWidget,
    colspan: int = 2,
) -> None:
    """Add a label-control row to a grid layout.

    Creates a stretch row container for the control widgets to ensure
    proper right-alignment, matching the Envs menu layout pattern.

    Args:
        grid: The grid layout to add the row to.
        row: The row index (0-based).
        label: The label widget or text string for the left column.
        *controls: Control widgets to place in the right column (inside stretch row).
        colspan: Number of columns the controls should span (default 2).

    Example:
        >>> add_grid_row(grid, 0, "Interactive terminal", combo, button)
        >>> add_grid_row(grid, 1, "Theme", theme_combo, colspan=1)
    """
    from PySide6.QtWidgets import QLabel

    label_widget = QLabel(label) if isinstance(label, str) else label
    control_row = create_stretch_row(*controls)

    grid.addWidget(label_widget, row, 0)
    grid.addWidget(control_row, row, 1, 1, colspan)
