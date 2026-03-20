# =============================================================================
# terms_dialog.py — Terms of Use, Disclaimers & Privacy Policy Dialog
# =============================================================================
#
# This dialog is shown the FIRST TIME a user launches Fovea.
# They must read and check the box to proceed.
#
# WHY IS THIS IMPORTANT?
#   Fovea is a serious tool that deals with:
#   - Recording people (which has legal requirements in many countries)
#   - AI analysis (which is NOT always accurate)
#   - API costs (which can add up if searching large time ranges)
#
#   By presenting clear terms BEFORE the user can do anything, we:
#   1. Protect the author from liability for misuse
#   2. Educate users about their own legal responsibilities
#   3. Set accurate expectations about AI accuracy
#   4. Warn about API cost implications
#
# The terms are stored locally — once accepted on a machine, the dialog
# won't show again (tracked by machine ID in the database).
# =============================================================================

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QWidget, QCheckBox, QFrame
)
from PyQt6.QtCore import Qt
from ui.theme import *
from core.storage import accept_terms


class TermsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fovea — Terms of Use, Disclaimers & Privacy Policy")
        self.setMinimumSize(720, 680)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint)
        self.setStyleSheet(f"""
            QDialog {{ background: {BG}; border: none; }}
            QLabel  {{ color: {TEXT}; font-family: '{FONT_DISPLAY}'; background: transparent; border: none; }}
            QScrollArea {{ border: 1px solid {BORDER}; border-radius: 10px; background: {SURFACE}; }}
            QWidget {{ border: none; }}
        """)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(0)

        # Header
        title = QLabel("Terms of Use, Disclaimers & Privacy Policy")
        title.setStyleSheet(f"color: {TEXT}; font-size: 20px; font-weight: 800;")
        root.addWidget(title)
        root.addSpacing(4)

        sub = QLabel("Read all sections carefully before using Fovea.")
        sub.setStyleSheet(f"color: {TEXT3}; font-size: 12px; font-family: '{FONT_MONO}';")
        root.addWidget(sub)
        root.addSpacing(18)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        cw = QWidget()
        cw.setStyleSheet(f"background: {SURFACE};")
        cl = QVBoxLayout(cw)
        cl.setContentsMargins(24, 20, 24, 20)
        cl.setSpacing(20)

        sections = [
            (
                "1.  What Fovea Is",
                f"color: {ACCENT}",
                "Fovea is a free, open source desktop application that connects to cameras, "
                "captures footage locally, and uses AI to help search recorded frames. "
                "It was created by an individual developer with the sole intention of helping people "
                "— particularly for personal security, home monitoring, and safety purposes."
            ),
            (
                "2.  Open Source & Free to Use",
                f"color: {ACCENT}",
                "Fovea is released as open source software. You are free to use, modify, and "
                "distribute it under the terms of the open source license included with the software. "
                "The author does not charge for this software and does not profit from it. "
                "It is provided entirely as a community contribution."
            ),
            (
                "3.  AI Is NOT Always Accurate — IMPORTANT",
                f"color: {RED}",
                "Fovea uses third-party AI services (ChatGPT, Gemini, Claude, Grok, DeepSeek) "
                "to analyze camera footage. AI analysis is NOT always correct.\n\n"
                "Results may include:\n"
                "  - FALSE POSITIVES: The AI may flag footage that does not actually match your query\n"
                "  - FALSE NEGATIVES: The AI may miss footage that does match your query\n"
                "  - INACCURATE DESCRIPTIONS: The AI may misidentify people, objects, or vehicles\n\n"
                "Fovea results must NEVER be used as sole evidence in any legal, criminal, "
                "civil, or disciplinary proceeding. Always verify results manually by reviewing "
                "the actual footage. The author accepts NO responsibility for decisions made "
                "based on Fovea's AI output."
            ),
            (
                "4.  API Key Usage & Costs",
                f"color: {YELLOW}",
                "When you use an AI provider (ChatGPT, Gemini, Claude, Grok, or DeepSeek), "
                "Fovea sends individual camera frames to that provider's servers using "
                "your personal API key.\n\n"
                "IMPORTANT — API COSTS:\n"
                "  - Each frame analyzed costs API credits from your account\n"
                "  - Searching large time ranges across many cameras can send HUNDREDS or "
                "THOUSANDS of frames to the AI, potentially using significant API credits\n"
                "  - Photo Enhancement mode (ChatGPT/Gemini) uses MORE credits per frame\n"
                "  - You are solely responsible for monitoring your API usage and costs\n"
                "  - The author is NOT responsible for unexpected API charges\n\n"
                "Recommendation: Start with short time ranges (1-2 hours) to understand "
                "your usage before searching across days of footage."
            ),
            (
                "5.  Your Legal Responsibility for Recording",
                f"color: {YELLOW}",
                "Recording people on camera may be subject to laws in your country, state, "
                "or region. These laws vary significantly worldwide.\n\n"
                "In many places:\n"
                "  - You MUST notify people they are being recorded\n"
                "  - Recording in certain areas (bathrooms, bedrooms) may be illegal\n"
                "  - Recording public streets from private property may require a permit\n"
                "  - Storing footage for extended periods may be regulated\n\n"
                "YOU are solely responsible for ensuring your use of Fovea complies "
                "with all applicable local, national, and international laws. "
                "The author accepts NO legal responsibility for how this software is used."
            ),
            (
                "6.  No Warranty — Software Provided 'As-Is'",
                f"color: {TEXT2}",
                "Fovea is provided 'AS-IS' without any warranty of any kind, express or implied. "
                "This includes but is not limited to:\n"
                "  - No warranty that the software is free of bugs or errors\n"
                "  - No warranty that footage will be captured or preserved correctly\n"
                "  - No warranty that AI search results are accurate or complete\n"
                "  - No warranty of fitness for any particular purpose\n\n"
                "THE AUTHOR SHALL NOT BE LIABLE FOR ANY DAMAGES, LOSSES, OR CLAIMS arising "
                "from the use of this software, including but not limited to data loss, "
                "missed security events, incorrect AI results, or API charges."
            ),
            (
                "7.  Privacy & Data",
                f"color: {TEXT2}",
                "Fovea does NOT collect, transmit, or sell any personal data.\n\n"
                "  - All footage is stored locally on your device only\n"
                "  - Your API key is encrypted with AES-128 and stored locally\n"
                "  - When using AI search, only individual frame images are sent to your "
                "chosen AI provider — no audio, no metadata, no personal information\n"
                "  - A random machine ID is generated locally for the voting system only\n"
                "  - You can delete all Fovea data by removing the Fovea folder "
                "from your home directory\n\n"
                "The AI providers you choose (OpenAI, Google, Anthropic, xAI, DeepSeek) "
                "have their own privacy policies governing how they handle images sent to "
                "their APIs. Review their policies before use."
            ),
            (
                "8.  Community Training Feature",
                f"color: {TEXT2}",
                "Fovea includes an optional community AI training system where users may "
                "voluntarily upload photos with descriptions to help improve future AI accuracy.\n\n"
                "By submitting a photo you confirm:\n"
                "  - You have the legal right to share that image\n"
                "  - The image does not contain inappropriate, illegal, offensive, or private content\n"
                "  - You consent to the image being used for AI training purposes\n\n"
                "Submissions are reviewed by moderators before being shown to other users. "
                "Inappropriate content will be rejected. Repeated violations may result in "
                "permanent blocking from this feature."
            ),
            (
                "9.  Inappropriate Content Policy",
                f"color: {TEXT2}",
                "You must NOT use Fovea to:\n"
                "  - Record or surveil people without their legal consent\n"
                "  - Record in locations where recording is prohibited by law\n"
                "  - Harass, stalk, or monitor individuals without authorization\n"
                "  - Capture, store, or share footage of minors inappropriately\n"
                "  - Upload inappropriate, offensive, or illegal images to the training system\n\n"
                "The author condemns any misuse of this software and designed it exclusively "
                "to help people protect their own property and improve personal safety."
            ),
            (
                "10.  Acceptance",
                f"color: {TEXT2}",
                "By clicking 'I Agree and Accept' below, you acknowledge that you have read "
                "and understood all of the above terms, disclaimers, and policies. "
                "You agree to use Fovea responsibly, legally, and ethically.\n\n"
                "If you do not agree, click 'Decline' to exit the application."
            ),
        ]

        for heading, heading_style, body in sections:
            # Heading
            h = QLabel(heading)
            h.setStyleSheet(f"{heading_style}; font-size: 13px; font-weight: 700;")
            cl.addWidget(h)

            # Body
            b = QLabel(body)
            b.setStyleSheet(f"color: {TEXT2}; font-size: 12px; line-height: 1.6;")
            b.setWordWrap(True)
            cl.addWidget(b)

            # Divider between sections
            div = QFrame()
            div.setFixedHeight(1)
            div.setStyleSheet(f"background: {BORDER};")
            cl.addWidget(div)

        scroll.setWidget(cw)
        root.addWidget(scroll)
        root.addSpacing(16)

        # Checkbox
        self._checkbox = QCheckBox(
            "I have read and understood all Terms, Disclaimers, and Privacy Policies above"
        )
        self._checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {TEXT};
                font-size: 13px;
                font-weight: 600;
                spacing: 10px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {BORDER2};
                border-radius: 4px;
                background: {BG3};
            }}
            QCheckBox::indicator:checked {{
                background: {ACCENT};
                border-color: {ACCENT};
            }}
        """)
        self._checkbox.toggled.connect(self._on_toggle)
        root.addWidget(self._checkbox)
        root.addSpacing(14)

        # Buttons
        btn_row = QHBoxLayout()

        decline_btn = QPushButton("Decline & Exit")
        decline_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {RED};
                border: 1px solid rgba(255,68,102,0.4);
                border-radius: {RADIUS_SM};
                padding: 10px 24px;
                font-size: 13px;
                font-weight: 600;
                min-height: 40px;
            }}
            QPushButton:hover {{ background: rgba(255,68,102,0.1); }}
        """)
        decline_btn.clicked.connect(self._on_decline)

        self._accept_btn = QPushButton("I Agree and Accept — Continue")
        self._accept_btn.setEnabled(False)
        self._accept_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {ACCENT}, stop:1 #0099cc);
                color: #000;
                border: none;
                border-radius: {RADIUS_SM};
                padding: 10px 28px;
                font-size: 13px;
                font-weight: 800;
                min-height: 40px;
            }}
            QPushButton:disabled {{
                background: {SURFACE2};
                color: {TEXT3};
            }}
        """)
        self._accept_btn.clicked.connect(self._on_accept)

        btn_row.addWidget(decline_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._accept_btn)
        root.addLayout(btn_row)

    def _on_toggle(self, checked):
        self._accept_btn.setEnabled(checked)

    def _on_accept(self):
        accept_terms()
        self.accept()

    def _on_decline(self):
        self.reject()