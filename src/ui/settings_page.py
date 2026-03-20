# =============================================================================
# settings_page.py — Application Settings Page
# =============================================================================
#
# This page lets users configure Fovea.
#
# SETTINGS EXPLAINED (for beginners):
#
# AI Provider:
#   Pick which AI to use for searching. Each has a free tier or cheap pricing.
#   You need an API key from the provider's website.
#   ChatGPT:  platform.openai.com/api-keys
#   Gemini:   aistudio.google.com/app/apikey
#   Claude:   console.anthropic.com
#   Grok:     console.x.ai
#   DeepSeek: platform.deepseek.com (TEXT ONLY — can't see images)
#
# API Key Security:
#   Your key is encrypted with AES-128 before being stored.
#   Even if someone copied your database file, they can't read the key.
#
# Capture Interval:
#   How often to save a frame. Every 5 seconds = 720 frames/hour per camera.
#   Lower = more storage used. Higher = might miss fast events.
#
# Moderator Password:
#   The master password for the AI training moderation system.
#   Set this FIRST before trying to moderate training submissions.
#
# Approval Keys:
#   Generate one-time codes to give trusted users "approved" status,
#   which lets them vote on and upload AI training photos.
# =============================================================================

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QComboBox, QSpinBox, QMessageBox,
    QScrollArea, QButtonGroup, QSizePolicy
)
from PyQt6.QtCore import Qt
from ui.theme import *
from core.storage import (
    get_setting, set_setting, get_secure_setting, set_secure_setting,
    is_machine_approved, set_admin_password
)
from ui.approval_key_dialog import ApprovalKeyDialog

PROVIDERS = {
    "openai":   ("ChatGPT",   "GPT",  "https://platform.openai.com/api-keys",   True),
    "gemini":   ("Gemini",    "GEM",  "https://aistudio.google.com/app/apikey", True),
    "claude":   ("Claude",    "CLO",  "https://console.anthropic.com/",         True),
    "deepseek": ("DeepSeek",  "DSK",  "https://platform.deepseek.com/",         False),
    "grok":     ("Grok",      "GRK",  "https://console.x.ai/",                  True),
}


def _divider():
    f = QFrame()
    f.setFixedHeight(1)
    f.setStyleSheet(f"background: {BORDER}; border: none;")
    return f


def _section_card():
    card = QFrame()
    card.setStyleSheet(f"""
        QFrame {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: {RADIUS};
        }}
    """)
    return card


def _section_header(title, subtitle=""):
    f = QFrame()
    f.setStyleSheet(f"background: transparent; border: none; border-bottom: 1px solid {BORDER};")
    f.setMinimumHeight(52)
    lay = QHBoxLayout(f)
    lay.setContentsMargins(20, 12, 20, 12)
    t = QLabel(title)
    t.setStyleSheet(f"color: {TEXT}; font-size: 15px; font-weight: 700; background: transparent;")
    lay.addWidget(t)
    if subtitle:
        lay.addStretch()
        s = QLabel(subtitle)
        s.setStyleSheet(f"color: {TEXT3}; font-family: '{FONT_MONO}'; font-size: 11px; background: transparent;")
        lay.addWidget(s)
    return f


class ProviderButton(QPushButton):
    """A selectable AI provider button — plain text, no emoji."""

    def __init__(self, key, display_name, short_code, supports_vision):
        super().__init__()
        self._key = key
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumSize(110, 72)

        # All buttons show the same format: short code + full name
        # DeepSeek text-only warning is shown as a separate banner below the buttons
        label = f"{short_code}\n{display_name}"

        self.setText(label)
        self._apply(False)

    def _apply(self, selected):
        if selected:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {ACCENT_DIM};
                    border: 2px solid {ACCENT};
                    border-radius: {RADIUS_SM};
                    color: {ACCENT};
                    font-size: 12px;
                    font-weight: 800;
                    font-family: '{FONT_DISPLAY}';
                    padding: 8px 4px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {BG3};
                    border: 1px solid {BORDER};
                    border-radius: {RADIUS_SM};
                    color: {TEXT2};
                    font-size: 12px;
                    font-weight: 600;
                    font-family: '{FONT_DISPLAY}';
                    padding: 8px 4px;
                }}
                QPushButton:hover {{
                    border-color: {BORDER2};
                    color: {TEXT};
                    background: {SURFACE2};
                }}
            """)

    def setChecked(self, v):
        super().setChecked(v)
        self._apply(v)

    def key(self):
        return self._key


class SettingsRow(QFrame):
    """A single settings row with label + description on left, widget on right."""

    def __init__(self, label, description, widget=None):
        super().__init__()
        self.setStyleSheet("QFrame { background: transparent; border: none; }")
        self.setMinimumHeight(64)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 14, 20, 14)
        lay.setSpacing(20)

        info = QVBoxLayout()
        info.setSpacing(4)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700; background: transparent;")
        info.addWidget(lbl)
        if description:
            desc = QLabel(description)
            desc.setStyleSheet(f"color: {TEXT3}; font-size: 11px; background: transparent;")
            desc.setWordWrap(True)
            info.addWidget(desc)

        lay.addLayout(info)
        lay.addStretch()

        if widget:
            lay.addWidget(widget)


class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG};")
        self._provider_btns = {}
        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)
        self._build_ui()
        self._load()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {BG}; }} {SCROLLBAR}")

        container = QWidget()
        container.setStyleSheet(f"background: {BG};")
        content = QVBoxLayout(container)
        content.setContentsMargins(28, 28, 28, 40)
        content.setSpacing(24)

        # ── Page header ───────────────────────────────────────────────────────
        page_title = QLabel("Settings")
        page_title.setStyleSheet(
            f"color: {TEXT}; font-size: 24px; font-weight: 800; letter-spacing: -0.5px;"
        )
        page_sub = QLabel("Configure your AI provider, capture preferences, and access control")
        page_sub.setStyleSheet(f"color: {TEXT3}; font-family: '{FONT_MONO}'; font-size: 12px;")
        content.addWidget(page_title)
        content.addWidget(page_sub)

        # ── AI PROVIDER card ──────────────────────────────────────────────────
        ai_card = _section_card()
        ai_layout = QVBoxLayout(ai_card)
        ai_layout.setContentsMargins(0, 0, 0, 0)
        ai_layout.setSpacing(0)

        ai_layout.addWidget(_section_header(
            "AI Provider",
            "Your key stays on your machine"
        ))

        # Provider buttons grid
        providers_widget = QWidget()
        providers_widget.setStyleSheet("background: transparent;")
        pb_layout = QHBoxLayout(providers_widget)
        pb_layout.setContentsMargins(20, 18, 20, 18)
        pb_layout.setSpacing(12)

        for key, (name, short, url, vision) in PROVIDERS.items():
            btn = ProviderButton(key, name, short, vision)
            self._btn_group.addButton(btn)
            self._provider_btns[key] = btn
            btn.clicked.connect(lambda _, k=key: self._on_provider(k))
            pb_layout.addWidget(btn)

        none_btn = ProviderButton("", "None", "—", True)
        self._btn_group.addButton(none_btn)
        self._provider_btns[""] = none_btn
        none_btn.clicked.connect(lambda: self._on_provider(""))
        pb_layout.addWidget(none_btn)

        ai_layout.addWidget(providers_widget)

        # DeepSeek warning
        self._ds_warn = QFrame()
        self._ds_warn.setStyleSheet(f"""
            QFrame {{
                background: rgba(255,209,102,0.07);
                border: none;
                border-top: 1px solid rgba(255,209,102,0.25);
            }}
        """)
        ds_lay = QHBoxLayout(self._ds_warn)
        ds_lay.setContentsMargins(20, 12, 20, 12)
        ds_lbl = QLabel(
            "DeepSeek is text-only and cannot analyze images. "
            "It matches keywords in saved descriptions only."
        )
        ds_lbl.setStyleSheet(f"color: {YELLOW}; font-size: 12px; background: transparent;")
        ds_lbl.setWordWrap(True)
        ds_lay.addWidget(ds_lbl)
        self._ds_warn.hide()
        ai_layout.addWidget(self._ds_warn)

        # Enhancement note
        self._enhance_note = QFrame()
        self._enhance_note.setStyleSheet(f"""
            QFrame {{
                background: rgba(0,212,255,0.05);
                border: none;
                border-top: 1px solid rgba(0,212,255,0.15);
            }}
        """)
        en_lay = QHBoxLayout(self._enhance_note)
        en_lay.setContentsMargins(20, 12, 20, 12)
        en_lbl = QLabel(
            "Photo Enhancement is available for this provider (in AI Search). "
            "Generates richer descriptions for more accurate matching."
        )
        en_lbl.setStyleSheet(f"color: {ACCENT}; font-size: 12px; background: transparent;")
        en_lbl.setWordWrap(True)
        en_lay.addWidget(en_lbl)
        self._enhance_note.hide()
        ai_layout.addWidget(self._enhance_note)

        # URL hint
        self._url_frame = QFrame()
        self._url_frame.setStyleSheet(f"background: transparent; border: none; border-top: 1px solid {BORDER};")
        url_lay = QHBoxLayout(self._url_frame)
        url_lay.setContentsMargins(20, 10, 20, 10)
        self._url_lbl = QLabel("")
        self._url_lbl.setStyleSheet(f"color: {ACCENT}; font-size: 12px; font-family: '{FONT_MONO}'; background: transparent;")
        url_lay.addWidget(self._url_lbl)
        self._url_frame.hide()
        ai_layout.addWidget(self._url_frame)

        # API Key row
        key_divider = _divider()
        ai_layout.addWidget(key_divider)

        key_row = QWidget()
        key_row.setStyleSheet("background: transparent;")
        key_row.setMinimumHeight(72)
        kr_lay = QHBoxLayout(key_row)
        kr_lay.setContentsMargins(20, 16, 20, 16)
        kr_lay.setSpacing(20)

        ki_info = QVBoxLayout()
        ki_info.setSpacing(4)
        ki_info.addWidget(QLabel("API Key", styleSheet=f"color:{TEXT};font-size:13px;font-weight:700;background:transparent;"))
        ki_info.addWidget(QLabel(
            "Encrypted and stored locally. Never sent anywhere except your chosen AI provider.",
            styleSheet=f"color:{TEXT3};font-size:11px;background:transparent;"
        ))
        kr_lay.addLayout(ki_info)
        kr_lay.addStretch()

        # Key input
        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText("Paste your API key here")
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setMinimumWidth(260)
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
                letter-spacing: 2px;
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
        """)
        kr_lay.addWidget(self._key_input)

        # Show/hide toggle
        self._eye_btn = QPushButton("Show")
        self._eye_btn.setStyleSheet(btn_ghost())
        self._eye_btn.setMinimumSize(64, 42)
        self._eye_btn.clicked.connect(self._toggle_key_vis)
        kr_lay.addWidget(self._eye_btn)

        # Clear key button
        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {RED};
                border: 1px solid rgba(255,68,102,0.4);
                border-radius: {RADIUS_SM};
                font-size: 12px;
                font-weight: 600;
                padding: 0 14px;
                min-height: 42px;
                min-width: 64px;
            }}
            QPushButton:hover {{ background: rgba(255,68,102,0.1); border-color: {RED}; }}
        """)
        clear_btn.clicked.connect(self._clear_key)
        kr_lay.addWidget(clear_btn)

        # Test button
        test_btn = QPushButton("Test")
        test_btn.setStyleSheet(btn_ghost())
        test_btn.setMinimumSize(64, 42)
        test_btn.clicked.connect(self._test_api)
        kr_lay.addWidget(test_btn)

        ai_layout.addWidget(key_row)
        content.addWidget(ai_card)

        # ── CAPTURE card ──────────────────────────────────────────────────────
        cap_card = _section_card()
        cap_layout = QVBoxLayout(cap_card)
        cap_layout.setContentsMargins(0, 0, 0, 0)
        cap_layout.setSpacing(0)
        cap_layout.addWidget(_section_header("Capture Settings"))

        # Interval row
        self._interval = QSpinBox()
        self._interval.setRange(1, 300)
        self._interval.setValue(5)
        self._interval.setMinimumSize(100, 42)
        self._interval.setStyleSheet(f"""
            QSpinBox {{
                background: {BG3};
                color: {TEXT};
                border: 1px solid {BORDER2};
                border-radius: {RADIUS_SM};
                padding: 8px 8px 8px 14px;
                font-size: 13px;
            }}
            QSpinBox:focus {{ border-color: {ACCENT}; }}
            QSpinBox::up-button {{
                width: 22px;
                border: none;
                border-left: 1px solid {BORDER2};
                border-bottom: 1px solid {BORDER2};
                background: {BG3};
                border-radius: 0 {RADIUS_SM} 0 0;
            }}
            QSpinBox::down-button {{
                width: 22px;
                border: none;
                border-left: 1px solid {BORDER2};
                background: {BG3};
                border-radius: 0 0 {RADIUS_SM} 0;
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background: {SURFACE2};
            }}
            QSpinBox::up-arrow {{
                width: 8px; height: 8px;
            }}
            QSpinBox::down-arrow {{
                width: 8px; height: 8px;
            }}
        """)
        cap_layout.addWidget(_divider())
        cap_layout.addWidget(SettingsRow(
            "Capture Interval (seconds)",
            "How often to save a frame from each camera. Lower = more storage used.",
            self._interval
        ))

        # Retention row
        self._retention = QSpinBox()
        self._retention.setRange(0, 365)
        self._retention.setValue(30)
        self._retention.setMinimumSize(100, 42)
        self._retention.setStyleSheet(f"""
            QSpinBox {{
                background: {BG3};
                color: {TEXT};
                border: 1px solid {BORDER2};
                border-radius: {RADIUS_SM};
                padding: 8px 8px 8px 14px;
                font-size: 13px;
            }}
            QSpinBox:focus {{ border-color: {ACCENT}; }}
            QSpinBox::up-button {{
                width: 22px; border: none;
                border-left: 1px solid {BORDER2};
                border-bottom: 1px solid {BORDER2};
                background: {BG3};
            }}
            QSpinBox::down-button {{
                width: 22px; border: none;
                border-left: 1px solid {BORDER2};
                background: {BG3};
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background: {SURFACE2}; }}
            QSpinBox::up-arrow {{ width: 8px; height: 8px; }}
            QSpinBox::down-arrow {{ width: 8px; height: 8px; }}
        """)
        cap_layout.addWidget(_divider())
        cap_layout.addWidget(SettingsRow(
            "Auto-delete frames older than (days)",
            "Set to 0 to keep footage forever.",
            self._retention
        ))
        content.addWidget(cap_card)

        # ── MODERATION card ───────────────────────────────────────────────────
        mod_card = _section_card()
        mod_layout = QVBoxLayout(mod_card)
        mod_layout.setContentsMargins(0, 0, 0, 0)
        mod_layout.setSpacing(0)
        mod_layout.addWidget(_section_header("Moderation"))

        self._mod_pw = QLineEdit()
        self._mod_pw.setPlaceholderText("Set a strong master password")
        self._mod_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._mod_pw.setMinimumWidth(240)
        self._mod_pw.setMinimumHeight(42)
        self._mod_pw.setStyleSheet(f"""
            QLineEdit {{
                background: {BG3}; color: {TEXT};
                border: 1px solid {BORDER2}; border-radius: {RADIUS_SM};
                padding: 10px 14px; font-family: '{FONT_MONO}'; font-size: 13px;
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
        """)
        mod_layout.addWidget(_divider())
        mod_layout.addWidget(SettingsRow(
            "Master Moderator Password",
            "Gives owner-level access to approve/reject training submissions and generate keys.",
            self._mod_pw
        ))
        content.addWidget(mod_card)

        # ── APPROVAL KEYS card ────────────────────────────────────────────────
        ak_card = _section_card()
        ak_layout = QVBoxLayout(ak_card)
        ak_layout.setContentsMargins(0, 0, 0, 0)
        ak_layout.setSpacing(0)
        ak_layout.addWidget(_section_header("Approval Keys"))

        ak_row = QWidget()
        ak_row.setStyleSheet("background: transparent;")
        ak_row.setMinimumHeight(72)
        akr_lay = QHBoxLayout(ak_row)
        akr_lay.setContentsMargins(20, 16, 20, 16)
        akr_lay.setSpacing(20)

        ak_info = QVBoxLayout()
        ak_info.setSpacing(4)
        self._approval_lbl = QLabel("Not approved")
        self._approval_lbl.setStyleSheet(f"color:{TEXT};font-size:13px;font-weight:700;background:transparent;")
        ak_info.addWidget(self._approval_lbl)
        ak_info.addWidget(QLabel(
            "Generate one-time keys to give people approved access, or claim a key you received.",
            styleSheet=f"color:{TEXT3};font-size:11px;background:transparent;"
        ))
        akr_lay.addLayout(ak_info)
        akr_lay.addStretch()

        open_btn = QPushButton("Open Key Manager")
        open_btn.setStyleSheet(btn_primary())
        open_btn.setMinimumSize(160, 42)
        open_btn.clicked.connect(self._open_keys)
        akr_lay.addWidget(open_btn)

        ak_layout.addWidget(_divider())
        ak_layout.addWidget(ak_row)
        content.addWidget(ak_card)

        # ── PRIVACY card ──────────────────────────────────────────────────────
        priv_card = _section_card()
        priv_layout = QVBoxLayout(priv_card)
        priv_layout.setContentsMargins(20, 18, 20, 18)
        priv_layout.setSpacing(10)

        priv_title = QLabel("Privacy")
        priv_title.setStyleSheet(f"color:{TEXT};font-size:15px;font-weight:700;background:transparent;")
        priv_layout.addWidget(priv_title)

        for item in [
            "All footage is stored locally on your machine only.",
            "No video or images are uploaded anywhere by Fovea.",
            "Only individual frames are sent to your chosen AI provider when using AI search.",
            "Your API key is encrypted with AES-128 before being stored locally.",
            "Delete the Fovea folder in your home directory to remove all data.",
            "Fovea works on Windows 10/11, macOS, and Linux.",
        ]:
            # Single label with built-in dash — no wrapper widget = no border artifact
            lbl = QLabel(f"— {item}")
            lbl.setStyleSheet(f"""
                color: {TEXT2};
                font-size: 12px;
                padding: 2px 0;
            """)
            lbl.setWordWrap(True)
            priv_layout.addWidget(lbl)

        content.addWidget(priv_card)

        # ── Save button ───────────────────────────────────────────────────────
        save_row = QHBoxLayout()
        save_btn = QPushButton("Save Settings")
        save_btn.setStyleSheet(btn_primary())
        save_btn.setFixedHeight(42)
        save_btn.setMinimumWidth(160)
        save_btn.setMaximumWidth(220)
        save_btn.clicked.connect(self._save)
        save_row.addWidget(save_btn)
        save_row.addStretch()
        content.addLayout(save_row)
        content.addStretch()

        scroll.setWidget(container)
        root.addWidget(scroll)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _on_provider(self, key):
        for k, btn in self._provider_btns.items():
            btn.setChecked(k == key)
        self._ds_warn.setVisible(key == "deepseek")
        self._enhance_note.setVisible(key in ("openai", "gemini"))
        urls = {k: v[2] for k, v in PROVIDERS.items()}
        if key and key in urls:
            self._url_lbl.setText(f"Get your API key at:  {urls[key]}")
            self._url_frame.show()
        else:
            self._url_frame.hide()

    def _toggle_key_vis(self):
        if self._key_input.echoMode() == QLineEdit.EchoMode.Password:
            self._key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self._eye_btn.setText("Hide")
        else:
            self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self._eye_btn.setText("Show")

    def _clear_key(self):
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "Clear API Key",
            "Remove the saved API key? You will need to re-enter it to use AI search."
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._key_input.clear()
            from core.storage import set_secure_setting, set_setting
            set_secure_setting("ai_api_key", "")
            set_setting("ai_provider", "")
            for btn in self._provider_btns.values():
                btn.setChecked(False)
            self._on_provider("")
            self._refresh_ai_badge() if hasattr(self, "_refresh_ai_badge") else None

    def _load(self):
        provider = get_setting("ai_provider", "")
        for k, btn in self._provider_btns.items():
            btn.setChecked(k == provider)
        self._on_provider(provider)
        self._key_input.setText(get_secure_setting("ai_api_key", ""))
        self._interval.setValue(int(get_setting("capture_interval", 5)))
        self._retention.setValue(int(get_setting("retention_days", 30)))
        self._mod_pw.setText(get_setting("master_mod_password", ""))
        self._refresh_approval()

    def _refresh_approval(self):
        if is_machine_approved():
            self._approval_lbl.setText("This machine is approved")
            self._approval_lbl.setStyleSheet(
                f"color:{GREEN};font-size:13px;font-weight:700;background:transparent;"
            )
        else:
            self._approval_lbl.setText("Not approved — claim a key to get access")
            self._approval_lbl.setStyleSheet(
                f"color:{TEXT2};font-size:13px;font-weight:700;background:transparent;"
            )

    def _open_keys(self):
        dlg = ApprovalKeyDialog(self)
        dlg.exec()
        self._refresh_approval()

    def _save(self):
        selected = next((k for k, b in self._provider_btns.items() if b.isChecked()), "")
        try:
            set_setting("ai_provider", selected)
            set_secure_setting("ai_api_key", self._key_input.text().strip())
            set_setting("capture_interval", self._interval.value())
            set_setting("retention_days", self._retention.value())
            pw = self._mod_pw.text().strip()
            if pw:
                set_admin_password(pw)
                set_setting("master_mod_password", pw)  # kept for auto-login check
            # Flash "Saved!" on the button briefly instead of a popup
            orig_text = "Save Settings"
            self.sender().setText("Saved!")
            self.sender().setStyleSheet(f"""
                QPushButton {{
                    background: {GREEN};
                    color: #000;
                    border: none;
                    border-radius: {RADIUS_SM};
                    font-size: 13px;
                    font-weight: 800;
                    padding: 0 18px;
                    min-height: 42px;
                }}
            """)
            from PyQt6.QtCore import QTimer
            def _reset(btn=self.sender()):
                btn.setText(orig_text)
                btn.setStyleSheet(btn_primary())
            QTimer.singleShot(1800, _reset)
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", f"Could not save settings:\n{e}")

    def _test_api(self):
        import tempfile, os
        import numpy as np
        import cv2

        provider = next((k for k, b in self._provider_btns.items() if b.isChecked() and k), "")
        key = self._key_input.text().strip()

        if not provider or not key:
            QMessageBox.warning(self, "Missing",
                "Please select a provider and enter an API key first.")
            return

        try:
            set_setting("ai_provider", provider)
            set_secure_setting("ai_api_key", key)

            img = np.zeros((100, 100, 3), dtype=np.uint8)
            cv2.putText(img, "TEST", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 212, 255), 2)
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            cv2.imwrite(tmp.name, img)
            tmp.close()

            from core.ai_handler import describe_image
            result = describe_image(tmp.name)
            os.unlink(tmp.name)

            if result and not result.startswith("[AI Error"):
                QMessageBox.information(self, "Success",
                    f"API key works!\n\nAI response:\n{result[:300]}")
            else:
                QMessageBox.warning(self, "Failed",
                    f"API test failed:\n{result or 'No response received'}")
        except RuntimeError as e:
            QMessageBox.critical(self, "API Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Test error:\n{e}")