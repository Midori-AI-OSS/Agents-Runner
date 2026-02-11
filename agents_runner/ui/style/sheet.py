from .metrics import FONT_FAMILY_UI, FONT_SIZE_BODY
from .palette import (
    ACCENT_CYAN_SELECTION_BG,
    TEXT_PLACEHOLDER,
    TEXT_PRIMARY,
)

from .template_base import TEMPLATE_BASE
from .template_tasks import TEMPLATE_TASKS

_TEMPLATE = TEMPLATE_BASE + TEMPLATE_TASKS


def app_stylesheet() -> str:
    return (
        _TEMPLATE.replace("__STYLE_TEXT_PRIMARY__", TEXT_PRIMARY)
        .replace("__STYLE_FONT_FAMILY__", FONT_FAMILY_UI)
        .replace("__STYLE_FONT_SIZE__", FONT_SIZE_BODY)
        .replace("__STYLE_TEXT_PLACEHOLDER__", TEXT_PLACEHOLDER)
        .replace("__STYLE_SELECTION_BG__", ACCENT_CYAN_SELECTION_BG)
    )
