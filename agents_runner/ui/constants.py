from __future__ import annotations

from agents_runner.prompts import load_prompt

PIXELARCH_EMERALD_IMAGE = "lunamidori5/pixelarch:emerald"
APP_TITLE = "Midori AI Agents Runner"
PIXELARCH_AGENT_CONTEXT_SUFFIX = load_prompt(
    "pixelarch_environment",
)

PIXELARCH_GIT_CONTEXT_SUFFIX = load_prompt(
    "github_version_control",
)

# UI Layout Constants (standardized across all pages)
# Main layout constants
MAIN_LAYOUT_MARGINS = (0, 0, 0, 0)
MAIN_LAYOUT_SPACING = 14

# Left navigation panel constants
LEFT_NAV_PANEL_WIDTH = 280
LEFT_NAV_COMPACT_THRESHOLD = 1080

# Header constants (GlassCard with title/subtitle/back)
HEADER_MARGINS = (18, 16, 18, 16)
HEADER_SPACING = 10

# Content card constants (GlassCard with form/content)
CARD_MARGINS = (18, 16, 18, 16)
CARD_SPACING = 12

# Tab content constants (for widgets inside tab containers)
TAB_CONTENT_MARGINS = (0, 16, 0, 12)
TAB_CONTENT_SPACING = 10

# Grid layout constants
GRID_HORIZONTAL_SPACING = 10
GRID_VERTICAL_SPACING = 10

# Button row constants
BUTTON_ROW_SPACING = 10

# Standard button width for Browse/similar buttons
STANDARD_BUTTON_WIDTH = 100

# Table row height
TABLE_ROW_HEIGHT = 56

# Standard column widths
AGENT_COMBO_WIDTH = 170
