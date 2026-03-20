# =============================================================================
# voting_popup.py — Training Photo Voting Popup
# =============================================================================
#
# This popup appears automatically when the user opens Fovea,
# IF there are any training photos waiting to be voted on.
#
# HOW IT WORKS (for beginners):
#   - Shows one photo at a time with its description
#   - User votes: "Yes, this description is accurate" or "No, it's wrong"
#   - User can also Skip (move to next without voting) or Report (flag bad content)
#   - "Skip All" closes the popup without voting on anything
#
# The votes are stored in the database and counted in real time.
# When 2 approved users vote Yes, the photo is approved for training.
# When 2 approved users vote No, it is rejected.
# Each machine can only vote ONCE per photo (tracked by machine ID).
# =============================================================================

from ui.theme import *
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
import os
from core.storage import get_submissions_for_voting, cast_vote, report_submission


BG     = "#0a0a14"
CARD   = "#12122a"
ACCENT = "#00d4ff"
TEXT   = "#f0f0f0"
DIM    = "#606080"
GREEN  = "#00ff9d"
RED    = "#ff4466"
ORANGE = "#ffaa00"


class VotingPopup(QDialog):
    """
    Shown on app launch when there are pending items to vote on.
    Shows one item at a time. User can: Yes, No, Skip, Skip All, Report.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Help Train the AI")
        self.setFixedSize(560, 520)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint)
        self.setStyleSheet(f"background: {BG};")

        self._items = get_submissions_for_voting()

        self._index = 0
        self._voted = 0

        if not self._items:
            self._empty = True
        else:
            self._empty = False
            self._build_ui()
            self._show_item()

    def should_show(self):
        return not self._empty

    def _build_ui(self):
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(32, 28, 32, 24)
        self._root.setSpacing(0)

        # Header
        header_row = QHBoxLayout()
        title = QLabel("Help Train the AI")
        title.setStyleSheet(f"color: {TEXT}; font-size: 18px; font-weight: 800;")
        self._counter_lbl = QLabel("")
        self._counter_lbl.setStyleSheet(f"color: {DIM}; font-size: 12px;")
        header_row.addWidget(title)
        header_row.addStretch()
        header_row.addWidget(self._counter_lbl)
        self._root.addLayout(header_row)
        self._root.addSpacing(4)

        sub = QLabel("Does the description accurately match the photo?")
        sub.setStyleSheet(f"color: {DIM}; font-size: 12px;")
        self._root.addWidget(sub)
        self._root.addSpacing(20)

        # Image card
        img_card = QFrame()
        img_card.setStyleSheet(f"""
            QFrame {{
                background: #080816;
                border: 1px solid rgba(0,212,255,0.15);
                border-radius: 12px;
            }}
        """)
        img_layout = QVBoxLayout(img_card)
        img_layout.setContentsMargins(0, 0, 0, 0)
        img_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._img_lbl = QLabel()
        self._img_lbl.setFixedSize(496, 260)
        self._img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_lbl.setStyleSheet("color: #404060; font-size: 13px; border-radius: 12px;")
        img_layout.addWidget(self._img_lbl)
        self._root.addWidget(img_card)
        self._root.addSpacing(16)

        # Description
        self._desc_lbl = QLabel()
        self._desc_lbl.setStyleSheet(f"""
            color: {TEXT};
            font-size: 15px;
            font-weight: 600;
            background: rgba(0,212,255,0.06);
            border: 1px solid rgba(0,212,255,0.2);
            border-radius: 8px;
            padding: 12px 16px;
        """)
        self._desc_lbl.setWordWrap(True)
        self._desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._root.addWidget(self._desc_lbl)
        self._root.addSpacing(20)

        # Vote buttons row
        vote_row = QHBoxLayout()
        vote_row.setSpacing(10)

        self._yes_btn = QPushButton("✓  Yes, Accurate")
        self._yes_btn.setStyleSheet(f"""
            QPushButton {{
                background: {GREEN};
                color: #000;
                border: none;
                border-radius: 9px;
                font-size: 13px;
                font-weight: 800;
                padding: 12px 0;
            }}
            QPushButton:hover {{ background: #00ffb0; }}
        """)
        self._yes_btn.clicked.connect(lambda: self._vote("yes"))

        self._no_btn = QPushButton("✗  No, Wrong")
        self._no_btn.setStyleSheet(f"""
            QPushButton {{
                background: {RED};
                color: #fff;
                border: none;
                border-radius: 9px;
                font-size: 13px;
                font-weight: 800;
                padding: 12px 0;
            }}
            QPushButton:hover {{ background: #ff6680; }}
        """)
        self._no_btn.clicked.connect(lambda: self._vote("no"))

        vote_row.addWidget(self._yes_btn)
        vote_row.addWidget(self._no_btn)
        self._root.addLayout(vote_row)
        self._root.addSpacing(10)

        # Skip / report row
        skip_row = QHBoxLayout()
        skip_row.setSpacing(10)

        report_btn = QPushButton("⚑  Report")
        report_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {ORANGE};
                border: 1px solid rgba(255,170,0,0.4);
                border-radius: 8px;
                font-size: 12px;
                font-weight: 600;
                padding: 8px 16px;
            }}
            QPushButton:hover {{ background: rgba(255,170,0,0.1); }}
        """)
        report_btn.clicked.connect(self._report)

        skip_btn = QPushButton("Skip")
        skip_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {DIM};
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 8px;
                font-size: 12px;
                font-weight: 600;
                padding: 8px 16px;
            }}
            QPushButton:hover {{ color: {TEXT}; border-color: rgba(255,255,255,0.3); }}
        """)
        skip_btn.clicked.connect(self._skip)

        skip_all_btn = QPushButton("Skip All")
        skip_all_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {DIM};
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 8px;
                font-size: 12px;
                font-weight: 600;
                padding: 8px 16px;
            }}
            QPushButton:hover {{ color: {TEXT}; border-color: rgba(255,255,255,0.3); }}
        """)
        skip_all_btn.clicked.connect(self._skip_all)

        skip_row.addWidget(report_btn)
        skip_row.addStretch()
        skip_row.addWidget(skip_btn)
        skip_row.addWidget(skip_all_btn)
        self._root.addLayout(skip_row)

    def _show_item(self):
        if self._index >= len(self._items):
            self._finish()
            return

        item = self._items[self._index]
        sub_id, filepath, description, votes_yes, votes_no, vote_total = item

        self._counter_lbl.setText(f"{self._index + 1} of {len(self._items)}")

        # Load image
        if os.path.exists(filepath):
            pix = QPixmap(filepath).scaled(
                496, 260,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self._img_lbl.setPixmap(pix)
        else:
            self._img_lbl.setText("Image not found")
            self._img_lbl.setPixmap(QPixmap())

        self._desc_lbl.setText(f'"{description}"')

    def _vote(self, vote):
        if self._index >= len(self._items):
            return
        item   = self._items[self._index]
        sub_id = item[0]
        cast_vote(sub_id, vote)
        self._voted += 1
        self._index += 1
        self._show_item()

    def _skip(self):
        self._index += 1
        self._show_item()

    def _skip_all(self):
        self._finish()

    def _report(self):
        if self._index >= len(self._items):
            return
        item   = self._items[self._index]
        sub_id = item[0]
        report_submission(sub_id)
        self._index += 1
        self._show_item()


    def _finish(self):
        self.accept()