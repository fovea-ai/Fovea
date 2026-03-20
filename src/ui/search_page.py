# =============================================================================
# search_page.py — AI Search Page
# =============================================================================
#
# This is the main feature of Fovea — searching footage by description.
#
# HOW SEARCH WORKS FOR THE USER (for beginners):
#   1. User types what they're looking for: "red car with white stripe"
#   2. User sets the time window: "last 24 hours"
#   3. User clicks Search
#   4. We find all frames in that time range from the database
#   5. We send each frame to the AI with the question
#   6. Matching frames appear as cards in the results grid
#   7. User can click "Extend" to see footage from after a match
#   8. User can export all results as a timeline
#
# PHOTO ENHANCEMENT:
#   Visible only for ChatGPT and Gemini users.
#   When enabled, asks the AI to describe each frame in maximum detail
#   BEFORE deciding if it matches. More accurate but uses 2x API credits.
#
# DISCLAIMER BANNER:
#   Always shown at the top of the search page to remind users that
#   AI results are not always accurate and must not be used as evidence.
# =============================================================================

import os
import shutil
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QLineEdit, QSpinBox, QComboBox,
    QDialog, QCheckBox, QFileDialog, QMessageBox, QProgressBar,
    QGridLayout
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap

from ui.theme import *
from core.storage import get_cameras, get_frames_in_range, get_setting
from core.search_worker import SearchWorker, TimelineExporter


DISCLAIMER = (
    "DISCLAIMER:  AI results are NOT always accurate and must never be used as "
    "sole evidence in any legal matter.  Results may contain false positives or miss "
    "relevant footage.  Large searches may use significant API credits — you are "
    "responsible for your own API costs.  Use this tool as an aid only."
)


class ControlGroup(QFrame):
    def __init__(self, label):
        super().__init__()
        self.setStyleSheet(f"QFrame{{background:{SURFACE};border:1px solid {BORDER};border-radius:{RADIUS_SM};}}")
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(10, 0, 12, 0)
        self._lay.setSpacing(8)
        self._lay.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.setFixedHeight(36)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color:{TEXT3};font-family:'{FONT_MONO}';font-size:10px;letter-spacing:1px;background:transparent;")
        self._lay.addWidget(lbl)
        div = QFrame()
        div.setFixedSize(1, 14)
        div.setStyleSheet(f"background:{BORDER2};")
        self._lay.addWidget(div)

    def add(self, w):
        self._lay.addWidget(w)

    @staticmethod
    def combo_style():
        return f"""
            QComboBox{{background:transparent;color:{TEXT};border:none;
            font-family:'{FONT_DISPLAY}';font-size:13px;font-weight:700;padding:0;}}
            QComboBox::drop-down{{border:none;}}
            QComboBox QAbstractItemView{{background:{BG2};color:{TEXT};
            border:1px solid {BORDER2};selection-background-color:{ACCENT};selection-color:#000;}}
        """

    @staticmethod
    def spin_style():
        return f"""
            QSpinBox{{background:transparent;color:{ACCENT};border:none;
            font-family:'{FONT_MONO}';font-size:14px;font-weight:600;padding:0;width:44px;}}
            QSpinBox::up-button,QSpinBox::down-button{{width:0;border:none;}}
        """


class ResultCard(QFrame):
    extend_requested = pyqtSignal(dict)

    def __init__(self, result):
        super().__init__()
        self.result = result
        self._build()

    def _build(self):
        self.setFixedHeight(190)
        self.setStyleSheet(f"""
            QFrame{{background:{SURFACE};border:1px solid {BORDER};border-radius:{RADIUS};}}
            QFrame:hover{{border-color:{ACCENT};}}
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Thumbnail
        thumb = QLabel()
        thumb.setFixedHeight(105)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet(f"background:{BG3};border-radius:{RADIUS} {RADIUS} 0 0;")
        fp = self.result.get("filepath", "")
        if os.path.exists(fp):
            pix = QPixmap(fp).scaled(999, 105,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation)
            thumb.setPixmap(pix)
        else:
            thumb.setText("📷  No image")
            thumb.setStyleSheet(f"background:{BG3};border-radius:{RADIUS} {RADIUS} 0 0;color:{TEXT3};font-size:12px;")
        lay.addWidget(thumb)

        body = QWidget()
        body.setStyleSheet("background:transparent;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(12, 8, 12, 8)
        bl.setSpacing(3)

        # Camera + time
        meta_row = QHBoxLayout()
        cam_lbl = QLabel(self.result.get("camera_name", "?"))
        cam_lbl.setStyleSheet(f"color:{ACCENT};font-size:10px;font-weight:700;font-family:'{FONT_MONO}';background:transparent;")
        time_lbl = QLabel(self.result.get("timestamp", ""))
        time_lbl.setStyleSheet(f"color:{TEXT3};font-size:10px;font-family:'{FONT_MONO}';background:transparent;")
        meta_row.addWidget(cam_lbl)
        meta_row.addStretch()
        meta_row.addWidget(time_lbl)
        bl.addLayout(meta_row)

        desc = self.result.get("description") or "Match found"
        dl = QLabel(desc[:100] + ("…" if len(desc) > 100 else ""))
        dl.setStyleSheet(f"color:{TEXT2};font-size:11px;background:transparent;")
        dl.setWordWrap(True)
        bl.addWidget(dl)
        bl.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        ext = QPushButton("＋ Extend")
        ext.setStyleSheet(f"""
            QPushButton{{background:transparent;color:{TEXT2};border:1px solid {BORDER};
            border-radius:5px;font-size:11px;font-weight:700;padding:4px 8px;font-family:'{FONT_DISPLAY}';}}
            QPushButton:hover{{border-color:{ACCENT};color:{ACCENT};background:{ACCENT_DIM};}}
        """)
        ext.clicked.connect(lambda: self.extend_requested.emit(self.result))
        view = QPushButton("View")
        view.setStyleSheet(f"""
            QPushButton{{background:{ACCENT};color:#000;border:none;border-radius:5px;
            font-size:11px;font-weight:700;padding:4px 8px;font-family:'{FONT_DISPLAY}';}}
            QPushButton:hover{{background:#33ddff;}}
        """)
        btn_row.addWidget(ext)
        btn_row.addWidget(view)
        bl.addLayout(btn_row)
        lay.addWidget(body)


class SearchPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{BG};")
        self._worker   = None
        self._exporter = None
        self._results  = []
        self._result_count = 0
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top search panel ──────────────────────────────────────────────────
        top = QWidget()
        top.setStyleSheet(f"background:{BG};border-bottom:1px solid {BORDER};")
        tl = QVBoxLayout(top)
        tl.setContentsMargins(24, 20, 24, 14)
        tl.setSpacing(0)

        heading = QLabel("AI Search")
        heading.setStyleSheet(f"color:{TEXT};font-size:22px;font-weight:800;letter-spacing:-0.5px;")
        tl.addWidget(heading)
        sub = QLabel("Describe what you're looking for — the AI will find it across all your cameras")
        sub.setStyleSheet(f"color:{TEXT3};font-family:'{FONT_MONO}';font-size:11px;margin-bottom:2px;")
        tl.addWidget(sub)
        tl.addSpacing(14)

        # Disclaimer banner
        disc = QFrame()
        disc.setStyleSheet(f"background:rgba(255,209,102,0.06);border:1px solid rgba(255,209,102,0.2);border-radius:{RADIUS_SM};")
        dl = QHBoxLayout(disc)
        dl.setContentsMargins(12, 8, 12, 8)
        dlbl = QLabel(DISCLAIMER)
        dlbl.setStyleSheet(f"color:{YELLOW};font-size:10px;font-family:'{FONT_MONO}';background:transparent;")
        dlbl.setWordWrap(True)
        dl.addWidget(dlbl)
        tl.addWidget(disc)
        tl.addSpacing(12)

        # Search bar
        sr = QHBoxLayout()
        sr.setSpacing(10)
        self._query = QLineEdit()
        self._query.setPlaceholderText('e.g. "a red car with a white stripe"')
        self._query.setFixedHeight(46)
        self._query.setMinimumHeight(46)
        self._query.setStyleSheet(f"""
            QLineEdit{{background:{SURFACE};color:{TEXT};border:1px solid {BORDER2};
            border-radius:{RADIUS};padding:12px 16px;font-family:'{FONT_DISPLAY}';font-size:14px;}}
            QLineEdit:focus{{border-color:{ACCENT};}}
            QLineEdit::placeholder{{color:{TEXT3};}}
        """)
        self._query.returnPressed.connect(self._run_search)

        self._search_btn = QPushButton("Search")
        self._search_btn.setStyleSheet(btn_primary())
        self._search_btn.setMinimumWidth(100)
        self._search_btn.setMinimumHeight(46)
        self._search_btn.setMaximumHeight(46)
        self._search_btn.clicked.connect(self._run_search)
        sr.addWidget(self._query)
        sr.addWidget(self._search_btn)
        tl.addLayout(sr)
        tl.addSpacing(12)

        # Controls row
        cr = QHBoxLayout()
        cr.setSpacing(10)
        cr.setAlignment(Qt.AlignmentFlag.AlignLeft)

        lb = ControlGroup("LOOK BACK")
        self._time_val = QSpinBox()
        self._time_val.setRange(1, 9999)
        self._time_val.setValue(24)
        self._time_val.setStyleSheet(ControlGroup.spin_style())
        self._time_val.setFixedWidth(48)
        self._time_unit = QComboBox()
        self._time_unit.addItems(["Minutes", "Hours", "Days"])
        self._time_unit.setCurrentIndex(1)
        self._time_unit.setStyleSheet(ControlGroup.combo_style())
        lb.add(self._time_val)
        lb.add(self._time_unit)
        cr.addWidget(lb)

        cc = ControlGroup("CAMERA")
        self._cam_combo = QComboBox()
        self._cam_combo.addItem("All Cameras", None)
        for cam in get_cameras():
            self._cam_combo.addItem(cam[1], cam[0])
        self._cam_combo.setStyleSheet(ControlGroup.combo_style())
        cc.add(self._cam_combo)
        cr.addWidget(cc)

        # Enhancement toggle (GPT/Gemini only)
        self._enhance_check = QCheckBox("Photo Enhancement")
        self._enhance_check.setStyleSheet(f"""
            QCheckBox{{color:{TEXT2};font-size:12px;font-weight:600;background:transparent;}}
            QCheckBox::indicator{{width:16px;height:16px;border:2px solid {BORDER2};border-radius:3px;background:transparent;}}
            QCheckBox::indicator:checked{{background:{ACCENT};border-color:{ACCENT};}}
        """)
        self._enhance_check.setToolTip(
            "Photo Enhancement: Ask AI to describe each frame in maximum detail before matching.\n"
            "Available for ChatGPT and Gemini only. Slower but more accurate."
        )
        cr.addWidget(self._enhance_check)
        cr.addStretch()

        # Export timeline button
        self._export_btn = QPushButton("⬇ Export Timeline")
        self._export_btn.setStyleSheet(btn_ghost())
        self._export_btn.setFixedHeight(36)
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._export_timeline)
        cr.addWidget(self._export_btn)

        tl.addLayout(cr)
        root.addWidget(top)

        # ── Status bar ────────────────────────────────────────────────────────
        sb = QFrame()
        sb.setFixedHeight(34)
        sb.setStyleSheet(f"background:{BG2};border-bottom:1px solid {BORDER};")
        sbl = QHBoxLayout(sb)
        sbl.setContentsMargins(24, 0, 24, 0)
        self._status_lbl = QLabel("Ready to search")
        self._status_lbl.setStyleSheet(f"color:{TEXT3};font-family:'{FONT_MONO}';font-size:11px;")
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(f"color:{TEXT3};font-family:'{FONT_MONO}';font-size:11px;")
        sbl.addWidget(self._status_lbl)
        sbl.addStretch()
        sbl.addWidget(self._count_lbl)
        root.addWidget(sb)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setFixedHeight(3)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet(f"""
            QProgressBar{{background:{BG2};border:none;border-radius:0;}}
            QProgressBar::chunk{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {ACCENT},stop:1 #7b2fff);}}
        """)
        self._progress.hide()
        root.addWidget(self._progress)

        # ── Results ───────────────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea{{border:none;background:{BG};}}{SCROLLBAR}")

        self._results_container = QWidget()
        self._results_container.setStyleSheet(f"background:{BG};")
        self._results_layout = QVBoxLayout(self._results_container)
        self._results_layout.setContentsMargins(24, 20, 24, 24)
        self._results_layout.setSpacing(0)

        # Empty state
        self._empty = QWidget()
        el = QVBoxLayout(self._empty)
        el.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.setSpacing(10)
        _ic=QLabel("🔍")
        _ic.setStyleSheet("font-size:48px;")
        _ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(_ic)
        el.addWidget(QLabel("Search your footage",
            styleSheet=f"color:{TEXT2};font-size:16px;font-weight:700;",
            alignment=Qt.AlignmentFlag.AlignCenter))
        es = QLabel("Describe what you're looking for.\nFovea searches across all cameras simultaneously.")
        es.setStyleSheet(f"color:{TEXT3};font-size:12px;")
        es.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(es)

        # Example chips
        chips_w = QWidget()
        chips_w.setStyleSheet("background:transparent;")
        chips_l = QHBoxLayout(chips_w)
        chips_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chips_l.setSpacing(8)
        for ex in ['"red car with white stripe"', '"person in blue jacket"', '"white van parked"']:
            ch = QPushButton(ex)
            ch.setStyleSheet(f"""
                QPushButton{{background:{ACCENT_DIM};color:{ACCENT};border:1px solid {ACCENT};
                border-radius:4px;font-family:'{FONT_MONO}';font-size:11px;padding:4px 10px;}}
                QPushButton:hover{{background:rgba(0,212,255,0.15);}}
            """)
            ch.clicked.connect(lambda _, e=ex: self._fill(e))
            chips_l.addWidget(ch)
        el.addWidget(chips_w)
        self._results_layout.addWidget(self._empty)

        self._grid_w = QWidget()
        self._grid_w.setStyleSheet("background:transparent;")
        self._grid = QGridLayout(self._grid_w)
        self._grid.setSpacing(14)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._grid_w.hide()
        self._results_layout.addWidget(self._grid_w)
        self._results_layout.addStretch()

        scroll.setWidget(self._results_container)
        root.addWidget(scroll)

        self._update_enhance_visibility()

    def _update_enhance_visibility(self):
        provider = get_setting("ai_provider", "")
        can = provider in ("openai", "gemini")
        self._enhance_check.setVisible(can)
        if not can:
            self._enhance_check.setChecked(False)

    def _fill(self, text):
        self._query.setText(text.strip('"'))
        self._run_search()

    def _get_hours(self):
        v = self._time_val.value()
        u = self._time_unit.currentText()
        if u == "Minutes": return v / 60
        if u == "Hours":   return v
        return v * 24

    def _run_search(self):
        query = self._query.text().strip()
        if not query:
            return

        if self._worker and self._worker.isRunning():
            self._worker.stop()

        # Clear grid
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._results.clear()
        self._result_count = 0
        self._export_btn.setEnabled(False)

        self._empty.hide()
        self._grid_w.show()
        self._search_btn.setEnabled(False)
        self._search_btn.setText("…")
        self._progress.setRange(0, 0)
        self._progress.show()

        cam_id = self._cam_combo.currentData()
        self._update_enhance_visibility()

        self._worker = SearchWorker(
            query, self._get_hours(),
            [cam_id] if cam_id else None,
            use_enhancement=self._enhance_check.isChecked()
        )
        self._worker.result_found.connect(self._on_result)
        self._worker.progress.connect(self._on_progress)
        self._worker.status.connect(lambda m: self._status_lbl.setText(m))
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

        # Update the mode indicator pill to show what search method is active
        from core.storage import get_setting, get_secure_setting
        provider = get_setting("ai_provider", "")
        api_key  = get_secure_setting("ai_api_key", "")
        if provider and api_key:
            names = {"openai":"ChatGPT","gemini":"Gemini","claude":"Claude",
                     "deepseek":"DeepSeek","grok":"Grok"}
            self._mode_lbl.setText(f"AI: {names.get(provider, provider)}")
            self._mode_lbl.setStyleSheet(f"""
                color: {ACCENT}; font-family: '{FONT_MONO}'; font-size: 10px;
                background: {ACCENT_DIM}; border: 1px solid {ACCENT};
                border-radius: {RADIUS_SM}; padding: 4px 10px;
            """)
        else:
            self._mode_lbl.setText("Local Vision")
            self._mode_lbl.setStyleSheet(f"""
                color: {GREEN}; font-family: '{FONT_MONO}'; font-size: 10px;
                background: {GREEN_DIM}; border: 1px solid rgba(0,255,157,0.3);
                border-radius: {RADIUS_SM}; padding: 4px 10px;
            """)

    def _on_result(self, result):
        self._results.append(result)
        card = ResultCard(result)
        card.extend_requested.connect(self._on_extend)
        row, col = divmod(self._result_count, 3)
        self._grid.addWidget(card, row, col)
        self._result_count += 1
        self._count_lbl.setText(f"{self._result_count} match{'es' if self._result_count != 1 else ''} found")

    def _on_progress(self, current, total):
        self._progress.setRange(0, total)
        self._progress.setValue(current)

    def _on_error(self, msg):
        self._status_lbl.setText(f"⚠ {msg}")

    def _on_finished(self, count):
        self._progress.hide()
        self._search_btn.setEnabled(True)
        self._search_btn.setText("Search")
        if count == 0:
            self._empty.show()
            self._grid_w.hide()
            self._status_lbl.setText("No matches found. Try a different query or expand the time range.")
        else:
            self._export_btn.setEnabled(True)
            self._status_lbl.setText(f"Done — {count} match{'es' if count != 1 else ''}")

    def _on_extend(self, result):
        dlg = _ExtendDialog(result, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            mins = dlg.get_minutes()
            try:
                base   = datetime.strptime(result["timestamp"], "%Y-%m-%d %H:%M:%S")
                end    = base + timedelta(minutes=mins)
                frames = get_frames_in_range(
                    result["camera_id"],
                    result["timestamp"],
                    end.strftime("%Y-%m-%d %H:%M:%S")
                )
                for fid, fp, ts, desc in frames:
                    fake = {**result, "filepath": fp, "timestamp": ts,
                            "description": desc or "Extended footage frame",
                            "camera_name": result["camera_name"] + " [+EXT]"}
                    self._on_result(fake)
                self._status_lbl.setText(
                    f"Extended +{mins} min — {len(frames)} additional frames"
                )
            except Exception as e:
                self._status_lbl.setText(f"Extend error: {e}")

    def _export_timeline(self):
        if not self._results:
            return
        folder = QFileDialog.getExistingDirectory(self, "Choose Export Folder")
        if not folder:
            return

        self._export_btn.setEnabled(False)
        self._export_btn.setText("Exporting…")

        self._exporter = TimelineExporter(self._results, folder)
        self._exporter.progress.connect(lambda c, t: self._status_lbl.setText(f"Exporting {c}/{t}…"))
        self._exporter.finished.connect(self._on_export_done)
        self._exporter.error.connect(self._on_export_error)
        self._exporter.start()

    def _on_export_done(self, path):
        self._export_btn.setEnabled(True)
        self._export_btn.setText("⬇ Export Timeline")
        QMessageBox.information(self, "Export Complete",
            f"Timeline exported to:\n{path}\n\n"
            "Contains all matched frames in chronological order "
            "plus a timeline.txt summary.")

    def _on_export_error(self, msg):
        self._export_btn.setEnabled(True)
        self._export_btn.setText("⬇ Export Timeline")
        QMessageBox.critical(self, "Export Failed", msg)


class _ExtendDialog(QDialog):
    def __init__(self, result, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Extend Search")
        self.setFixedSize(400, 230)
        self.setStyleSheet(f"QDialog{{background:{BG2};}} QLabel{{color:{TEXT};}}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(14)

        lay.addWidget(QLabel("View Extended Footage",
            styleSheet=f"color:{TEXT};font-size:16px;font-weight:800;"))
        sub = QLabel(f"How long after  {result.get('timestamp','')}  to show?")
        sub.setStyleSheet(f"color:{TEXT2};font-size:12px;")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        row = QHBoxLayout()
        self._amount = QSpinBox()
        self._amount.setRange(1, 999)
        self._amount.setValue(30)
        self._amount.setStyleSheet(input_style())
        self._amount.setFixedWidth(80)
        self._unit = QComboBox()
        self._unit.addItems(["Minutes", "Hours", "Days"])
        self._unit.setStyleSheet(input_style())
        row.addWidget(self._amount)
        row.addWidget(self._unit)
        row.addStretch()
        lay.addLayout(row)

        go = QPushButton("View Footage")
        go.setStyleSheet(btn_primary())
        go.clicked.connect(self.accept)
        lay.addWidget(go)

    def get_minutes(self):
        v = self._amount.value()
        u = self._unit.currentText()
        return v if u == "Minutes" else v * 60 if u == "Hours" else v * 1440
