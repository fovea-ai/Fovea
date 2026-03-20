# =============================================================================
# training_page.py — Local AI Training System
# =============================================================================
#
# This page lets you build a local training dataset for AI.
#
# HOW IT WORKS:
#   1. Upload a photo and write a description of what's in it
#      Example: "Red Honda Civic, license plate partially visible, facing left"
#   2. As admin you can approve it instantly — no votes needed
#   3. Approved photos build up your local training dataset
#   4. Export the dataset as JSON to fine-tune a custom AI model
#
# WHY LOCAL?
#   Your training data stays on your machine. No servers, no internet,
#   no sharing with strangers. You control everything.
#
# TWO TRAINING MODES:
#   - Train for yourself only: upload, approve, export, use locally
#   - Get your own AI: export the JSON dataset and fine-tune a model
#     (e.g. via OpenAI fine-tuning, Google Vertex AI, or Hugging Face)
# =============================================================================

import os
import shutil
import json
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QDialog, QLineEdit, QTextEdit,
    QFileDialog, QMessageBox, QTabWidget, QApplication
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from ui.theme import *
from core.storage import (
    add_training_submission, get_submissions_for_moderation,
    get_approved_training_data, get_training_stats,
    moderate_submission, TRAINING_PATH,
    get_setting, set_setting, is_machine_approved, _get_machine_id
)


# =============================================================================
# Upload Dialog
# =============================================================================

class UploadDialog(QDialog):
    """Dialog for uploading a photo with a description."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Upload Training Photo")
        self.setMinimumWidth(520)
        self.setStyleSheet(f"""
            QDialog {{ background: {BG2}; border: none; }}
            QLabel  {{ color: {TEXT}; background: transparent; border: none; }}
        """)
        self._filepath = None
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setStyleSheet(f"background: {BG3}; border-bottom: 1px solid {BORDER};")
        hdr.setMinimumHeight(64)
        hl = QVBoxLayout(hdr)
        hl.setContentsMargins(24, 14, 24, 14)
        t = QLabel("Upload Training Photo")
        t.setStyleSheet(f"color: {TEXT}; font-size: 18px; font-weight: 800;")
        s = QLabel("Add a photo with a description to your local training dataset")
        s.setStyleSheet(f"color: {TEXT3}; font-size: 12px; font-family: '{FONT_MONO}';")
        hl.addWidget(t)
        hl.addWidget(s)
        lay.addWidget(hdr)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(24, 20, 24, 20)
        cl.setSpacing(14)

        # Photo picker
        self._preview = QLabel("Click to select a photo")
        self._preview.setMinimumHeight(160)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet(f"""
            background: {BG3};
            border: 2px dashed {BORDER2};
            border-radius: {RADIUS};
            color: {TEXT3};
            font-size: 13px;
        """)
        self._preview.setCursor(Qt.CursorShape.PointingHandCursor)
        self._preview.mousePressEvent = lambda e: self._pick_photo()
        cl.addWidget(self._preview)

        pick_btn = QPushButton("Choose Photo")
        pick_btn.setStyleSheet(btn_ghost())
        pick_btn.setMinimumHeight(38)
        pick_btn.clicked.connect(self._pick_photo)
        cl.addWidget(pick_btn)

        # Description
        desc_lbl = QLabel("Description")
        desc_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 12px; font-weight: 600; font-family: '{FONT_MONO}';")
        cl.addWidget(desc_lbl)

        self._desc = QTextEdit()
        self._desc.setMinimumHeight(100)
        self._desc.setPlaceholderText(
            "Describe everything in the photo:\n"
            "- Colors, make, model of vehicles\n"
            "- Clothing colors and description of people\n"
            "- Location, lighting, time of day\n"
            "Example: Red Honda Civic sedan facing left, white horizontal stripe on door panel, daytime"
        )
        self._desc.setStyleSheet(f"""
            QTextEdit {{
                background: {BG3};
                color: {TEXT};
                border: 1px solid {BORDER2};
                border-radius: {RADIUS_SM};
                padding: 10px;
                font-family: '{FONT_DISPLAY}';
                font-size: 13px;
            }}
            QTextEdit:focus {{ border-color: {ACCENT}; }}
        """)
        cl.addWidget(self._desc)

        # Submitted by
        name_lbl = QLabel("Your name  (optional)")
        name_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 12px; font-weight: 600; font-family: '{FONT_MONO}';")
        cl.addWidget(name_lbl)

        self._name = QLineEdit()
        self._name.setPlaceholderText("anonymous")
        self._name.setMinimumHeight(40)
        self._name.setStyleSheet(f"""
            QLineEdit {{
                background: {BG3}; color: {TEXT};
                border: 1px solid {BORDER2}; border-radius: {RADIUS_SM};
                padding: 8px 14px; font-size: 13px;
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
        """)
        cl.addWidget(self._name)

        # Buttons
        btns = QHBoxLayout()
        btns.setSpacing(10)
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(btn_ghost())
        cancel.setMinimumHeight(42)
        cancel.clicked.connect(self.reject)
        submit = QPushButton("Upload Photo")
        submit.setStyleSheet(btn_primary())
        submit.setMinimumHeight(42)
        submit.clicked.connect(self._submit)
        btns.addWidget(cancel)
        btns.addWidget(submit)
        cl.addLayout(btns)

        lay.addWidget(content)

    def _pick_photo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Photo", "",
            "Images (*.jpg *.jpeg *.png *.bmp *.webp)"
        )
        if not path:
            return
        self._filepath = path
        pix = QPixmap(path).scaled(
            460, 160,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self._preview.setPixmap(pix)

    def _submit(self):
        if not self._filepath:
            QMessageBox.warning(self, "Missing", "Please select a photo.")
            return
        desc = self._desc.toPlainText().strip()
        if len(desc) < 10:
            QMessageBox.warning(self, "Missing",
                "Please write a description of at least 10 characters.")
            return

        ext      = os.path.splitext(self._filepath)[1]
        new_name = datetime.now().strftime("sub_%Y%m%d_%H%M%S") + ext
        dest     = os.path.join(TRAINING_PATH, new_name)
        os.makedirs(TRAINING_PATH, exist_ok=True)
        shutil.copy2(self._filepath, dest)

        submitted_by = self._name.text().strip() or "anonymous"
        add_training_submission(dest, desc, submitted_by)
        self.accept()


# =============================================================================
# Submission Card (for moderation view)
# =============================================================================

class SubmissionCard(QWidget):
    def __init__(self, item, on_done, parent=None):
        super().__init__(parent)
        self.item    = item
        self.on_done = on_done
        self._build()

    def _build(self):
        sub_id, filepath, description, submitted_by, status, \
            v_yes, v_no, v_total, reports, created_at = self.item

        self.setStyleSheet(f"""
            QWidget {{
                background: {SURFACE};
                border: 1px solid {BORDER};
                border-radius: {RADIUS};
            }}
            QLabel {{ border: none; background: transparent; }}
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 14, 0)
        lay.setSpacing(14)

        # Thumbnail
        thumb = QLabel()
        thumb.setFixedSize(120, 100)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet(f"background: {BG3}; border-radius: {RADIUS} 0 0 {RADIUS}; color: {TEXT3}; font-size: 11px; border: none;")

        display_path = filepath
        if display_path and os.path.exists(display_path):
            pix = QPixmap(display_path).scaled(
                120, 100,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            thumb.setPixmap(pix)
        else:
            thumb.setText("No image")
        lay.addWidget(thumb)

        # Info
        info = QVBoxLayout()
        info.setSpacing(4)

        desc_lbl = QLabel(description[:120] + "..." if len(description) > 120 else description)
        desc_lbl.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 600;")
        desc_lbl.setWordWrap(True)

        meta = QLabel(f"by {submitted_by}  ·  {created_at[:16] if created_at else ''}  ·  Status: {status}")
        meta.setStyleSheet(f"color: {TEXT3}; font-size: 11px; font-family: '{FONT_MONO}';")

        info.addWidget(desc_lbl)
        info.addWidget(meta)
        info.addStretch()

        # Action buttons (only shown for pending)
        if status in ("pending_review", "flagged"):
            btn_row = QHBoxLayout()
            btn_row.setSpacing(8)

            approve_btn = QPushButton("Approve")
            approve_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {GREEN_DIM};
                    color: {GREEN};
                    border: 1px solid rgba(0,255,157,0.3);
                    border-radius: {RADIUS_SM};
                    font-size: 12px; font-weight: 700;
                    padding: 6px 16px; min-height: 32px;
                }}
                QPushButton:hover {{ background: rgba(0,255,157,0.15); }}
            """)
            approve_btn.clicked.connect(lambda: self._act("accept"))

            reject_btn = QPushButton("Reject")
            reject_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {RED};
                    border: 1px solid rgba(255,68,102,0.3);
                    border-radius: {RADIUS_SM};
                    font-size: 12px; font-weight: 700;
                    padding: 6px 16px; min-height: 32px;
                }}
                QPushButton:hover {{ background: rgba(255,68,102,0.08); }}
            """)
            reject_btn.clicked.connect(lambda: self._act("reject"))

            btn_row.addWidget(approve_btn)
            btn_row.addWidget(reject_btn)
            btn_row.addStretch()
            info.addLayout(btn_row)

        lay.addLayout(info)

    def _act(self, action):
        moderate_submission(self.item[0], action, "Owner")
        self.on_done()
        self.deleteLater()


# =============================================================================
# Training Page
# =============================================================================

class TrainingPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG}; border: none;")
        self._mod_label = "Owner" if get_setting("master_mod_password", "") else None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QHBoxLayout()

        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        title = QLabel("AI Training")
        title.setStyleSheet(f"color: {TEXT}; font-size: 22px; font-weight: 800; letter-spacing: -0.5px;")
        sub = QLabel(
            "Build a local dataset of photos and descriptions to train your own AI model."
        )
        sub.setStyleSheet(f"color: {TEXT2}; font-size: 12px;")
        title_col.addWidget(title)
        title_col.addWidget(sub)

        hdr.addLayout(title_col)
        hdr.addStretch()

        upload_btn = QPushButton("+ Upload Photo")
        upload_btn.setStyleSheet(btn_primary())
        upload_btn.setMinimumHeight(38)
        upload_btn.setMinimumWidth(140)
        upload_btn.clicked.connect(self._on_upload)
        hdr.addWidget(upload_btn)

        root.addLayout(hdr)
        root.addSpacing(20)

        # ── Stat cards ────────────────────────────────────────────────────────
        self._stats_layout = QHBoxLayout()
        self._stats_layout.setSpacing(12)
        root.addLayout(self._stats_layout)
        root.addSpacing(20)

        # ── Tabs ──────────────────────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                border-top: 1px solid {BORDER};
                background: transparent;
            }}
            QTabBar {{ border: none; }}
            QTabBar::tab {{
                background: transparent;
                color: {TEXT3};
                border: none;
                border-bottom: 2px solid transparent;
                padding: 10px 22px;
                font-size: 13px;
                font-weight: 600;
                font-family: '{FONT_DISPLAY}';
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                color: {ACCENT};
                border-bottom: 2px solid {ACCENT};
                font-weight: 700;
            }}
            QTabBar::tab:hover {{ color: {TEXT}; background: rgba(255,255,255,0.03); }}
        """)

        self._pending_tab   = self._make_scroll_tab()
        self._approved_tab  = self._make_scroll_tab()

        self._tabs.addTab(self._pending_tab["scroll"],  "Pending Review")
        self._tabs.addTab(self._approved_tab["scroll"], "Approved Dataset")
        self._tabs.currentChanged.connect(lambda _: self._refresh())

        root.addWidget(self._tabs)

        self._refresh()

    def _make_scroll_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: transparent; }} {SCROLLBAR}")
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(w)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.addStretch()
        scroll.setWidget(w)
        return {"scroll": scroll, "widget": w, "layout": layout}

    def _clear_tab(self, tab):
        layout = tab["layout"]
        while layout.count() > 1:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _refresh(self):
        self._refresh_stats()
        idx = self._tabs.currentIndex()
        if idx == 0:
            self._refresh_pending()
        elif idx == 1:
            self._refresh_approved()

    def _refresh_stats(self):
        while self._stats_layout.count():
            item = self._stats_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        stats = get_training_stats()
        items = [
            ("PENDING",  stats.get("pending_review", 0), TEXT2),
            ("APPROVED", stats.get("approved", 0),       GREEN),
            ("REJECTED", stats.get("rejected", 0),       RED),
        ]
        for label, val, color in items:
            card = QWidget()
            card.setStyleSheet(f"""
                QWidget {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; }}
                QLabel  {{ border: none; background: transparent; }}
            """)
            card.setMinimumWidth(120)
            card.setMinimumHeight(80)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(16, 14, 16, 14)
            cl.setSpacing(6)
            v = QLabel(str(val))
            v.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: 800;")
            l = QLabel(label)
            l.setStyleSheet(f"color: {TEXT3}; font-size: 9px; font-family: '{FONT_MONO}'; letter-spacing: 1.5px; font-weight: 600;")
            cl.addWidget(v)
            cl.addWidget(l)
            self._stats_layout.addWidget(card)
        self._stats_layout.addStretch()

    def _refresh_pending(self):
        self._clear_tab(self._pending_tab)
        items = get_submissions_for_moderation()

        if not items:
            lbl = QLabel("No submissions pending review.\nUpload a photo to get started.")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {TEXT3}; font-size: 14px; padding: 40px;")
            self._pending_tab["layout"].insertWidget(0, lbl)
            return

        for item in items:
            card = SubmissionCard(item, self._refresh)
            self._pending_tab["layout"].insertWidget(
                self._pending_tab["layout"].count() - 1, card
            )

    def _refresh_approved(self):
        self._clear_tab(self._approved_tab)

        # Export button at top
        export_row = QHBoxLayout()
        export_btn = QPushButton("Export Training Dataset (JSON)")
        export_btn.setStyleSheet(btn_primary())
        export_btn.setMinimumHeight(38)
        export_btn.clicked.connect(self._export_dataset)
        how_lbl = QLabel("Export your approved photos + descriptions as JSON to fine-tune your own AI model.")
        how_lbl.setStyleSheet(f"color: {TEXT3}; font-size: 11px;")
        export_row.addWidget(export_btn)
        export_row.addSpacing(16)
        export_row.addWidget(how_lbl)
        export_row.addStretch()

        export_widget = QWidget()
        export_widget.setStyleSheet("background: transparent; border: none;")
        ew_lay = QVBoxLayout(export_widget)
        ew_lay.setContentsMargins(0, 0, 0, 0)
        ew_lay.addLayout(export_row)
        self._approved_tab["layout"].insertWidget(0, export_widget)

        items = get_approved_training_data()
        if not items:
            lbl = QLabel("No approved items yet.\nApprove submissions from the Pending Review tab.")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {TEXT3}; font-size: 14px; padding: 40px;")
            self._approved_tab["layout"].insertWidget(1, lbl)
            return

        for item in items:
            sub_id, filepath, description, v_yes, v_no, v_total = item
            card = self._make_approved_card(filepath, description)
            self._approved_tab["layout"].insertWidget(
                self._approved_tab["layout"].count() - 1, card
            )

    def _make_approved_card(self, filepath, description):
        card = QWidget()
        card.setStyleSheet(f"""
            QWidget {{
                background: {SURFACE};
                border: 1px solid {BORDER};
                border-radius: {RADIUS};
            }}
            QLabel {{ border: none; background: transparent; }}
        """)
        card.setMinimumHeight(80)

        lay = QHBoxLayout(card)
        lay.setContentsMargins(0, 0, 14, 0)
        lay.setSpacing(14)

        # Thumb
        thumb = QLabel()
        thumb.setFixedSize(100, 80)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet(f"background: {BG3}; border-radius: {RADIUS} 0 0 {RADIUS}; border: none;")
        if filepath and os.path.exists(filepath):
            pix = QPixmap(filepath).scaled(100, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            thumb.setPixmap(pix)
        lay.addWidget(thumb)

        desc_lbl = QLabel(description[:140] + "..." if len(description) > 140 else description)
        desc_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 12px;")
        desc_lbl.setWordWrap(True)
        lay.addWidget(desc_lbl)

        tick = QLabel("Approved")
        tick.setStyleSheet(f"color: {GREEN}; font-size: 11px; font-family: '{FONT_MONO}'; font-weight: 700;")
        lay.addWidget(tick)

        return card

    def _on_upload(self):
        dlg = UploadDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            QMessageBox.information(
                self, "Uploaded",
                "Photo saved locally.\n\n"
                "Go to the Pending Review tab to approve it.\n"
                "Once approved it will appear in your training dataset."
            )
            self._refresh()

    def _export_dataset(self):
        items = get_approved_training_data()
        if not items:
            QMessageBox.warning(self, "Nothing to Export",
                "No approved items yet. Approve some submissions first.")
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Training Dataset", "fovea_training_dataset.json",
            "JSON Files (*.json)"
        )
        if not save_path:
            return

        dataset = []
        for sub_id, filepath, description, v_yes, v_no, v_total in items:
            dataset.append({
                "id":          sub_id,
                "description": description,
                "image_path":  filepath,
                "approved":    True,
            })

        with open(save_path, "w", encoding="utf-8") as f:
            json.dump({"version": "2.0", "count": len(dataset), "items": dataset}, f, indent=2)

        QMessageBox.information(
            self, "Exported",
            f"Exported {len(dataset)} approved training items to:\n{save_path}\n\n"
            "You can use this JSON file to fine-tune a custom AI model via:\n"
            "- OpenAI fine-tuning (platform.openai.com)\n"
            "- Google Vertex AI\n"
            "- Hugging Face"
        )