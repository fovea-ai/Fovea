# =============================================================================
# approval_key_dialog.py — Approval Key Generation & Claiming Dialog
# =============================================================================
#
# This dialog has two tabs:
#
# TAB 1 — CLAIM A KEY (for any user):
#   Users who received an approval key from the admin paste it here.
#   Claiming a key gives them "approved" status on their machine,
#   which allows them to vote on and upload AI training photos.
#
# TAB 2 — ADMIN PANEL (for the app owner only):
#   Protected by the master password set in Settings.
#   Allows the admin to:
#   - Generate new one-time approval keys
#   - See all keys (active, claimed, voided)
#   - Revoke keys that haven't been used yet
#   - Approve their own machine directly without a key
#
# RACE CONDITION PROTECTION (for beginners — this is advanced):
#   A "race condition" happens when two things try to do the same action
#   at exactly the same time. If two people claim the same key at the
#   exact same millisecond, both would succeed — which is wrong.
#
#   We prevent this by:
#   1. Atomically incrementing a "claim_attempts" counter in SQLite
#   2. After the increment, reading the counter back
#   3. If counter > 1, MULTIPLE people tried at once → void the key
#   4. Nobody gets approved — they both get "race condition" error
#   This guarantees each key can only ever be used by ONE person.
# =============================================================================

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QWidget, QScrollArea, QApplication,
    QTabWidget, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from ui.theme import *
from core.storage import (
    verify_admin_password, generate_approval_key, claim_approval_key,
    is_machine_approved, get_all_approval_keys, revoke_approval_key,
    admin_approve_this_machine
)


class ApprovalKeyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Approval Key System")
        self.setMinimumSize(660, 600)
        self.setStyleSheet(f"""
            QDialog {{ background: {BG2}; }}
            QLabel  {{ color: {TEXT}; font-family: '{FONT_DISPLAY}'; background: transparent; }}
            {SCROLLBAR}
        """)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr = QFrame()
        hdr.setFixedHeight(68)
        hdr.setStyleSheet(f"background: {BG3}; border-bottom: 1px solid {BORDER};")
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(24, 0, 24, 0)
        hdr_lay.setSpacing(0)

        col = QVBoxLayout()
        col.setSpacing(3)
        t = QLabel("Approval Key System")
        t.setStyleSheet(f"color: {TEXT}; font-size: 18px; font-weight: 800;")
        s = QLabel("One-time keys  |  Single use  |  Race-condition protected")
        s.setStyleSheet(f"color: {TEXT3}; font-size: 11px; font-family: '{FONT_MONO}';")
        col.addWidget(t)
        col.addWidget(s)
        hdr_lay.addLayout(col)
        root.addWidget(hdr)

        # Tabs
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background: {BG2};
            }}
            QTabBar::tab {{
                background: {BG3};
                color: {TEXT2};
                border: 1px solid {BORDER};
                border-bottom: none;
                border-radius: 6px 6px 0 0;
                padding: 10px 28px;
                font-size: 13px;
                font-weight: 600;
                font-family: '{FONT_DISPLAY}';
                margin-right: 4px;
                min-width: 130px;
            }}
            QTabBar::tab:selected {{
                background: {BG2};
                color: {ACCENT};
                font-weight: 700;
            }}
            QTabBar::tab:hover {{ color: {TEXT}; }}
        """)

        self._tabs.addTab(self._build_claim_tab(), "  Claim a Key")
        self._tabs.addTab(self._build_admin_tab(), "  Admin Panel")
        root.addWidget(self._tabs)

    # ── Claim tab ─────────────────────────────────────────────────────────────

    def _build_claim_tab(self):
        widget = QWidget()
        widget.setStyleSheet(f"background: {BG2};")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        # Status banner
        self._status_banner = QFrame()
        self._status_banner.setStyleSheet(f"""
            QFrame {{
                background: {SURFACE};
                border: 1px solid {BORDER};
                border-radius: {RADIUS};
            }}
        """)
        sb_lay = QHBoxLayout(self._status_banner)
        sb_lay.setContentsMargins(16, 14, 16, 14)
        sb_lay.setSpacing(10)

        self._status_dot_lbl = QLabel("●")
        self._status_dot_lbl.setStyleSheet(f"color: {TEXT3}; font-size: 14px;")
        self._status_dot_lbl.setFixedWidth(16)

        info_col = QVBoxLayout()
        info_col.setSpacing(3)
        self._status_text_lbl = QLabel("Not yet approved")
        self._status_text_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 13px; font-weight: 700;")
        self._status_sub_lbl = QLabel("Claim an approval key below to get access")
        self._status_sub_lbl.setStyleSheet(f"color: {TEXT3}; font-size: 11px; font-family: '{FONT_MONO}';")
        info_col.addWidget(self._status_text_lbl)
        info_col.addWidget(self._status_sub_lbl)

        sb_lay.addWidget(self._status_dot_lbl)
        sb_lay.addLayout(info_col)
        sb_lay.addStretch()
        layout.addWidget(self._status_banner)

        # Explanation
        exp = QLabel(
            "An approval key is a one-time code given to you by the Fovea admin.\n"
            "Once you claim it, it is permanently tied to your machine and can never be used again."
        )
        exp.setStyleSheet(f"color: {TEXT2}; font-size: 12px;")
        exp.setWordWrap(True)
        layout.addWidget(exp)

        # Key input label
        key_lbl = QLabel("Your Approval Key")
        key_lbl.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700;")
        layout.addWidget(key_lbl)

        # Key input + claim button
        input_row = QHBoxLayout()
        input_row.setSpacing(10)

        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText("VG-XXXXXXXXXXXXXXXXXXXXXXXXXXXX")
        self._key_input.setMinimumHeight(42)
        self._key_input.setStyleSheet(f"""
            QLineEdit {{
                background: {BG3};
                color: {TEXT};
                border: 1px solid {BORDER2};
                border-radius: {RADIUS_SM};
                padding: 10px 14px;
                font-family: '{FONT_MONO}';
                font-size: 13px;
                letter-spacing: 1px;
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
        """)

        self._claim_btn = QPushButton("Claim Key")
        self._claim_btn.setStyleSheet(btn_primary())
        self._claim_btn.setMinimumHeight(42)
        self._claim_btn.setMinimumWidth(110)
        self._claim_btn.clicked.connect(self._claim_key)

        input_row.addWidget(self._key_input)
        input_row.addWidget(self._claim_btn)
        layout.addLayout(input_row)

        # Result message
        self._claim_result = QLabel("")
        self._claim_result.setStyleSheet(f"color: {TEXT3}; font-size: 12px; font-family: '{FONT_MONO}';")
        self._claim_result.setWordWrap(True)
        self._claim_result.setMinimumHeight(20)
        layout.addWidget(self._claim_result)

        # NOW safe to refresh — all widgets are created
        self._refresh_status_banner()

        layout.addStretch()

        # Perks card
        perks = QFrame()
        perks.setStyleSheet(f"""
            QFrame {{
                background: {SURFACE};
                border: 1px solid {BORDER};
                border-radius: {RADIUS};
            }}
        """)
        pk_lay = QVBoxLayout(perks)
        pk_lay.setContentsMargins(18, 14, 18, 14)
        pk_lay.setSpacing(8)

        pk_title = QLabel("What approval gives you")
        pk_title.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700;")
        pk_lay.addWidget(pk_title)

        for item in [
            "Vote on AI training photos (Yes / No)",
            "Upload photos for AI training",
            "Help improve AI accuracy for everyone",
        ]:
            row = QHBoxLayout()
            row.setSpacing(8)
            tick = QLabel("✓")
            tick.setStyleSheet(f"color: {GREEN}; font-size: 13px; font-weight: 800;")
            tick.setFixedWidth(16)
            lbl = QLabel(item)
            lbl.setStyleSheet(f"color: {TEXT2}; font-size: 12px;")
            row.addWidget(tick)
            row.addWidget(lbl)
            row.addStretch()
            pk_lay.addLayout(row)

        layout.addWidget(perks)
        return widget

    # ── Admin tab ─────────────────────────────────────────────────────────────

    def _build_admin_tab(self):
        widget = QWidget()
        widget.setStyleSheet(f"background: {BG2};")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        # Warning banner
        warn = QFrame()
        warn.setStyleSheet(f"""
            QFrame {{
                background: rgba(255,209,102,0.07);
                border: 1px solid rgba(255,209,102,0.3);
                border-radius: {RADIUS_SM};
            }}
        """)
        wl = QHBoxLayout(warn)
        wl.setContentsMargins(14, 12, 14, 12)
        wl.setSpacing(10)
        wicon = QLabel("!")
        wicon.setStyleSheet(f"color: {YELLOW}; font-size: 16px; font-weight: 800;")
        wicon.setFixedWidth(16)
        wtext = QLabel(
            "Admin panel. Enter your master password to generate keys or approve your machine."
        )
        wtext.setStyleSheet(f"color: {YELLOW}; font-size: 12px;")
        wtext.setWordWrap(True)
        wl.addWidget(wicon)
        wl.addWidget(wtext)
        layout.addWidget(warn)

        # Password label
        pw_lbl = QLabel("Master Password")
        pw_lbl.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700;")
        layout.addWidget(pw_lbl)

        # Password input row
        pw_row = QHBoxLayout()
        pw_row.setSpacing(10)

        self._admin_pw = QLineEdit()
        self._admin_pw.setPlaceholderText("Enter master password")
        self._admin_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._admin_pw.setMinimumHeight(42)
        self._admin_pw.setStyleSheet(f"""
            QLineEdit {{
                background: {BG3};
                color: {TEXT};
                border: 1px solid {BORDER2};
                border-radius: {RADIUS_SM};
                padding: 10px 14px;
                font-family: '{FONT_MONO}';
                font-size: 13px;
                letter-spacing: 3px;
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
        """)
        self._admin_pw.returnPressed.connect(self._generate_key)

        gen_btn = QPushButton("Generate Key")
        gen_btn.setStyleSheet(btn_primary())
        gen_btn.setMinimumHeight(42)
        gen_btn.setMinimumWidth(130)
        gen_btn.clicked.connect(self._generate_key)

        self_btn = QPushButton("Approve My Machine")
        self_btn.setStyleSheet(btn_ghost())
        self_btn.setMinimumHeight(42)
        self_btn.setMinimumWidth(170)
        self_btn.clicked.connect(self._self_approve)

        pw_row.addWidget(self._admin_pw)
        pw_row.addWidget(gen_btn)
        pw_row.addWidget(self_btn)
        layout.addLayout(pw_row)

        # Generated key display (hidden until a key is generated)
        self._gen_frame = QFrame()
        self._gen_frame.setStyleSheet(f"""
            QFrame {{
                background: rgba(0,212,255,0.06);
                border: 1px solid rgba(0,212,255,0.3);
                border-radius: {RADIUS_SM};
            }}
        """)
        gen_frame_lay = QHBoxLayout(self._gen_frame)
        gen_frame_lay.setContentsMargins(14, 12, 14, 12)
        gen_frame_lay.setSpacing(10)

        self._gen_key_lbl = QLabel("")
        self._gen_key_lbl.setStyleSheet(
            f"color: {ACCENT}; font-family: '{FONT_MONO}'; font-size: 13px; font-weight: 700;"
        )
        self._gen_key_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        copy_btn = QPushButton("Copy")
        copy_btn.setStyleSheet(btn_ghost())
        copy_btn.setMinimumHeight(36)
        copy_btn.setMinimumWidth(80)
        copy_btn.clicked.connect(self._copy_key)

        gen_frame_lay.addWidget(self._gen_key_lbl)
        gen_frame_lay.addStretch()
        gen_frame_lay.addWidget(copy_btn)
        self._gen_frame.hide()
        layout.addWidget(self._gen_frame)

        # Keys list header
        keys_hdr = QHBoxLayout()
        keys_title = QLabel("All Generated Keys")
        keys_title.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700;")
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(btn_ghost())
        refresh_btn.setMinimumHeight(32)
        refresh_btn.clicked.connect(self._refresh_keys)
        keys_hdr.addWidget(keys_title)
        keys_hdr.addStretch()
        keys_hdr.addWidget(refresh_btn)
        layout.addLayout(keys_hdr)

        # Keys scroll list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: 1px solid {BORDER};
                border-radius: {RADIUS_SM};
                background: {BG3};
            }}
            {SCROLLBAR}
        """)

        self._keys_widget = QWidget()
        self._keys_widget.setStyleSheet(f"background: {BG3};")
        self._keys_layout = QVBoxLayout(self._keys_widget)
        self._keys_layout.setContentsMargins(8, 8, 8, 8)
        self._keys_layout.setSpacing(6)
        self._keys_layout.addStretch()

        scroll.setWidget(self._keys_widget)
        layout.addWidget(scroll)

        return widget

    # ── Logic ─────────────────────────────────────────────────────────────────

    def _refresh_status_banner(self):
        approved = is_machine_approved()
        if approved:
            self._status_dot_lbl.setStyleSheet(f"color: {GREEN}; font-size: 14px;")
            self._status_text_lbl.setText("Approved")
            self._status_sub_lbl.setText("This machine is approved — you can vote and upload training photos")
            self._status_banner.setStyleSheet(f"""
                QFrame {{
                    background: {GREEN_DIM};
                    border: 1px solid rgba(0,255,157,0.3);
                    border-radius: {RADIUS};
                }}
            """)
            self._key_input.setEnabled(False)
            self._claim_btn.setEnabled(False)
            self._claim_btn.setText("Already Approved")
        else:
            self._status_dot_lbl.setStyleSheet(f"color: {TEXT3}; font-size: 14px;")
            self._status_text_lbl.setText("Not yet approved")
            self._status_sub_lbl.setText("Claim an approval key below to get access")
            self._status_banner.setStyleSheet(f"""
                QFrame {{
                    background: {SURFACE};
                    border: 1px solid {BORDER};
                    border-radius: {RADIUS};
                }}
            """)
            self._key_input.setEnabled(True)
            self._claim_btn.setEnabled(True)
            self._claim_btn.setText("Claim Key")

    def _claim_key(self):
        key = self._key_input.text().strip()
        if not key:
            self._set_result("Please paste your approval key.", TEXT3)
            return

        self._claim_btn.setEnabled(False)
        self._claim_btn.setText("Claiming...")

        result = claim_approval_key(key)

        messages = {
            "approved": ("Approved! Your machine now has access.", GREEN),
            "already":  ("This machine is already approved.", GREEN),
            "invalid":  ("Invalid key. Check that you copied it correctly.", RED),
            "used":     ("This key was already used by another machine.", RED),
            "voided":   ("This key has been voided or revoked.", RED),
            "race": (
                "Race condition: two machines tried this key at the same time.\n"
                "The key is now void. Contact the admin for a new one.",
                YELLOW
            ),
        }
        msg, color = messages.get(result, ("Unknown error.", RED))
        self._set_result(msg, color)

        if result in ("approved", "already"):
            self._refresh_status_banner()
        else:
            self._claim_btn.setEnabled(True)
            self._claim_btn.setText("Claim Key")

    def _set_result(self, msg, color):
        self._claim_result.setText(msg)
        self._claim_result.setStyleSheet(
            f"color: {color}; font-size: 12px; font-family: '{FONT_MONO}';"
        )

    def _generate_key(self):
        pw = self._admin_pw.text()
        if not pw:
            QMessageBox.warning(self, "Missing", "Enter the master password first.")
            return

        key = generate_approval_key(pw)
        if key is None:
            QMessageBox.warning(self, "Wrong Password",
                "Incorrect master password. Try again.")
            self._admin_pw.clear()
            self._admin_pw.setFocus()
            return

        self._admin_pw.clear()
        self._gen_key_lbl.setText(key)
        self._gen_frame.show()
        self._refresh_keys()

    def _self_approve(self):
        pw = self._admin_pw.text()
        if not pw:
            QMessageBox.warning(self, "Missing", "Enter the master password first.")
            return
        if admin_approve_this_machine(pw):
            self._admin_pw.clear()
            QMessageBox.information(self, "Approved",
                "Your machine is now approved as admin.\n"
                "You can vote on and upload training photos.")
            self._tabs.setCurrentIndex(0)
            self._refresh_status_banner()
        else:
            QMessageBox.warning(self, "Wrong Password", "Incorrect master password.")
            self._admin_pw.clear()

    def _copy_key(self):
        key = self._gen_key_lbl.text()
        if not key:
            return
        QApplication.clipboard().setText(key)
        self._gen_key_lbl.setText(key + "   (Copied!)")
        QTimer.singleShot(2000, lambda: self._gen_key_lbl.setText(key))

    def _refresh_keys(self):
        # Clear existing items (keep the stretch at the end)
        while self._keys_layout.count() > 1:
            item = self._keys_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        keys = get_all_approval_keys()
        if not keys:
            lbl = QLabel("No keys generated yet.")
            lbl.setStyleSheet(f"color: {TEXT3}; font-size: 12px; padding: 12px; font-family: '{FONT_MONO}';")
            self._keys_layout.insertWidget(0, lbl)
            return

        status_colors = {"active": ACCENT, "claimed": GREEN, "voided": RED}
        status_icons  = {"active": "○", "claimed": "✓", "voided": "✗"}

        for kid, key, status, claimed_by, created_at, claimed_at, attempts in keys:
            row = QFrame()
            row.setStyleSheet(f"""
                QFrame {{
                    background: {SURFACE};
                    border: 1px solid {BORDER};
                    border-radius: {RADIUS_SM};
                }}
            """)
            row.setMinimumHeight(54)
            rl = QHBoxLayout(row)
            rl.setContentsMargins(14, 10, 14, 10)
            rl.setSpacing(10)

            color = status_colors.get(status, TEXT3)
            icon  = status_icons.get(status, "?")

            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet(f"color: {color}; font-size: 15px; font-family: '{FONT_MONO}'; font-weight: 700;")
            icon_lbl.setFixedWidth(18)

            key_short = key[:34] + "..." if len(key) > 34 else key
            key_lbl = QLabel(key_short)
            key_lbl.setStyleSheet(f"color: {color}; font-family: '{FONT_MONO}'; font-size: 11px;")
            key_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

            meta = created_at[:16] if created_at else ""
            if status == "claimed" and claimed_at:
                meta += f"  |  claimed {claimed_at[:16]}"
            if attempts > 1:
                meta += f"  |  {attempts} attempts (race)"
            meta_lbl = QLabel(meta)
            meta_lbl.setStyleSheet(f"color: {TEXT3}; font-size: 10px; font-family: '{FONT_MONO}';")

            info_col = QVBoxLayout()
            info_col.setSpacing(3)
            info_col.addWidget(key_lbl)
            info_col.addWidget(meta_lbl)

            rl.addWidget(icon_lbl)
            rl.addLayout(info_col)
            rl.addStretch()

            if status == "active":
                revoke_btn = QPushButton("Revoke")
                revoke_btn.setStyleSheet(btn_danger())
                revoke_btn.setMinimumHeight(30)
                revoke_btn.setMinimumWidth(70)
                revoke_btn.clicked.connect(lambda _, k=kid: self._revoke(k))
                rl.addWidget(revoke_btn)

            self._keys_layout.insertWidget(self._keys_layout.count() - 1, row)

    def _revoke(self, key_id):
        reply = QMessageBox.question(
            self, "Revoke Key",
            "Revoke this key? If not yet used, it becomes void immediately."
        )
        if reply == QMessageBox.StandardButton.Yes:
            revoke_approval_key(key_id)
            self._refresh_keys()