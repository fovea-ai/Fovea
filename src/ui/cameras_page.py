# =============================================================================
# cameras_page.py — Camera Management Page
# =============================================================================
#
# This page lets users add, connect, and monitor their cameras.
#
# HOW CAMERA CARDS WORK (for beginners):
#   Each connected camera gets a "card" widget showing:
#   - A live preview (updated ~30 times per second from the capture thread)
#   - The camera name and source (IP address or webcam index)
#   - A colored dot: green=connected, yellow=reconnecting, red=error
#   - Connect/Disconnect and Remove buttons
#
# THREADING:
#   Each camera runs in its OWN thread (CaptureThread from capture.py).
#   This means 4 cameras = 4 threads running simultaneously.
#   The threads communicate back to the UI via PyQt6 signals.
#
# ADDING A CAMERA:
#   Webcam: Just pick index 0, 1, 2... Most laptops = index 0
#   RTSP:   Enter the camera's stream URL (check your camera's manual)
#           Format: rtsp://username:password@ip_address:554/stream
# =============================================================================

import cv2
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QDialog, QLineEdit, QComboBox,
    QMessageBox, QGridLayout, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap

from ui.theme import *
from core.storage import add_camera, get_cameras, delete_camera, get_setting
from core.capture import CaptureThread


class AddCameraDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Camera")
        self.setMinimumWidth(480)
        self.setStyleSheet(f"""
            QDialog {{ background: {BG2}; }}
            QLabel  {{ color: {TEXT}; font-family: '{FONT_DISPLAY}'; }}
            QLineEdit, QComboBox {{
                background: {BG3};
                color: {TEXT};
                border: 1px solid {BORDER2};
                border-radius: {RADIUS_SM};
                padding: 10px 14px;
                font-family: '{FONT_DISPLAY}';
                font-size: 13px;
                min-height: 20px;
            }}
            QLineEdit:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
            QComboBox::drop-down {{ border: none; padding-right: 8px; }}
            QComboBox QAbstractItemView {{
                background: {BG2};
                color: {TEXT};
                border: 1px solid {BORDER2};
                selection-background-color: {ACCENT};
                selection-color: #000;
            }}
        """)
        self._result = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(0)

        title = QLabel("Add New Camera")
        title.setStyleSheet(f"color: {TEXT}; font-size: 20px; font-weight: 800;")
        layout.addWidget(title)
        layout.addSpacing(20)

        # Camera Name
        lbl1 = QLabel("Camera Name")
        lbl1.setStyleSheet(f"color: {TEXT2}; font-size: 12px; font-weight: 600; font-family: '{FONT_MONO}';")
        layout.addWidget(lbl1)
        layout.addSpacing(5)
        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. Front Door, Parking Lot, Back Yard")
        layout.addWidget(self._name)
        layout.addSpacing(16)

        # Camera Type
        lbl2 = QLabel("Camera Type")
        lbl2.setStyleSheet(f"color: {TEXT2}; font-size: 12px; font-weight: 600; font-family: '{FONT_MONO}';")
        layout.addWidget(lbl2)
        layout.addSpacing(5)
        self._type = QComboBox()
        self._type.addItems([
            "Webcam  (built-in / USB)",
            "RTSP  (IP / security camera, NVR, DVR)",
            "HTTP / MJPEG  (cheap WiFi cameras, baby monitors)",
            "Phone Camera  (DroidCam, IP Webcam app)",
        ])
        self._type.currentIndexChanged.connect(self._on_type)
        layout.addWidget(self._type)
        layout.addSpacing(16)

        # Source
        self._src_label = QLabel("Webcam Index  (0 = default, 1 = second camera, etc.)")
        self._src_label.setStyleSheet(f"color: {TEXT2}; font-size: 12px; font-weight: 600; font-family: '{FONT_MONO}';")
        layout.addWidget(self._src_label)
        layout.addSpacing(5)
        self._source = QLineEdit()
        self._source.setPlaceholderText("0")
        layout.addWidget(self._source)
        layout.addSpacing(6)

        # Hint text
        self._hint = QLabel(
            "Tip: Most built-in webcams are index 0. USB cameras are usually 1 or 2.\n"
            "For RTSP: rtsp://admin:password@192.168.1.x:554/stream"
        )
        self._hint.setStyleSheet(f"color: {TEXT3}; font-size: 11px; font-family: '{FONT_MONO}';")
        self._hint.setWordWrap(True)
        layout.addWidget(self._hint)
        layout.addSpacing(24)

        # Buttons
        btns = QHBoxLayout()
        btns.setSpacing(10)
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(btn_ghost())
        cancel.setMinimumHeight(42)
        cancel.clicked.connect(self.reject)

        add = QPushButton("Add Camera")
        add.setStyleSheet(btn_primary())
        add.setMinimumHeight(42)
        add.clicked.connect(self._submit)

        btns.addWidget(cancel)
        btns.addWidget(add)
        layout.addLayout(btns)

    def _on_type(self, idx):
        if idx == 0:
            self._src_label.setText("Webcam Index  (0 = default, 1 = second camera, etc.)")
            self._source.setPlaceholderText("0")
            self._hint.setText(
                "Most built-in webcams are index 0.\n"
                "USB cameras are usually index 1 or 2.\n"
                "If it doesn't connect, try the next number."
            )
        elif idx == 1:
            self._src_label.setText("RTSP URL")
            self._source.setPlaceholderText("rtsp://admin:password@192.168.1.100:554/stream")
            self._hint.setText(
                "Hikvision:    rtsp://admin:PASS@IP:554/Streaming/Channels/101\n"
                "Dahua:        rtsp://admin:PASS@IP:554/cam/realmonitor?channel=1\n"
                "Reolink:      rtsp://admin:PASS@IP:554/h264Preview_01_main\n"
                "TP-Link Tapo: rtsp://user:PASS@IP:554/stream1\n"
                "Find your camera's IP in your router's connected devices list."
            )
        elif idx == 2:
            self._src_label.setText("HTTP / MJPEG Stream URL")
            self._source.setPlaceholderText("http://192.168.1.100:8080/video")
            self._hint.setText(
                "For cheap WiFi cameras and baby monitors that stream over HTTP.\n"
                "Common URLs:\n"
                "  http://192.168.1.x:8080/video\n"
                "  http://192.168.1.x:8080/?action=stream\n"
                "Check your camera's app or web interface for the exact URL."
            )
        elif idx == 3:
            self._src_label.setText("Phone Camera URL")
            self._source.setPlaceholderText("http://192.168.1.x:8080")
            self._hint.setText(
                "Turn your phone into a security camera (free):\n\n"
                "Android: Install 'IP Webcam' app -> tap Start Server\n"
                "         Enter the URL shown on your phone screen\n\n"
                "iPhone:  Install 'EpocCam' or 'DroidCam' -> use the shown IP\n\n"
                "Phone and computer must be on the same WiFi network."
            )

    def _submit(self):
        name   = self._name.text().strip()
        source = self._source.text().strip()
        idx    = self._type.currentIndex()

        if not name:
            QMessageBox.warning(self, "Missing", "Please enter a camera name.")
            return

        if idx == 0:
            ctype  = "webcam"
            source = source or "0"
            if not source.isdigit():
                QMessageBox.warning(self, "Invalid", "Webcam index must be a number: 0, 1, 2...")
                return

        elif idx == 1:
            ctype = "rtsp"
            if not source:
                QMessageBox.warning(self, "Missing", "Please enter the RTSP URL.")
                return
            if not source.startswith("rtsp://"):
                QMessageBox.warning(self, "Invalid URL",
                    "RTSP URL must start with rtsp://\n"
                    "Example: rtsp://admin:password@192.168.1.100:554/stream")
                return

        elif idx == 2:
            ctype = "http"
            if not source:
                QMessageBox.warning(self, "Missing", "Please enter the HTTP stream URL.")
                return
            if not (source.startswith("http://") or source.startswith("https://")):
                source = "http://" + source

        elif idx == 3:
            # Phone camera — HTTP/MJPEG, auto-complete URL
            ctype = "http"
            if not source:
                QMessageBox.warning(self, "Missing", "Please enter your phone's camera URL.")
                return
            if not (source.startswith("http://") or source.startswith("https://")):
                source = "http://" + source
            # Auto-append /video if user just entered the base IP:port
            if source.count("/") <= 2:
                source = source.rstrip("/") + "/video"

        else:
            ctype = "rtsp"

        self._result = (name, source, ctype)
        self.accept()

    def result_data(self):
        return self._result


class CameraCard(QFrame):
    remove_requested    = pyqtSignal(int)
    disconnect_detected = pyqtSignal(int, str)

    def __init__(self, cam_id, name, source, cam_type):
        super().__init__()
        self.cam_id  = cam_id
        self._name   = name
        self._source = source
        self._type   = cam_type
        self._thread = None
        self._build()

    def _build(self):
        self.setMinimumWidth(300)
        self.setMaximumWidth(420)
        self.setStyleSheet(f"QFrame {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: {RADIUS}; }}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 14)
        lay.setSpacing(0)

        # Preview
        self._preview = QLabel()
        self._preview.setMinimumHeight(180)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setWordWrap(True)
        self._preview.setStyleSheet(f"""
            background: {BG3};
            border: none;
            border-radius: {RADIUS} {RADIUS} 0 0;
            color: {TEXT3};
            font-size: 11px;
            font-family: '{FONT_MONO}';
            padding: 8px;
        """)
        self._preview.setText("Not connected")
        lay.addWidget(self._preview)
        lay.addSpacing(12)

        # Info
        info_row = QHBoxLayout()
        info_row.setContentsMargins(14, 0, 14, 0)

        col = QVBoxLayout()
        col.setSpacing(3)
        nl = QLabel(self._name)
        nl.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700;")

        type_label = "Webcam" if self._type == "webcam" else "RTSP"
        src_text   = f"Index {self._source}" if self._type == "webcam" else self._source
        if len(src_text) > 32:
            src_text = src_text[:32] + "..."
        sl = QLabel(f"{type_label}  ·  {src_text}")
        sl.setStyleSheet(f"color: {TEXT3}; font-size: 10px; font-family: '{FONT_MONO}';")

        col.addWidget(nl)
        col.addWidget(sl)
        info_row.addLayout(col)
        info_row.addStretch()

        self._dot = QLabel("●")
        self._dot.setStyleSheet(f"color: {TEXT3}; font-size: 14px;")
        info_row.addWidget(self._dot)
        lay.addLayout(info_row)
        lay.addSpacing(10)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(14, 0, 14, 0)
        btn_row.setSpacing(8)

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setStyleSheet(btn_primary())
        self._connect_btn.setMinimumHeight(36)
        self._connect_btn.clicked.connect(self._toggle)

        del_btn = QPushButton("Remove")
        del_btn.setStyleSheet(btn_danger())
        del_btn.setMinimumHeight(36)
        del_btn.clicked.connect(lambda: self.remove_requested.emit(self.cam_id))

        btn_row.addWidget(self._connect_btn)
        btn_row.addWidget(del_btn)
        lay.addLayout(btn_row)

    def _toggle(self):
        if self._thread and self._thread.running:
            self._thread.stop()
            self._thread = None
            self._connect_btn.setText("Connect")
            self._dot.setStyleSheet(f"color: {TEXT3}; font-size: 14px;")
            self._preview.setPixmap(QPixmap())
            self._preview.setText("Not connected")
        else:
            interval = int(get_setting("capture_interval", 5))
            self._thread = CaptureThread(
                self.cam_id, self._name, self._source, self._type, interval
            )
            self._thread.frame_ready.connect(self._on_frame)
            self._thread.status_signal.connect(self._on_status)
            self._thread.error_signal.connect(self._on_error)
            self._thread.disconnect_alert.connect(
                lambda cid, cname: self.disconnect_detected.emit(cid, cname)
            )
            self._thread.storage_error.connect(
                lambda msg: QMessageBox.warning(self, "Storage Warning", msg)
            )
            self._thread.start()
            self._connect_btn.setText("Disconnect")
            self._preview.setText("Connecting...")

    def _on_frame(self, cam_id, frame):
        if cam_id != self.cam_id:
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        pw  = self._preview.width()
        ph  = self._preview.height()
        pix = QPixmap.fromImage(img).scaled(
            pw, ph,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self._preview.setPixmap(pix)

    def _on_status(self, cam_id, status):
        if cam_id != self.cam_id:
            return
        colors = {
            "connected":    GREEN,
            "disconnected": TEXT3,
            "reconnecting": YELLOW,
            "connecting":   ACCENT,
        }
        self._dot.setStyleSheet(f"color: {colors.get(status, TEXT3)}; font-size: 14px;")
        if status == "reconnecting":
            self._preview.setText("Reconnecting...")
        elif status == "connecting":
            self._preview.setText("Connecting...")
        elif status == "disconnected" and not (self._thread and self._thread.running):
            self._preview.setText("Not connected")

    def _on_error(self, cam_id, msg):
        if cam_id != self.cam_id:
            return
        # Show first 120 chars of error, wrapped
        short = msg[:120] + ("..." if len(msg) > 120 else "")
        self._preview.setText(short)
        self._preview.setWordWrap(True)
        self._dot.setStyleSheet(f"color: {RED}; font-size: 14px;")

    def stop(self):
        if self._thread:
            self._thread.stop()


class CamerasPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG}; border: none;")
        self._cards  = {}
        self._parent = parent
        self._build_ui()
        self._load_cameras()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(0)

        # Header
        hdr = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(4)
        title = QLabel("Cameras")
        title.setStyleSheet(f"color: {TEXT}; font-size: 22px; font-weight: 800; letter-spacing: -0.5px;")
        sub = QLabel("Connect and monitor your cameras. All footage is saved locally on your machine.")
        sub.setStyleSheet(f"color: {TEXT3}; font-family: '{FONT_MONO}'; font-size: 11px;")
        left.addWidget(title)
        left.addWidget(sub)
        hdr.addLayout(left)
        hdr.addStretch()

        add_btn = QPushButton("Add Camera")
        add_btn.setStyleSheet(btn_primary())
        add_btn.setMinimumHeight(38)
        add_btn.setMinimumWidth(120)
        add_btn.clicked.connect(self._on_add)
        hdr.addWidget(add_btn)

        root.addLayout(hdr)
        root.addSpacing(24)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: transparent; }} {SCROLLBAR}")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._grid_widget = QWidget()
        self._grid_widget.setStyleSheet("background: transparent;")
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setSpacing(16)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll.setWidget(self._grid_widget)
        root.addWidget(scroll)

        # Empty state
        self._empty_lbl = QLabel(
            "No cameras added yet.\n\n"
            "Click 'Add Camera' to connect a webcam or IP security camera."
        )
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(f"color: {TEXT3}; font-size: 14px; padding: 40px;")
        root.addWidget(self._empty_lbl)
        self._empty_lbl.hide()

    def _load_cameras(self):
        for cam in get_cameras():
            cam_id, name, source, cam_type, active = cam
            self._add_card(cam_id, name, source, cam_type)
        self._update_empty()

    def _add_card(self, cam_id, name, source, cam_type):
        card = CameraCard(cam_id, name, source, cam_type)
        card.remove_requested.connect(self._on_remove)
        card.disconnect_detected.connect(self._on_disconnect)
        count = len(self._cards)
        row, col = divmod(count, 3)
        self._grid.addWidget(card, row, col)
        self._cards[cam_id] = card

    def _on_add(self):
        dlg = AddCameraDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.result_data()
            if data:
                cam_id = add_camera(*data)
                self._add_card(cam_id, *data)
                self._update_empty()

    def _on_remove(self, cam_id):
        card = self._cards.pop(cam_id, None)
        if card:
            card.stop()
            self._grid.removeWidget(card)
            card.deleteLater()
            delete_camera(cam_id)
            for i, c in enumerate(self._cards.values()):
                row, col = divmod(i, 3)
                self._grid.addWidget(c, row, col)
        self._update_empty()

    def _on_disconnect(self, cam_id, cam_name):
        if hasattr(self._parent, "notify_camera_disconnect"):
            self._parent.notify_camera_disconnect(cam_id, cam_name)

    def _update_empty(self):
        self._empty_lbl.setVisible(len(self._cards) == 0)

    def stop_all_cameras(self):
        for card in self._cards.values():
            card.stop()