# =============================================================================
# dashboard.py — Dashboard Overview Page
# =============================================================================
import os
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGridLayout, QApplication, QMessageBox,
    QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from ui.theme import *
from core.storage import get_cameras, get_setting, search_frames, FRAMES_PATH

BTC_ADDRESS = "bc1qq3hda30w4cwfmxvya8747askvz3s4u0xnx2mf8"


class StatCard(QWidget):
    """A clean stat card with no inner borders."""
    def __init__(self, title, value, subtitle="", color=ACCENT):
        super().__init__()
        self.setStyleSheet(f"""
            QWidget {{
                background: {SURFACE};
                border: 1px solid {BORDER};
                border-radius: 10px;
            }}
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(110)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(6)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"""
            color: {TEXT3};
            font-size: 10px;
            font-family: '{FONT_MONO}';
            letter-spacing: 2px;
            background: transparent;
            border: none;
        """)
        lay.addWidget(title_lbl)

        self._val_lbl = QLabel(value)
        self._val_lbl.setStyleSheet(f"""
            color: {color};
            font-size: 30px;
            font-weight: 800;
            background: transparent;
            border: none;
        """)
        lay.addWidget(self._val_lbl)

        if subtitle:
            sub = QLabel(subtitle)
            sub.setStyleSheet(f"""
                color: {TEXT3};
                font-size: 11px;
                background: transparent;
                border: none;
            """)
            lay.addWidget(sub)

        lay.addStretch()

    def set_value(self, v):
        self._val_lbl.setText(str(v))


class DashboardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG}; border: none;")
        self._build_ui()
        self._refresh()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh)
        self._refresh_timer.start(8000)

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick)
        self._clock_timer.start(1000)
        self._tick()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(24)

        # ── Header row ────────────────────────────────────────────────────────
        header = QHBoxLayout()

        title_col = QVBoxLayout()
        title_col.setSpacing(3)

        title = QLabel("Dashboard")
        title.setStyleSheet(f"""
            color: {TEXT};
            font-size: 24px;
            font-weight: 800;
            letter-spacing: -0.5px;
            background: transparent;
            border: none;
        """)
        sub = QLabel("System overview")
        sub.setStyleSheet(f"""
            color: {TEXT3};
            font-size: 12px;
            font-family: '{FONT_MONO}';
            background: transparent;
            border: none;
        """)
        title_col.addWidget(title)
        title_col.addWidget(sub)

        header.addLayout(title_col)
        header.addStretch()

        self._clock_lbl = QLabel()
        self._clock_lbl.setStyleSheet(f"""
            color: {TEXT3};
            font-size: 12px;
            font-family: '{FONT_MONO}';
            background: transparent;
            border: none;
        """)
        header.addWidget(self._clock_lbl)
        root.addLayout(header)

        # ── Stat cards ────────────────────────────────────────────────────────
        self._card_cameras  = StatCard("CAMERAS",      "0", "total added",  ACCENT)
        self._card_frames   = StatCard("FRAMES TODAY", "0", "captured",     ACCENT)
        self._card_ai       = StatCard("AI PROVIDER",  "None", "configured", GREEN)
        self._card_storage  = StatCard("LOCAL STORAGE","0 MB", "used",       YELLOW)

        grid = QHBoxLayout()
        grid.setSpacing(14)
        for card in [self._card_cameras, self._card_frames,
                     self._card_ai, self._card_storage]:
            grid.addWidget(card)
        root.addLayout(grid)

        # ── Divider ───────────────────────────────────────────────────────────
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: {BORDER}; border: none;")
        root.addWidget(div)

        # ── Quick start ───────────────────────────────────────────────────────
        qs_label = QLabel("QUICK START")
        qs_label.setStyleSheet(f"""
            color: {TEXT3};
            font-size: 10px;
            font-family: '{FONT_MONO}';
            letter-spacing: 2px;
            background: transparent;
            border: none;
        """)
        root.addWidget(qs_label)

        steps = [
            (ACCENT,  "1", "Add a Camera",
             "Cameras  →  Add Camera  →  choose webcam or paste RTSP URL"),
            (GREEN,   "2", "Set an AI Key  (optional)",
             "Settings  →  choose provider  →  paste your API key  "
             "(app also works without one)"),
            (YELLOW,  "3", "Search Footage",
             "AI Search  →  describe what you saw  →  Search"),
        ]

        steps_widget = QWidget()
        steps_widget.setStyleSheet("background: transparent; border: none;")
        steps_lay = QVBoxLayout(steps_widget)
        steps_lay.setContentsMargins(0, 0, 0, 0)
        steps_lay.setSpacing(14)

        for color, num, title, desc in steps:
            row = QHBoxLayout()
            row.setSpacing(14)
            row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

            # Number circle
            circle = QLabel(num)
            circle.setFixedSize(32, 32)
            circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
            circle.setStyleSheet(f"""
                background: {color};
                color: #000;
                font-size: 14px;
                font-weight: 800;
                border-radius: 16px;
                border: none;
            """)

            # Text
            text_col = QVBoxLayout()
            text_col.setSpacing(2)
            t = QLabel(title)
            t.setStyleSheet(f"""
                color: {TEXT};
                font-size: 13px;
                font-weight: 700;
                background: transparent;
                border: none;
            """)
            d = QLabel(desc)
            d.setStyleSheet(f"""
                color: {TEXT2};
                font-size: 12px;
                background: transparent;
                border: none;
            """)
            text_col.addWidget(t)
            text_col.addWidget(d)

            row.addWidget(circle)
            row.addLayout(text_col)
            row.addStretch()
            steps_lay.addLayout(row)

        root.addWidget(steps_widget)
        root.addStretch()

        # ── BTC donation banner ───────────────────────────────────────────────
        btc = QWidget()
        btc.setStyleSheet(f"""
            QWidget {{
                background: rgba(255,170,0,0.07);
                border: 1px solid rgba(255,170,0,0.2);
                border-radius: 10px;
            }}
        """)
        btc.setMinimumHeight(70)
        btc_lay = QHBoxLayout(btc)
        btc_lay.setContentsMargins(18, 14, 18, 14)
        btc_lay.setSpacing(14)

        btc_label = QLabel("BTC")
        btc_label.setStyleSheet(f"""
            color: {YELLOW};
            font-size: 14px;
            font-weight: 900;
            background: transparent;
            border: none;
        """)
        btc_label.setFixedWidth(36)

        btc_info = QVBoxLayout()
        btc_info.setSpacing(2)
        btc_title = QLabel("Support Fovea")
        btc_title.setStyleSheet(f"""
            color: {TEXT};
            font-size: 13px;
            font-weight: 700;
            background: transparent;
            border: none;
        """)
        btc_sub = QLabel("Fovea is free and open source. If it helped you, consider a BTC donation.")
        btc_sub.setStyleSheet(f"""
            color: {TEXT2};
            font-size: 11px;
            background: transparent;
            border: none;
        """)
        btc_sub.setWordWrap(True)
        btc_info.addWidget(btc_title)
        btc_info.addWidget(btc_sub)

        btc_btn = QPushButton("Copy BTC Address")
        btc_btn.setStyleSheet(f"""
            QPushButton {{
                background: {YELLOW};
                color: #000;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 800;
                padding: 8px 18px;
                min-height: 36px;
            }}
            QPushButton:hover {{ background: #ffe066; }}
        """)
        btc_btn.clicked.connect(self._copy_btc)

        btc_lay.addWidget(btc_label)
        btc_lay.addLayout(btc_info)
        btc_lay.addStretch()
        btc_lay.addWidget(btc_btn)
        root.addWidget(btc)

        # ── Footer ────────────────────────────────────────────────────────────
        footer = QLabel("Open Source")
        footer.setStyleSheet(f"""
            color: {TEXT3};
            font-size: 10px;
            font-family: '{FONT_MONO}';
            background: transparent;
            border: none;
        """)
        root.addWidget(footer)

    # ── Logic ─────────────────────────────────────────────────────────────────

    def _refresh(self):
        cams = get_cameras()
        self._card_cameras.set_value(len(cams))

        provider = get_setting("ai_provider", "")
        names = {
            "openai": "ChatGPT", "gemini": "Gemini",
            "claude": "Claude",  "deepseek": "DeepSeek", "grok": "Grok"
        }
        self._card_ai.set_value(names.get(provider, "None") if provider else "None")

        # Count frames captured in the last 24 hours only
        frames_today = search_frames("", 24)
        self._card_frames.set_value(len(frames_today))

        total = 0
        for dp, _, files in os.walk(FRAMES_PATH):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(dp, f))
                except Exception:
                    pass
        mb = total / (1024 * 1024)
        self._card_storage.set_value(
            f"{mb / 1024:.1f} GB" if mb > 1024 else f"{mb:.0f} MB"
        )

    def _tick(self):
        self._clock_lbl.setText(
            datetime.now().strftime("%A  %d %B %Y    %H:%M:%S")
        )

    def _copy_btc(self):
        QApplication.clipboard().setText(BTC_ADDRESS)
        QMessageBox.information(
            self, "Copied",
            f"Bitcoin address copied:\n\n{BTC_ADDRESS}\n\nThank you for supporting Fovea!"
        )