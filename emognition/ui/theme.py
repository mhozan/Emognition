# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""One light, high-contrast look for every Qt window, dialog and popup.

The setup window used to style only some widget types, over whatever palette
the desktop supplied. On a dark desktop theme that left the volume box black on
black, dropdown lists and spin-box arrows white on white, and message boxes dark
on dark. So the whole application now gets Qt's Fusion style (it draws every
widget from the palette, the same on Linux, Windows and macOS) and an explicit
light palette -- every colour role, with the disabled ones visibly greyed and
dark tooltips -- plus a small stylesheet for what palettes don't reach. Window
stylesheets then only add layout and accents.
"""

from __future__ import annotations

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

from .assets import ui_icon_path

INK = "#20203a"          # text
MUTED = "#5a5a7a"        # secondary text
DISABLED = "#a3a3b8"     # text of controls that don't apply right now
PAPER = "#ffffff"        # fields, lists, cards
WINDOW = "#f4f4f9"       # window backgrounds
BUTTON = "#ececf5"
BORDER = "#c4c4d6"
ACCENT = "#6c5ce7"
TIP = "#2a2250"          # tooltip background (white text)

_R = QPalette.ColorRole

# (role, normal colour, colour when disabled)
_ROLES = (
    (_R.Window, WINDOW, WINDOW),
    (_R.WindowText, INK, DISABLED),
    (_R.Base, PAPER, "#f2f2f7"),
    (_R.AlternateBase, "#f7f7fb", "#f7f7fb"),
    (_R.Text, INK, DISABLED),
    (_R.PlaceholderText, "#9a9ab0", "#c0c0d0"),
    (_R.Button, BUTTON, "#f0f0f5"),
    (_R.ButtonText, INK, DISABLED),
    (_R.BrightText, "#ffffff", "#ffffff"),
    (_R.Highlight, ACCENT, "#cfcbf3"),
    (_R.HighlightedText, "#ffffff", "#ffffff"),
    (_R.ToolTipBase, TIP, TIP),
    (_R.ToolTipText, "#ffffff", "#ffffff"),
    (_R.Link, ACCENT, DISABLED),
    # Fusion draws bevels, frames and spin-box arrows from these.
    (_R.Light, "#ffffff", "#ffffff"),
    (_R.Midlight, "#e4e4ee", "#e4e4ee"),
    (_R.Mid, BORDER, "#d6d6e2"),
    (_R.Dark, "#8a8aa6", "#b4b4c6"),
    (_R.Shadow, "#5a5a7a", "#9a9ab0"),
)


def _url(name: str) -> str:
    """A stylesheet url() for a theme icon (forward slashes work on Windows too)."""
    return "url(" + ui_icon_path(name).replace("\\", "/") + ")"


# Restyling a checkbox, dropdown or spin box means supplying its check mark and
# arrows as images: without them Qt draws none (unchecked boxes were invisible and
# dropdowns had no arrow), so the controls looked inert.
STYLESHEET = f"""
QToolTip {{ color: #ffffff; background: {TIP}; border: 1px solid {TIP};
           padding: 6px 8px; border-radius: 4px; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {PAPER}; color: {INK}; border: 1px solid {BORDER};
    border-radius: 7px; padding: 6px 8px; min-height: 18px;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border: 1px solid {ACCENT}; }}
QComboBox {{ padding-right: 28px; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right;
                       width: 26px; border: none; }}
QComboBox::down-arrow {{ image: {_url("arrow-down")}; width: 10px; height: 10px; }}
QComboBox::down-arrow:disabled {{ image: {_url("arrow-down-disabled")}; }}
QSpinBox, QDoubleSpinBox {{ padding-right: 24px; }}
QSpinBox::up-button, QDoubleSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border; width: 22px; border-left: 1px solid {BORDER}; background: {WINDOW};
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{ subcontrol-position: top right;
    border-top-right-radius: 7px; border-bottom: 1px solid {BORDER}; }}
QSpinBox::down-button, QDoubleSpinBox::down-button {{ subcontrol-position: bottom right;
    border-bottom-right-radius: 7px; }}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{ background: #e8e6fb; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: {_url("arrow-up")}; width: 9px; height: 9px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: {_url("arrow-down")}; width: 9px; height: 9px; }}
QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled {{ image: {_url("arrow-up-disabled")}; }}
QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:disabled {{ image: {_url("arrow-down-disabled")}; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid #8a8aa6;
                       border-radius: 4px; background: {PAPER}; }}
QCheckBox::indicator:hover {{ border: 1px solid {ACCENT}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border: 1px solid {ACCENT}; image: {_url("check")}; }}
QCheckBox::indicator:disabled {{ background: #f2f2f7; border: 1px solid #d6d6e2; }}
QCheckBox::indicator:checked:disabled {{ background: #cfcbf3; border: 1px solid #cfcbf3; }}
QMessageBox, QDialog {{ background: {PAPER}; }}
QMessageBox QLabel {{ color: {INK}; }}
QComboBox QAbstractItemView {{
    background: {PAPER}; color: {INK}; border: 1px solid {BORDER};
    selection-background-color: {ACCENT}; selection-color: #ffffff; outline: none;
}}
QCheckBox:disabled, QRadioButton:disabled, QLabel:disabled {{ color: {DISABLED}; }}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
    color: {DISABLED}; background: #f2f2f7;
}}
"""


def light_palette() -> QPalette:
    """The palette above, for the active, inactive and disabled colour groups."""
    palette = QPalette()
    groups = QPalette.ColorGroup
    for role, normal, disabled in _ROLES:
        for group in (groups.Active, groups.Inactive):
            palette.setColor(group, role, QColor(normal))
        palette.setColor(groups.Disabled, role, QColor(disabled))
    return palette


def apply_theme(app: QApplication) -> QApplication:
    """Give *app* the Fusion style, the light palette and the shared stylesheet."""
    app.setStyle("Fusion")
    app.setPalette(light_palette())
    app.setStyleSheet(STYLESHEET)
    return app
