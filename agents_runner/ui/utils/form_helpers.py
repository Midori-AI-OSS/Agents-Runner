from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QGridLayout, QHBoxLayout, QLabel, QWidget

from agents_runner.ui.constants import (
    BUTTON_ROW_SPACING,
    GRID_HORIZONTAL_SPACING,
    GRID_VERTICAL_SPACING,
)


def configure_form_grid(grid: QGridLayout) -> None:
    """Apply the shared grid configuration used by form pages."""

    grid.setHorizontalSpacing(GRID_HORIZONTAL_SPACING)
    grid.setVerticalSpacing(GRID_VERTICAL_SPACING)
    grid.setContentsMargins(0, 0, 0, 0)


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

    Single checkbox controls are wrapped in a stretch row to keep the
    checkbox compact and left-aligned. Other single controls are placed
    directly in the grid cell. Multi-control rows are wrapped in a stretch
    row so controls remain left-aligned with trailing space on the right.

    Args:
        grid: The grid layout to add the row to.
        row: The row index (0-based).
        label: The label widget or text string for the left column.
        *controls: Control widgets to place in the right column.
        colspan: Number of columns the controls should span (default 2).

    Example:
        >>> add_grid_row(grid, 0, "Interactive terminal", combo, button)
        >>> add_grid_row(grid, 1, "Theme", theme_combo, colspan=1)
    """
    label_widget = QLabel(label) if isinstance(label, str) else label
    if not controls:
        msg = "add_grid_row requires at least one control widget"
        raise ValueError(msg)

    if len(controls) == 1:
        single_control = controls[0]
        control_widget = (
            create_stretch_row(single_control, stretch_index=1)
            if isinstance(single_control, QCheckBox)
            else single_control
        )
    else:
        control_widget = create_stretch_row(*controls, stretch_index=len(controls))

    grid.addWidget(label_widget, row, 0)
    grid.addWidget(control_widget, row, 1, 1, colspan)
