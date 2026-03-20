# =============================================================================
# main_window.py — Main Application Window
# =============================================================================
#
# This is the "skeleton" of the whole app. It creates:
#   - The TOP BAR (logo, status pill, alerts button)
#   - The SIDEBAR (camera list, navigation, AI badge)
#   - The PAGE STACK (switches between Dashboard, Cameras, Search, etc.)
#
# HOW NAVIGATION WORKS (for beginners):
#   We use a QStackedWidget — imagine a deck of cards where only one card
#   is visible at a time. When you click "AI Search" in the sidebar,
#   we just flip to the search card. All pages are always in memory.
#
# SIGNALS & SLOTS PATTERN:
#   In PyQt6, UI events (like button clicks) use "signals" and "slots".
#   A signal is like a notification: "something happened".
#   A slot is a function that responds to that notification.
#   Example: btn.clicked.connect(self._on_click)
#     "clicked" is the signal, "_on_click" is the slot.
#
# CAMERA LIST:
#   Refreshed every 5 seconds by a QTimer, but only rebuilt if the
#   number of cameras changed (optimization to avoid flickering).
# =============================================================================

import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame,
    QScrollArea, QSizePolicy, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from ui.theme import *
from ui.dashboard import DashboardPage
from ui.cameras_page import CamerasPage
from ui.search_page import SearchPage
from ui.settings_page import SettingsPage
from ui.training_page import TrainingPage
from ui.terms_dialog import TermsDialog
from ui.voting_popup import VotingPopup
from core.storage import (
    init_db, has_accepted_terms, get_cameras,
    get_setting, get_unseen_alerts, mark_alerts_seen
)

SIDEBAR_W = 220
TOPBAR_H  = 52


class NavItem(QPushButton):
    def __init__(self, icon, label):
        super().__init__()
        self.setText(f"  {icon}   {label}")
        self.setCheckable(True)
        self.setFixedHeight(40)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply(False)

    def _apply(self, active):
        if active:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {ACCENT_DIM};
                    border: none;
                    border-left: 3px solid {ACCENT};
                    border-radius: 0;
                    color: {ACCENT};
                    text-align: left;
                    padding: 0 0 0 16px;
                    font-family: '{FONT_DISPLAY}';
                    font-size: 13px;
                    font-weight: 700;
                    outline: none;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    border-left: 3px solid transparent;
                    border-radius: 0;
                    color: {TEXT2};
                    text-align: left;
                    padding: 0 0 0 16px;
                    font-family: '{FONT_DISPLAY}';
                    font-size: 13px;
                    font-weight: 500;
                    outline: none;
                }}
                QPushButton:hover {{
                    color: {TEXT};
                    background: rgba(255,255,255,0.04);
                    border-left: 3px solid {BORDER2};
                }}
            """)

    def setChecked(self, v):
        super().setChecked(v)
        self._apply(v)


class CameraListItem(QFrame):
    def __init__(self, name, source, cam_type, on_click=None):
        super().__init__()
        self.setFixedHeight(46)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._on_click = on_click
        self.setStyleSheet(f"""
            QFrame {{ background: transparent; border: 1px solid transparent; border-radius: {RADIUS_SM}; }}
            QFrame:hover {{ background: {SURFACE}; border-color: {BORDER}; }}
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(8)

        thumb = QLabel("CAM")
        thumb.setFixedSize(34, 24)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet(f"background: {SURFACE2}; border: 1px solid {BORDER2}; border-radius: 3px; font-size: 9px; font-weight: 700; color: {ACCENT};")
        lay.addWidget(thumb)

        info = QVBoxLayout()
        info.setSpacing(1)
        nl = QLabel(name)
        nl.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: 700; background: transparent;")
        sl = QLabel((cam_type.upper() + " · " + source)[:28])
        sl.setStyleSheet(f"color: {TEXT3}; font-size: 10px; font-family: '{FONT_MONO}'; background: transparent;")
        info.addWidget(nl)
        info.addWidget(sl)
        lay.addLayout(info)
        lay.addStretch()

        self._dot = QLabel("●")
        self._dot.setStyleSheet(f"color: {TEXT3}; font-size: 9px; background: transparent;")
        lay.addWidget(self._dot)

    def mousePressEvent(self, e):
        if self._on_click:
            self._on_click()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        init_db()
        self.setWindowTitle("Fovea  —  AI Camera Intelligence")
        self.setMinimumSize(1100, 680)
        self._build_ui()
        self._nav_items[0].setChecked(True)
        QTimer.singleShot(300, self._check_terms_and_voting)

        # Alert poll
        self._alert_timer = QTimer(self)
        self._alert_timer.timeout.connect(self._poll_alerts)
        self._alert_timer.start(3000)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.setStyleSheet(f"background: {BG}; color: {TEXT}; font-family: '{FONT_DISPLAY}';")
        cw = QWidget()
        self.setCentralWidget(cw)
        root = QVBoxLayout(cw)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_topbar())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())

        div = QFrame()
        div.setFixedWidth(1)
        div.setStyleSheet(f"background: {BORDER};")
        body.addWidget(div)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background: {BG};")

        self._page_dashboard = DashboardPage(self)
        self._page_cameras   = CamerasPage(self)
        self._page_search    = SearchPage(self)
        self._page_training  = TrainingPage(self)
        self._page_settings  = SettingsPage(self)

        for p in [self._page_dashboard, self._page_cameras,
                  self._page_search, self._page_training, self._page_settings]:
            self._stack.addWidget(p)

        body.addWidget(self._stack)
        bw = QWidget()
        bw.setLayout(body)
        root.addWidget(bw)

    def _build_topbar(self):
        bar = QFrame()
        bar.setFixedHeight(TOPBAR_H)
        bar.setStyleSheet(f"background: {BG2}; border-bottom: 1px solid {BORDER};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(12)

        logo_icon = QLabel("FV")
        logo_icon.setFixedSize(28, 28)
        logo_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_icon.setStyleSheet(f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {ACCENT},stop:1 {ACCENT2}); border-radius: 8px; font-size: 11px; font-weight: 900; color: #000; border: none;")
        logo_text = QLabel(f"<span style='color:{TEXT};font-weight:800;'>Fo</span><span style='color:{ACCENT};font-weight:800;'>vea</span>")
        logo_text.setTextFormat(Qt.TextFormat.RichText)
        logo_text.setStyleSheet(f"color: {TEXT}; font-size: 16px; font-weight: 800; letter-spacing: -0.5px;")
        lay.addWidget(logo_icon)
        lay.addWidget(logo_text)
        lay.addStretch()

        # Status pill
        pill = QWidget()
        pill.setStyleSheet(
            f"QWidget {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; }}"
            f"QLabel {{ border: none; background: transparent; }}"
        )
        pl = QHBoxLayout(pill)
        pl.setContentsMargins(10, 4, 14, 4)
        pl.setSpacing(7)
        self._status_dot  = QLabel("●")
        self._status_dot.setStyleSheet(f"color: {TEXT3}; font-size: 9px;")
        self._status_text = QLabel("Ready")
        self._status_text.setStyleSheet(f"color: {TEXT2}; font-size: 11px; font-family: '{FONT_MONO}';")
        pl.addWidget(self._status_dot)
        pl.addWidget(self._status_text)
        lay.addWidget(pill)
        lay.addStretch()

        # Alert bell — plain text, never squishes
        self._alert_btn = QPushButton("Alerts")
        self._alert_btn.setFixedHeight(32)
        self._alert_btn.setMinimumWidth(72)
        self._alert_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {BORDER};
                border-radius: {RADIUS_SM};
                color: {TEXT2};
                font-size: 12px;
                font-weight: 600;
                padding: 0 14px;
            }}
            QPushButton:hover {{ border-color: {ACCENT}; color: {ACCENT}; background: {ACCENT_DIM}; }}
        """)
        self._alert_btn.clicked.connect(self._show_alerts)
        lay.addWidget(self._alert_btn)

        return bar

    def _build_sidebar(self):
        sb = QFrame()
        sb.setFixedWidth(SIDEBAR_W)
        sb.setStyleSheet(f"background: {BG2}; border: none; border-right: 1px solid {BORDER};")
        lay = QVBoxLayout(sb)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Camera header
        ch = QWidget()
        ch.setFixedHeight(36)
        ch.setStyleSheet(
            f"QWidget {{ background: transparent; border-bottom: 1px solid {BORDER}; }}"
            f"QLabel {{ border: none; background: transparent; }}"
        )
        chl = QHBoxLayout(ch)
        chl.setContentsMargins(14, 0, 14, 0)
        cam_lbl = QLabel("CAMERAS")
        cam_lbl.setStyleSheet(
            f"color: {TEXT3}; font-family: '{FONT_MONO}'; font-size: 9px; "
            f"letter-spacing: 2px; font-weight: 600; border: none; background: transparent;"
        )
        chl.addWidget(cam_lbl)
        lay.addWidget(ch)

        self._cam_scroll_widget = QWidget()
        self._cam_scroll_widget.setStyleSheet("background: transparent;")
        self._cam_list_layout = QVBoxLayout(self._cam_scroll_widget)
        self._cam_list_layout.setContentsMargins(8, 6, 8, 6)
        self._cam_list_layout.setSpacing(2)
        self._cam_list_layout.addStretch()

        cs = QScrollArea()
        cs.setWidget(self._cam_scroll_widget)
        cs.setWidgetResizable(True)
        cs.setFixedHeight(155)
        cs.setStyleSheet(f"QScrollArea{{border:none;background:transparent;}}{SCROLLBAR}")
        cs.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lay.addWidget(cs)

        add_cam = QPushButton("＋  Add Camera")
        add_cam.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT3};
                border: 1px dashed {BORDER2}; border-radius: {RADIUS_SM};
                font-size: 12px; font-weight: 600; padding: 6px;
                margin: 4px 10px 8px 10px;
            }}
            QPushButton:hover {{ border-color: {ACCENT}; color: {ACCENT}; background: {ACCENT_DIM}; }}
        """)
        add_cam.setCursor(Qt.CursorShape.PointingHandCursor)
        add_cam.clicked.connect(lambda: self.navigate_to(1))
        lay.addWidget(add_cam)

        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: {BORDER};")
        lay.addWidget(div)

        # Nav
        nc = QWidget()
        nc.setStyleSheet("background: transparent;")
        nl = QVBoxLayout(nc)
        nl.setContentsMargins(10, 8, 10, 8)
        nl.setSpacing(2)

        self._nav_items = []
        for icon, label in [("","Dashboard"),("","Cameras"),("","AI Search"),
                             ("","AI Training"),("","Settings")]:
            item = NavItem(icon, label)
            item.clicked.connect(lambda _, i=item: self._on_nav(i))
            self._nav_items.append(item)
            nl.addWidget(item)
        nl.addStretch()
        lay.addWidget(nc)
        lay.addStretch()

        # Footer div
        fd = QFrame()
        fd.setFixedHeight(1)
        fd.setStyleSheet(f"background: {BORDER};")
        lay.addWidget(fd)

        # AI badge — click to go to Settings
        badge_wrap = QWidget()
        badge_wrap.setStyleSheet("background: transparent; border: none; padding: 8px 10px 10px 10px;")
        bwl = QVBoxLayout(badge_wrap)
        bwl.setContentsMargins(10, 8, 10, 10)
        bwl.setSpacing(0)

        self._ai_badge = QWidget()
        self._ai_badge.setStyleSheet(f"""
            QWidget {{
                background: {SURFACE};
                border: 1px solid {BORDER};
                border-radius: {RADIUS_SM};
            }}
            QWidget:hover {{
                border-color: {ACCENT};
            }}
            QLabel {{ border: none; background: transparent; }}
        """)
        self._ai_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ai_badge.setMinimumHeight(52)
        self._ai_badge.setMinimumWidth(140)
        self._ai_badge.mousePressEvent = lambda e: self.navigate_to(4)
        bl = QHBoxLayout(self._ai_badge)
        bl.setContentsMargins(12, 0, 12, 0)
        bl.setSpacing(10)

        ai_icon = QLabel("AI")
        ai_icon.setStyleSheet(
            f"color: {ACCENT}; font-size: 11px; font-weight: 900; "
            f"background: {ACCENT_DIM}; border-radius: 4px; padding: 2px 5px;"
        )

        bi = QVBoxLayout()
        bi.setSpacing(2)
        self._badge_name   = QLabel("No AI provider")
        self._badge_name.setStyleSheet(
            f"color: {TEXT}; font-size: 11px; font-weight: 700;"
        )
        self._badge_name.setWordWrap(True)
        self._badge_status = QLabel("Go to Settings")
        self._badge_status.setStyleSheet(
            f"color: {TEXT3}; font-size: 10px; font-family: '{FONT_DISPLAY}';"
        )
        bi.addWidget(self._badge_name)
        bi.addWidget(self._badge_status)

        bl.addWidget(ai_icon)
        bl.addLayout(bi)
        bl.addStretch()
        bl.addWidget(QLabel("›", styleSheet=f"color: {TEXT3}; font-size: 16px;"))

        bwl.addWidget(self._ai_badge)
        lay.addWidget(badge_wrap)

        self._refresh_camera_list()
        self._refresh_ai_badge()

        self._cam_timer = QTimer(self)
        self._cam_timer.timeout.connect(self._refresh_camera_list)
        self._cam_timer.start(5000)

        return sb

    # ── Refresh helpers ───────────────────────────────────────────────────────

    def _refresh_camera_list(self):
        cameras = get_cameras()
        # Only rebuild if camera count changed — avoid unnecessary widget churn
        current_count = self._cam_list_layout.count() - 1  # -1 for stretch
        if current_count == len(cameras):
            return

        while self._cam_list_layout.count() > 1:
            item = self._cam_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not cameras:
            e = QLabel("No cameras yet")
            e.setStyleSheet(f"color:{TEXT3};font-size:11px;padding:6px 8px;font-family:'{FONT_MONO}';")
            self._cam_list_layout.insertWidget(0, e)
        else:
            for cam in cameras:
                cam_id, name, source, cam_type, active = cam
                item = CameraListItem(name, source, cam_type,
                                      on_click=lambda: self.navigate_to(1))
                self._cam_list_layout.insertWidget(self._cam_list_layout.count()-1, item)

        total = len(cameras)
        if total == 0:
            self._status_text.setText("No cameras · add one to start")
            self._status_dot.setStyleSheet(f"color:{TEXT3};font-size:8px;")
        else:
            self._status_text.setText(f"{total} camera{'s' if total!=1 else ''} · recording")
            self._status_dot.setStyleSheet(f"color:{GREEN};font-size:8px;")

    def _refresh_ai_badge(self):
        provider = get_setting("ai_provider", "")
        from core.storage import get_secure_setting
        key = get_secure_setting("ai_api_key", "")
        names = {"openai":"ChatGPT","gemini":"Gemini","claude":"Claude",
                 "deepseek":"DeepSeek","grok":"Grok"}
        if provider and key:
            self._badge_name.setText(names.get(provider, provider))
            self._badge_status.setText("API key set")
            self._badge_status.setStyleSheet(f"color:{GREEN};font-size:10px;font-family:'{FONT_MONO}';background:transparent;")
        else:
            self._badge_name.setText("No AI provider")
            self._badge_status.setText("Set up in Settings")
            self._badge_status.setStyleSheet(f"color:{TEXT3};font-size:10px;font-family:'{FONT_DISPLAY}';background:transparent;")

    # ── Navigation ────────────────────────────────────────────────────────────

    def _on_nav(self, clicked):
        for i, item in enumerate(self._nav_items):
            item.setChecked(item is clicked)
            if item is clicked:
                self._stack.setCurrentIndex(i)
        if clicked is self._nav_items[4]:
            QTimer.singleShot(300, self._refresh_ai_badge)

    def navigate_to(self, index):
        if 0 <= index < len(self._nav_items):
            self._nav_items[index].click()

    # ── Alerts ────────────────────────────────────────────────────────────────

    def _poll_alerts(self):
        alerts = get_unseen_alerts()
        if alerts:
            self._alert_btn.setText(f"! Alerts ({len(alerts)})")
            self._alert_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255,68,102,0.12);
                    border: 1px solid {RED};
                    border-radius: {RADIUS_SM};
                    color: {RED};
                    font-size: 12px;
                    font-weight: 700;
                    padding: 0 14px;
                    min-width: 100px;
                    min-height: 32px;
                }}
            """)
        else:
            self._alert_btn.setText("Alerts")
            self._alert_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: 1px solid {BORDER};
                    border-radius: {RADIUS_SM};
                    color: {TEXT2};
                    font-size: 12px;
                    font-weight: 600;
                    padding: 0 14px;
                    min-width: 72px;
                    min-height: 32px;
                }}
                QPushButton:hover {{ border-color: {ACCENT}; color: {ACCENT}; background: {ACCENT_DIM}; }}
            """)

    def _show_alerts(self):
        alerts = get_unseen_alerts()
        if not alerts:
            QMessageBox.information(self, "Alerts", "No new alerts.")
            return
        lines = []
        for aid, cam_id, atype, msg, created_at, cam_name in alerts:
            lines.append(f"[{created_at[:16]}] {cam_name}: {msg}")
        QMessageBox.warning(self, f"⚠ {len(alerts)} Camera Alert(s)",
                            "\n".join(lines))
        mark_alerts_seen()
        self._poll_alerts()

    # ── Terms + voting ────────────────────────────────────────────────────────

    def _check_terms_and_voting(self):
        if not has_accepted_terms():
            dlg = TermsDialog(self)
            if dlg.exec() != TermsDialog.DialogCode.Accepted:
                sys.exit(0)
        QTimer.singleShot(200, self._show_voting_popup)

    def _show_voting_popup(self):
        popup = VotingPopup(self)
        if popup.should_show():
            popup.exec()

    def closeEvent(self, event):
        if hasattr(self._page_cameras, 'stop_all_cameras'):
            self._page_cameras.stop_all_cameras()
        event.accept()

    # ── Public: camera disconnect notification (called from cameras_page) ──────

    def notify_camera_disconnect(self, cam_id: int, cam_name: str):
        self._poll_alerts()  # refresh bell immediately