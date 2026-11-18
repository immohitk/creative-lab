"""Shared application stylesheet construction."""

from system_monitor.presentation.theme import colors, spacing, typography


def build_stylesheet() -> str:
    """Build the shared application stylesheet."""

    return f"""
    QMainWindow {{
        background-color: {colors.BACKGROUND};
    }}

    QWidget#sidebar {{
        background-color: {colors.SIDEBAR_BACKGROUND};
        border-right: 1px solid {colors.BORDER};
    }}

    QLabel#brand_label {{
        color: {colors.TEXT_PRIMARY};
        font-size: {typography.FONT_SIZE_BRAND}px;
        font-weight: {typography.FONT_WEIGHT_BOLD};
        letter-spacing: {typography.LETTER_SPACING_BRAND}px;
    }}

    QLabel#brand_subtitle {{
        color: {colors.TEXT_SUBDUED};
        font-size: {typography.FONT_SIZE_SMALL}px;
        font-weight: {typography.FONT_WEIGHT_SEMIBOLD};
        letter-spacing: {typography.LETTER_SPACING_SUBTITLE}px;
    }}

    QPushButton#navigation_button {{
        color: {colors.TEXT_NAVIGATION};
        background-color: transparent;
        border: none;
        border-radius: {spacing.RADIUS_NAVIGATION}px;
        text-align: left;
        padding: {spacing.NAVIGATION_PADDING_VERTICAL}px
                 {spacing.NAVIGATION_PADDING_HORIZONTAL}px;
        font-size: {typography.FONT_SIZE_BODY}px;
    }}

    QPushButton#navigation_button:hover {{
        color: {colors.TEXT_INVERSE};
        background-color: {colors.NAVIGATION_HOVER};
    }}

    QPushButton#navigation_button:checked {{
        color: {colors.TEXT_INVERSE};
        background-color: {colors.ACCENT_PRIMARY};
        font-weight: {typography.FONT_WEIGHT_SEMIBOLD};
    }}

    QLabel#version_label {{
        color: {colors.TEXT_SUBDUED};
        font-size: {typography.FONT_SIZE_SMALL}px;
        padding-top: {spacing.VERSION_LABEL_PADDING_TOP}px;
    }}

    QWidget#content_area {{
        background-color: {colors.BACKGROUND};
    }}

    QLabel#page_title {{
        color: {colors.TEXT_PRIMARY};
        font-size: {typography.FONT_SIZE_TITLE}px;
        font-weight: {typography.FONT_WEIGHT_BOLD};
    }}

    QLabel#application_status {{
        color: {colors.STATUS_TEXT};
        background-color: {colors.STATUS_BACKGROUND};
        border-radius: {spacing.RADIUS_STATUS}px;
        padding: {spacing.STATUS_PADDING_VERTICAL}px
                 {spacing.STATUS_PADDING_HORIZONTAL}px;
        font-size: {typography.FONT_SIZE_SMALL}px;
        font-weight: {typography.FONT_WEIGHT_BOLD};
    }}

    QStackedWidget#page_stack {{
        background-color: {colors.SURFACE};
        border: 1px solid {colors.BORDER};
        border-radius: {spacing.RADIUS_PAGE_CONTAINER}px;
    }}

    QLabel#section_heading {{
        color: {colors.TEXT_SECONDARY};
        font-size: {typography.FONT_SIZE_SECTION}px;
        font-weight: {typography.FONT_WEIGHT_SEMIBOLD};
    }}

    QLabel#placeholder_description {{
        color: {colors.TEXT_MUTED};
        font-size: {typography.FONT_SIZE_BODY}px;
    }}
    """