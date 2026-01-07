TEMPLATE_TASKS = """    QWidget#TaskList {
        background-color: transparent;
        border: none;
    }

    QWidget#TaskRow {
        border: 1px solid rgba(255, 255, 255, 12);
        border-left: 4px solid rgba(148, 163, 184, 110);
        border-radius: 0px;
        background-color: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(148, 163, 184, 20),
            stop: 1 rgba(18, 20, 28, 55)
        );
    }

    QWidget#TaskRow[stain="slate"] {
        border-left-color: rgba(148, 163, 184, 110);
        background-color: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(148, 163, 184, 20),
            stop: 1 rgba(18, 20, 28, 55)
        );
    }
    QWidget#TaskRow[stain="cyan"] {
        border-left-color: rgba(56, 189, 248, 130);
        background-color: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(56, 189, 248, 22),
            stop: 1 rgba(18, 20, 28, 55)
        );
    }
    QWidget#TaskRow[stain="emerald"] {
        border-left-color: rgba(16, 185, 129, 125);
        background-color: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(16, 185, 129, 20),
            stop: 1 rgba(18, 20, 28, 55)
        );
    }
    QWidget#TaskRow[stain="violet"] {
        border-left-color: rgba(139, 92, 246, 125);
        background-color: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(139, 92, 246, 18),
            stop: 1 rgba(18, 20, 28, 55)
        );
    }
    QWidget#TaskRow[stain="rose"] {
        border-left-color: rgba(244, 63, 94, 125);
        background-color: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(244, 63, 94, 16),
            stop: 1 rgba(18, 20, 28, 55)
        );
    }
    QWidget#TaskRow[stain="amber"] {
        border-left-color: rgba(245, 158, 11, 125);
        background-color: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(245, 158, 11, 16),
            stop: 1 rgba(18, 20, 28, 55)
        );
    }
    QWidget#TaskRow[stain="blue"] {
        border-left-color: rgba(59, 130, 246, 125);
        background-color: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(59, 130, 246, 18),
            stop: 1 rgba(18, 20, 28, 55)
        );
    }
    QWidget#TaskRow[stain="teal"] {
        border-left-color: rgba(20, 184, 166, 125);
        background-color: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(20, 184, 166, 18),
            stop: 1 rgba(18, 20, 28, 55)
        );
    }
    QWidget#TaskRow[stain="lime"] {
        border-left-color: rgba(132, 204, 22, 125);
        background-color: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(132, 204, 22, 16),
            stop: 1 rgba(18, 20, 28, 55)
        );
    }
    QWidget#TaskRow[stain="fuchsia"] {
        border-left-color: rgba(217, 70, 239, 125);
        background-color: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(217, 70, 239, 18),
            stop: 1 rgba(18, 20, 28, 55)
        );
    }
    QWidget#TaskRow[stain="indigo"] {
        border-left-color: rgba(99, 102, 241, 125);
        background-color: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(99, 102, 241, 18),
            stop: 1 rgba(18, 20, 28, 55)
        );
    }
    QWidget#TaskRow[stain="orange"] {
        border-left-color: rgba(249, 115, 22, 125);
        background-color: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(249, 115, 22, 16),
            stop: 1 rgba(18, 20, 28, 55)
        );
    }

    QTabBar#DashboardTabs::tab {
        background-color: rgba(18, 20, 28, 135);
        border: 1px solid rgba(255, 255, 255, 18);
        border-top-left-radius: 0px;
        border-top-right-radius: 0px;
        padding: 8px 12px;
        margin-right: 6px;
        font-weight: 650;
    }

    QTabBar#DashboardTabs::tab:hover {
        background-color: rgba(255, 255, 255, 10);
        border: 1px solid rgba(255, 255, 255, 24);
    }

    QTabBar#DashboardTabs::tab:selected {
        background-color: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(16, 185, 129, 20),
            stop: 1 rgba(18, 20, 28, 75)
        );
        border: 1px solid rgba(16, 185, 129, 140);
    }

    QTabBar#DashboardTabs::tab:selected:hover {
        background-color: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(16, 185, 129, 26),
            stop: 1 rgba(18, 20, 28, 80)
        );
        border: 1px solid rgba(16, 185, 129, 170);
    }

    QWidget#TaskRow[stain="slate"]:hover,
    QWidget#TaskRow[stain="cyan"]:hover,
    QWidget#TaskRow[stain="emerald"]:hover,
    QWidget#TaskRow[stain="violet"]:hover,
    QWidget#TaskRow[stain="rose"]:hover,
    QWidget#TaskRow[stain="amber"]:hover,
    QWidget#TaskRow[stain="blue"]:hover,
    QWidget#TaskRow[stain="teal"]:hover,
    QWidget#TaskRow[stain="lime"]:hover,
    QWidget#TaskRow[stain="fuchsia"]:hover,
    QWidget#TaskRow[stain="indigo"]:hover,
    QWidget#TaskRow[stain="orange"]:hover {
        border-top: 1px solid rgba(255, 255, 255, 18);
        border-right: 1px solid rgba(255, 255, 255, 18);
        border-bottom: 1px solid rgba(255, 255, 255, 18);
        background-color: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(255, 255, 255, 14),
            stop: 1 rgba(18, 20, 28, 65)
        );
    }

    QWidget#TaskRow[selected="true"] {
        border-top: 1px solid rgba(56, 189, 248, 75);
        border-right: 1px solid rgba(56, 189, 248, 75);
        border-bottom: 1px solid rgba(56, 189, 248, 75);
        background-color: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(56, 189, 248, 16),
            stop: 1 rgba(18, 20, 28, 75)
        );
    }

    QPlainTextEdit#LogsView {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, \"Liberation Mono\", monospace;
        font-size: 12px;
    }
    """
