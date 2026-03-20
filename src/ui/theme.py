# =============================================================================
# theme.py — Fovea Design System
# =============================================================================
#
# This file defines ALL colors, fonts, spacing, and reusable styles.
# Think of it like a "style guide" that every other UI file imports from.
#
# WHY HAVE ONE FILE FOR COLORS? (for beginners)
#   If you define colors in 10 different files, changing the main blue color
#   means editing 10 files and missing some. Here, you change ONE variable
#   and every button, label, and card in the app updates automatically.
#
# HOW TO USE:
#   In any UI file, write: from ui.theme import *
#   Then use: ACCENT, TEXT, BG, btn_primary(), etc.
#
# COLOR SYSTEM:
#   BG, BG2, BG3  → background layers (darkest to slightly lighter)
#   SURFACE       → card/panel backgrounds
#   BORDER        → subtle dividing lines
#   ACCENT        → the main teal/cyan highlight color (#00d4ff)
#   TEXT, TEXT2, TEXT3 → text colors (brightest to dimmest)
#   GREEN, RED, YELLOW → status indicator colors
# =============================================================================

# ── Fovea Design System ─────────────────────────────────────────────────
# Matches the dark navy / teal aesthetic from the HTML reference

BG       = "#080c10"
BG2      = "#0d1318"
BG3      = "#111920"
SURFACE  = "#131d26"
SURFACE2 = "#1a2733"
BORDER   = "#1f3040"
BORDER2  = "#2a3f52"

ACCENT      = "#00d4ff"
ACCENT2     = "#0099cc"
ACCENT_GLOW = "rgba(0,212,255,0.15)"
ACCENT_DIM  = "rgba(0,212,255,0.05)"

GREEN     = "#00ff9d"
GREEN_DIM = "rgba(0,255,157,0.12)"
RED       = "#ff4466"
RED_DIM   = "rgba(255,68,102,0.12)"
YELLOW    = "#ffd166"

TEXT  = "#e8f4f8"
TEXT2 = "#7a9bb0"
TEXT3 = "#4a6478"

FONT_DISPLAY = "Segoe UI"   # closest system font to Syne on Windows
FONT_MONO    = "Consolas"   # closest to JetBrains Mono on Windows

RADIUS    = "10px"
RADIUS_SM = "6px"

# ── Reusable stylesheet snippets ──────────────────────────────────────────────

SCROLLBAR = f"""
    QScrollBar:vertical {{
        background: {BG};
        width: 5px;
        border-radius: 3px;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER2};
        border-radius: 3px;
        min-height: 30px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{
        background: {BG};
        height: 5px;
        border-radius: 3px;
    }}
    QScrollBar::handle:horizontal {{
        background: {BORDER2};
        border-radius: 3px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
"""

def btn_primary(extra=""):
    return f"""
        QPushButton {{
            background: {ACCENT};
            color: #000;
            border: none;
            border-radius: {RADIUS_SM};
            font-family: '{FONT_DISPLAY}';
            font-size: 13px;
            font-weight: 700;
            padding: 7px 16px;
            {extra}
        }}
        QPushButton:hover {{
            background: #33ddff;
        }}
        QPushButton:focus {{ outline: none; }}
        QPushButton:disabled {{
            background: {SURFACE2};
            color: {TEXT3};
        }}
    """

def btn_ghost(extra=""):
    return f"""
        QPushButton {{
            background: transparent;
            color: {TEXT2};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_SM};
            font-family: '{FONT_DISPLAY}';
            font-size: 13px;
            font-weight: 600;
            padding: 7px 16px;
            {extra}
        }}
        QPushButton:hover {{
            border-color: {BORDER2};
            color: {TEXT};
            background: {SURFACE};
        }}
    """

def btn_danger(extra=""):
    return f"""
        QPushButton {{
            background: {RED_DIM};
            color: {RED};
            border: 1px solid rgba(255,68,102,0.3);
            border-radius: {RADIUS_SM};
            font-size: 13px;
            font-weight: 600;
            padding: 7px 16px;
            {extra}
        }}
        QPushButton:hover {{ background: rgba(255,68,102,0.22); }}
    """

def card_style(border_color=None):
    bc = border_color or BORDER
    return f"""
        QFrame {{
            background: {SURFACE};
            border: 1px solid {bc};
            border-radius: {RADIUS};
            outline: none;
        }}
        QFrame > QWidget {{
            background: transparent;
            border: none;
            outline: none;
        }}
        QFrame > QLabel {{
            background: transparent;
            border: none;
            outline: none;
        }}
    """

def input_style(extra=""):
    return f"""
        QLineEdit, QTextEdit, QSpinBox, QComboBox {{
            background: {BG3};
            color: {TEXT};
            border: 1px solid {BORDER2};
            border-radius: {RADIUS_SM};
            padding: 10px 14px;
            font-family: '{FONT_DISPLAY}';
            font-size: 13px;
            min-height: 20px;
            {extra}
        }}
        QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus {{
            border-color: {ACCENT};
        }}
        QLineEdit::placeholder, QTextEdit::placeholder {{ color: {TEXT3}; }}
        QComboBox::drop-down {{ border: none; padding-right: 8px; }}
        QComboBox QAbstractItemView {{
            background: {BG2};
            color: {TEXT};
            border: 1px solid {BORDER2};
            selection-background-color: {ACCENT};
            selection-color: #000;
        }}
    """

MONO_LABEL = f"font-family: '{FONT_MONO}'; font-size: 10px; color: {TEXT3}; letter-spacing: 2px;"