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

    QStackedWidget#page_stack,
    QWidget#overview_page,
    QWidget#cpu_page,
    QWidget#memory_page,
    QWidget#disk_page,
    QWidget#network_page,
    QWidget#processes_page,
    QScrollArea#page_scroll_area,
    QWidget#page_content {{
        background-color: {colors.SURFACE};
        color: {colors.TEXT_PRIMARY};
    }}

    QScrollArea#page_scroll_area {{
        border: none;
    }}

    QScrollArea#page_scroll_area QWidget#qt_scrollarea_viewport {{
        background-color: {colors.SURFACE};
    }}

    QLabel#page_description {{
        color: {colors.TEXT_MUTED};
        font-size: {typography.FONT_SIZE_BODY}px;
    }}

    QLabel#page_data_status {{
        color: {colors.STATUS_TEXT};
        font-size: {typography.FONT_SIZE_SMALL}px;
        padding-bottom: 4px;
    }}

    QLabel {{
        color: {colors.TEXT_SECONDARY};
    }}

    QTableWidget#monitoring_table {{
        background-color: {colors.SURFACE};
        alternate-background-color: {colors.SIDEBAR_BACKGROUND};
        color: {colors.TEXT_PRIMARY};
        gridline-color: {colors.BORDER};
        border: 1px solid {colors.BORDER};
        border-radius: 8px;
        selection-background-color: {colors.ACCENT_PRIMARY};
        selection-color: {colors.TEXT_INVERSE};
        outline: none;
    }}

    QTableWidget#monitoring_table::item {{
        padding: 5px 8px;
        border-bottom: 1px solid {colors.BORDER};
    }}

    QTableWidget#monitoring_table::item:selected {{
        background-color: {colors.ACCENT_PRIMARY};
    }}

    QHeaderView::section {{
        background-color: {colors.SIDEBAR_BACKGROUND};
        color: {colors.TEXT_SECONDARY};
        border: none;
        border-bottom: 1px solid {colors.BORDER};
        padding: 9px 8px;
        font-weight: {typography.FONT_WEIGHT_SEMIBOLD};
    }}

    QScrollBar:vertical {{
        background-color: {colors.BACKGROUND};
        width: 11px;
        margin: 0;
    }}

    QScrollBar::handle:vertical {{
        background-color: {colors.BORDER};
        min-height: 24px;
        border-radius: 5px;
    }}

    QScrollBar:horizontal {{
        background-color: {colors.BACKGROUND};
        height: 11px;
        margin: 0;
    }}

    QScrollBar::handle:horizontal {{
        background-color: {colors.BORDER};
        min-width: 24px;
        border-radius: 5px;
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

    QFrame#metric_card {{
        background-color: {colors.SURFACE};
        border: 1px solid {colors.BORDER};
        border-radius: {spacing.RADIUS_PAGE_CONTAINER}px;
    }}

    QLabel#metric_card_title {{
        color: {colors.TEXT_MUTED};
        font-size: {typography.FONT_SIZE_BODY}px;
        font-weight: {typography.FONT_WEIGHT_SEMIBOLD};
    }}

    QLabel#metric_card_value {{
        color: {colors.TEXT_PRIMARY};
        font-size: {typography.FONT_SIZE_METRIC_VALUE}px;
        font-weight: {typography.FONT_WEIGHT_BOLD};
    }}

    QLabel#metric_card_unit {{
        color: {colors.TEXT_SECONDARY};
        font-size: {typography.FONT_SIZE_BODY}px;
    }}

    QLabel#metric_card_description {{
        color: {colors.TEXT_MUTED};
        font-size: {typography.FONT_SIZE_SMALL}px;
    }}

    QWidget#section_header {{
        background-color: transparent;
    }}

    QLabel#section_header_title {{
        color: {colors.TEXT_SECONDARY};
        font-size: {typography.FONT_SIZE_SECTION}px;
        font-weight: {typography.FONT_WEIGHT_SEMIBOLD};
    }}

    QLabel#section_header_description {{
        color: {colors.TEXT_MUTED};
        font-size: {typography.FONT_SIZE_BODY}px;
    }}

    QFrame#status_indicator {{
        background-color: transparent;
        border: none;
    }}

    QLabel#status_indicator_marker {{
        border-radius: 4px;
    }}

    QFrame#status_indicator[status="success"] QLabel#status_indicator_marker {{
        background-color: {colors.STATUS_SUCCESS};
    }}

    QFrame#status_indicator[status="warning"] QLabel#status_indicator_marker {{
        background-color: {colors.STATUS_WARNING};
    }}

    QFrame#status_indicator[status="error"] QLabel#status_indicator_marker {{
        background-color: {colors.STATUS_ERROR};
    }}

    QFrame#status_indicator[status="info"] QLabel#status_indicator_marker {{
        background-color: {colors.STATUS_INFO};
    }}

    QFrame#status_indicator[status="neutral"] QLabel#status_indicator_marker {{
        background-color: {colors.STATUS_NEUTRAL};
    }}

    QLabel#status_indicator_text {{
        color: {colors.TEXT_SECONDARY};
        font-size: {typography.FONT_SIZE_BODY}px;
    }}

    QFrame#loading_state,
    QFrame#empty_state,
    QFrame#error_state {{
        background-color: transparent;
        border: none;
    }}

    QLabel#loading_state_title,
    QLabel#empty_state_title,
    QLabel#error_state_title {{
        color: {colors.TEXT_PRIMARY};
        font-weight: {typography.FONT_WEIGHT_SEMIBOLD};
    }}

    QLabel#loading_state_description,
    QLabel#empty_state_description,
    QLabel#error_state_description {{
        color: {colors.TEXT_SECONDARY};
    }}
    """