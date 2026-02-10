TEMPLATE_BASE = """
    QWidget {
        color: __STYLE_TEXT_PRIMARY__;
        font-family: __STYLE_FONT_FAMILY__;
        font-size: __STYLE_FONT_SIZE__;
    }

    QMainWindow {
        background: transparent;
    }

    QLineEdit, QPlainTextEdit {
        background-color: rgba(18, 20, 28, 190);
        border: 1px solid rgba(255, 255, 255, 22);
        border-radius: 0px;
        padding: 10px;
        selection-background-color: __STYLE_SELECTION_BG__;
    }

    QLineEdit::placeholder, QPlainTextEdit::placeholder {
        color: __STYLE_TEXT_PLACEHOLDER__;
    }

    QLineEdit:hover, QPlainTextEdit:hover {
        border: 1px solid rgba(56, 189, 248, 50);
        background-color: rgba(18, 20, 28, 205);
    }

    QLineEdit:focus, QPlainTextEdit:focus {
        border: 1px solid rgba(56, 189, 248, 120);
        background-color: rgba(18, 20, 28, 225);
    }

    QComboBox {
        background-color: rgba(18, 20, 28, 190);
        border: 1px solid rgba(255, 255, 255, 22);
        border-radius: 0px;
        padding: 9px 34px 9px 10px;
        selection-background-color: __STYLE_SELECTION_BG__;
    }

    QComboBox:hover {
        border: 1px solid rgba(56, 189, 248, 60);
        background-color: rgba(18, 20, 28, 210);
    }

    QComboBox:focus {
        border: 1px solid rgba(56, 189, 248, 120);
        background-color: rgba(18, 20, 28, 225);
    }

    QComboBox:disabled {
        background-color: rgba(18, 20, 28, 90);
        color: rgba(237, 239, 245, 130);
        border: 1px solid rgba(255, 255, 255, 14);
    }

    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 28px;
        border-left: 1px solid rgba(255, 255, 255, 14);
        background-color: rgba(18, 20, 28, 120);
        border-top-right-radius: 0px;
        border-bottom-right-radius: 0px;
    }

    QComboBox::drop-down:hover {
        background-color: rgba(56, 189, 248, 30);
    }

    QComboBox QAbstractItemView {
        background-color: rgba(18, 20, 28, 240);
        border: 1px solid rgba(255, 255, 255, 22);
        outline: 0px;
        selection-background-color: rgba(56, 189, 248, 85);
    }

    QComboBox QAbstractItemView::item {
        padding: 8px 10px;
    }

    QTableWidget {
        background-color: rgba(18, 20, 28, 120);
        border: 1px solid rgba(255, 255, 255, 14);
        border-radius: 0px;
        gridline-color: rgba(255, 255, 255, 10);
        selection-background-color: rgba(56, 189, 248, 85);
        outline: 0px;
    }

    QTableWidget::item {
        padding: 6px 8px;
        border-radius: 0px;
    }

    QHeaderView::section {
        background-color: rgba(18, 20, 28, 190);
        border: 1px solid rgba(255, 255, 255, 14);
        padding: 8px 10px;
        font-weight: 650;
        border-radius: 0px;
    }

    QTableCornerButton::section {
        background-color: rgba(18, 20, 28, 190);
        border: 1px solid rgba(255, 255, 255, 14);
        border-radius: 0px;
    }

    QPlainTextEdit {
        border-radius: 0px;
    }

    QPushButton {
        color: rgba(237, 239, 245, 235);
        background-color: rgba(18, 20, 28, 135);
        border: 1px solid rgba(255, 255, 255, 22);
        border-radius: 0px;
        padding: 9px 12px;
        font-weight: 600;
    }

    QPushButton:hover {
        background-color: rgba(56, 189, 248, 30);
        border: 1px solid rgba(56, 189, 248, 80);
    }

    QPushButton:pressed {
        background-color: rgba(56, 189, 248, 70);
        border: 1px solid rgba(56, 189, 248, 100);
    }

    QPushButton:focus {
        border: 1px solid rgba(56, 189, 248, 105);
    }

    QPushButton:disabled {
        background-color: rgba(18, 20, 28, 90);
        color: rgba(237, 239, 245, 130);
        border: 1px solid rgba(255, 255, 255, 14);
    }

    QToolButton {
        color: rgba(237, 239, 245, 235);
        background-color: rgba(18, 20, 28, 135);
        border: 1px solid rgba(255, 255, 255, 22);
        border-radius: 0px;
        padding: 9px 12px;
        font-weight: 600;
    }

    QToolButton:hover {
        background-color: rgba(56, 189, 248, 30);
        border: 1px solid rgba(56, 189, 248, 80);
    }

    QToolButton:pressed {
        background-color: rgba(56, 189, 248, 70);
        border: 1px solid rgba(56, 189, 248, 100);
    }

    QToolButton:focus {
        border: 1px solid rgba(56, 189, 248, 105);
    }

    QToolButton:disabled {
        background-color: rgba(18, 20, 28, 90);
        color: rgba(237, 239, 245, 130);
        border: 1px solid rgba(255, 255, 255, 14);
    }

    QToolButton[autoRaise="true"] {
        background-color: rgba(0, 0, 0, 0);
        border: 1px solid rgba(0, 0, 0, 0);
        border-radius: 0px;
        padding: 6px;
    }

    QToolButton[autoRaise="true"]:hover {
        background-color: rgba(255, 255, 255, 10);
        border: 1px solid rgba(255, 255, 255, 18);
    }

    QToolButton[autoRaise="true"]:pressed {
        background-color: rgba(56, 189, 248, 60);
        border: 1px solid rgba(56, 189, 248, 90);
    }

    QToolButton[autoRaise="true"]:focus {
        border: 1px solid rgba(56, 189, 248, 105);
    }

    QToolButton#RowTrash {
        background-color: rgba(0, 0, 0, 0);
        border: 1px solid rgba(255, 255, 255, 14);
        border-radius: 0px;
        padding: 6px;
        font-weight: 600;
    }

    QToolButton#RowTrash:hover {
        background-color: rgba(255, 255, 255, 12);
        border: 1px solid rgba(255, 255, 255, 26);
    }

    QToolButton#RowTrash:pressed {
        background-color: rgba(56, 189, 248, 60);
        border: 1px solid rgba(56, 189, 248, 90);
    }

    QWidget#RadioControlRoot {
        background: transparent;
    }

    QToolButton#RadioControlButton {
        min-width: 40px;
        max-width: 40px;
        min-height: 40px;
        max-height: 40px;
        padding: 0px;
    }

    QWidget#RadioControlSliderWrap {
        background: transparent;
        border: 0px;
    }

    QSlider#RadioControlVolumeSlider::groove:horizontal {
        height: 6px;
        border: 1px solid rgba(255, 255, 255, 20);
        background: rgba(18, 20, 28, 140);
        border-radius: 0px;
    }

    QSlider#RadioControlVolumeSlider::sub-page:horizontal {
        background: rgba(56, 189, 248, 90);
        border-radius: 0px;
    }

    QSlider#RadioControlVolumeSlider::handle:horizontal {
        width: 10px;
        margin: -4px 0px;
        border: 1px solid rgba(56, 189, 248, 120);
        background: rgba(237, 239, 245, 240);
        border-radius: 0px;
    }

    QSlider#RadioControlVolumeSlider::handle:horizontal:hover {
        border: 1px solid rgba(56, 189, 248, 170);
    }

    QWidget#SettingsNavPanel {
        background-color: rgba(18, 20, 28, 95);
        border: 1px solid rgba(255, 255, 255, 14);
        border-radius: 0px;
    }

    QLabel#SettingsNavSection {
        color: rgba(237, 239, 245, 145);
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.6px;
        margin-top: 8px;
        margin-bottom: 2px;
        padding: 2px 6px;
    }

    QToolButton#SettingsNavButton {
        text-align: left;
        padding: 9px 10px;
        border: 1px solid rgba(255, 255, 255, 14);
        background-color: rgba(18, 20, 28, 95);
        color: rgba(237, 239, 245, 220);
        border-radius: 0px;
        font-weight: 620;
    }

    QToolButton#SettingsNavButton:hover {
        border: 1px solid rgba(56, 189, 248, 70);
        background-color: rgba(56, 189, 248, 20);
    }

    QToolButton#SettingsNavButton:checked {
        border: 1px solid rgba(56, 189, 248, 110);
        background-color: rgba(56, 189, 248, 62);
    }

    QToolButton#SettingsNavButton:checked:hover {
        border: 1px solid rgba(56, 189, 248, 130);
        background-color: rgba(56, 189, 248, 76);
    }

    QLabel#SettingsPaneTitle {
        font-size: 16px;
        font-weight: 760;
        color: rgba(237, 239, 245, 245);
    }

    QLabel#SettingsPaneSubtitle {
        color: rgba(237, 239, 245, 160);
    }

    QWidget#ThemePreviewGridHost {
        background: transparent;
    }

    QFrame#ThemePreviewTile {
        background-color: rgba(18, 20, 28, 105);
        border: 1px solid rgba(255, 255, 255, 16);
        border-radius: 0px;
        padding: 0px;
    }

    QFrame#ThemePreviewTile:hover {
        border: 1px solid rgba(56, 189, 248, 85);
        background-color: rgba(56, 189, 248, 16);
    }

    QFrame#ThemePreviewTile[selected="true"] {
        border: 1px solid rgba(56, 189, 248, 120);
        background-color: rgba(56, 189, 248, 28);
    }

    QLabel#ThemePreviewTileLabel {
        color: rgba(237, 239, 245, 215);
        font-weight: 620;
        padding: 0px 2px 2px 2px;
    }

    QWidget#ThemePreviewCanvas {
        border: 1px solid rgba(255, 255, 255, 22);
        border-radius: 0px;
        background-color: rgba(10, 11, 13, 255);
    }

    QWidget#ThemePreviewDialogFrame {
        border: 1px solid rgba(255, 255, 255, 16);
        border-radius: 0px;
        background-color: rgba(18, 20, 28, 70);
    }

    QWidget#ThemePreviewDialogCanvas {
        border: 1px solid rgba(255, 255, 255, 20);
        border-radius: 0px;
        background-color: rgba(10, 11, 13, 255);
    }

    QCheckBox {
        spacing: 10px;
    }

    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border-radius: 0px;
        border: 1px solid rgba(255, 255, 255, 35);
        background-color: rgba(18, 20, 28, 170);
    }

    QCheckBox::indicator:hover {
        border: 1px solid rgba(56, 189, 248, 70);
        background-color: rgba(18, 20, 28, 200);
    }

    QCheckBox::indicator:checked {
        background-color: rgba(16, 185, 129, 165);
        border: 1px solid rgba(16, 185, 129, 180);
    }

    QCheckBox::indicator:checked:hover {
        background-color: rgba(16, 185, 129, 195);
        border: 1px solid rgba(16, 185, 129, 220);
    }

    QScrollBar:vertical {
        background: rgba(0, 0, 0, 0);
        width: 10px;
        margin: 4px 2px 4px 2px;
    }
    QScrollBar::handle:vertical {
        background: rgba(255, 255, 255, 35);
        border-radius: 0px;
        min-height: 20px;
    }
    QScrollBar::handle:vertical:hover {
        background: rgba(56, 189, 248, 100);
    }
    QScrollBar::handle:vertical:pressed {
        background: rgba(56, 189, 248, 140);
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
        subcontrol-origin: margin;
    }

    QScrollArea#TaskScroll {
        background: transparent;
        border: none;
    }
    QScrollArea#TaskScroll > QWidget > QWidget {
        background: transparent;
    }

    QTabWidget::pane {
        border: 1px solid rgba(255, 255, 255, 14);
        border-top: 0px;
        background: rgba(18, 20, 28, 55);
        margin-top: 0px;
        border-radius: 0px;
    }

    QFrame#TaskTabPane {
        border: none;
        background: transparent;
        margin-top: 0px;
    }

    QTabBar::base {
        border: none;
        background: transparent;
    }

    QTabBar::tab {
        background-color: rgba(18, 20, 28, 135);
        border: 1px solid rgba(255, 255, 255, 18);
        border-top-left-radius: 0px;
        border-top-right-radius: 0px;
        padding: 8px 12px;
        margin-right: 6px;
        font-weight: 650;
    }

    QTabBar::tab:hover {
        background-color: rgba(56, 189, 248, 25);
        border: 1px solid rgba(56, 189, 248, 60);
    }

    QTabBar::tab:selected {
        background-color: rgba(56, 189, 248, 75);
        border: 1px solid rgba(56, 189, 248, 120);
    }

    QTabBar::tab:selected:hover {
        background-color: rgba(56, 189, 248, 90);
        border: 1px solid rgba(56, 189, 248, 140);
    }
"""
