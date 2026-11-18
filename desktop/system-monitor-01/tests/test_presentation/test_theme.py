"""Tests for the presentation theme foundation."""

import re

from system_monitor.presentation.theme import build_stylesheet
from system_monitor.presentation.theme import colors, spacing, typography


def test_color_tokens_are_valid_hex_values():
    """Every colour token must use a valid six-digit hex value."""
    color_tokens = {
        name: value
        for name, value in vars(colors).items()
        if name.isupper()
    }

    assert color_tokens

    for name, value in color_tokens.items():
        assert isinstance(value, str), name
        assert re.fullmatch(r"#[0-9A-Fa-f]{6}", value), name


def test_typography_tokens_are_positive_integers():
    """Typography sizes, weights and letter spacing must be positive."""
    typography_tokens = {
        name: value
        for name, value in vars(typography).items()
        if name.isupper()
    }

    assert typography_tokens

    for name, value in typography_tokens.items():
        assert isinstance(value, int), name
        assert value > 0, name


def test_spacing_tokens_are_non_negative_integers():
    """Spacing and sizing tokens must be non-negative integers."""
    spacing_tokens = {
        name: value
        for name, value in vars(spacing).items()
        if name.isupper()
    }

    assert spacing_tokens

    for name, value in spacing_tokens.items():
        assert isinstance(value, int), name
        assert value >= 0, name


def test_build_stylesheet_returns_non_empty_string():
    """The stylesheet builder must return a non-empty string."""
    stylesheet = build_stylesheet()

    assert isinstance(stylesheet, str)
    assert stylesheet.strip()


def test_stylesheet_contains_expected_widget_selectors():
    """The stylesheet must cover the existing main-window widgets."""
    stylesheet = build_stylesheet()

    expected_selectors = (
        "QMainWindow",
        "QWidget#sidebar",
        "QLabel#brand_label",
        "QLabel#brand_subtitle",
        "QPushButton#navigation_button",
        "QLabel#version_label",
        "QWidget#content_area",
        "QLabel#page_title",
        "QLabel#application_status",
        "QStackedWidget#page_stack",
        "QLabel#section_heading",
        "QLabel#placeholder_description",
    )

    for selector in expected_selectors:
        assert selector in stylesheet


def test_stylesheet_uses_centralized_color_tokens():
    """The stylesheet must contain the defined colour token values."""
    stylesheet = build_stylesheet()

    for name, value in vars(colors).items():
        if name.isupper():
            assert value in stylesheet, name


def test_stylesheet_uses_centralized_typography_tokens():
    """The stylesheet must use centralized typography values."""
    stylesheet = build_stylesheet()

    pixel_tokens = (
        typography.FONT_SIZE_SMALL,
        typography.FONT_SIZE_BODY,
        typography.FONT_SIZE_BRAND,
        typography.FONT_SIZE_SECTION,
        typography.FONT_SIZE_TITLE,
        typography.LETTER_SPACING_BRAND,
        typography.LETTER_SPACING_SUBTITLE,
    )

    weight_tokens = (
        typography.FONT_WEIGHT_SEMIBOLD,
        typography.FONT_WEIGHT_BOLD,
    )

    for value in pixel_tokens:
        assert f"{value}px" in stylesheet

    for value in weight_tokens:
        assert f"font-weight: {value};" in stylesheet


def test_stylesheet_uses_centralized_spacing_tokens():
    """The stylesheet must use the relevant spacing and radius values."""
    stylesheet = build_stylesheet()

    used_tokens = (
        spacing.RADIUS_NAVIGATION,
        spacing.NAVIGATION_PADDING_VERTICAL,
        spacing.NAVIGATION_PADDING_HORIZONTAL,
        spacing.VERSION_LABEL_PADDING_TOP,
        spacing.RADIUS_STATUS,
        spacing.STATUS_PADDING_VERTICAL,
        spacing.STATUS_PADDING_HORIZONTAL,
        spacing.RADIUS_PAGE_CONTAINER,
    )

    for value in used_tokens:
        assert f"{value}px" in stylesheet