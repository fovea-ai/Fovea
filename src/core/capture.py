# =============================================================================
# capture.py — Camera Feed Capture Thread
# =============================================================================
#
# This file handles connecting to cameras and capturing frames continuously.
# It runs in a BACKGROUND THREAD (QThread) so the UI stays responsive.
#
# HOW IT WORKS (for beginners):
#   - A "thread" is like a separate mini-program running at the same time.
#     Without threads, the app would freeze every time it reads a camera frame.
#   - Every ~33ms (30fps) we read a frame from the camera and emit it
#     to the UI for the live preview (frame_ready signal).
#   - Every N seconds (capture_interval setting) we SAVE a frame to disk
#     as a JPEG file and record it in the database.
#   - If the camera disconnects, we detect it, send an alert, and keep
#     trying to reconnect automatically.
#
# KEY CONCEPTS:
#   - Signal: A way for a background thread to safely send data to the UI.
#             Think of it like sending a message. The UI listens for signals.
#   - RTSP: The protocol most IP/security cameras use to stream video.
#           Like a URL for a live video stream.
#   - CAP_DSHOW: Windows-specific camera backend. Faster than the default.
#   - FFmpeg: A video tool that OpenCV uses to connect to RTSP cameras.
# =============================================================================

import cv2
import os
import time
import platform
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal
from core.storage import save_frame, FRAMES_PATH, add_camera_alert, get_setting, update_frame_description
from core.local_search import build_frame_description

DISCONNECT_THRESHOLD = 15   # consecutive failed reads before declaring disconnected
RECONNECT_INTERVAL   = 8    # minimum seconds between reconnect attempts


def _send_os_notification(title: str, message: str):
    try:
        from plyer import notification
        notification.notify(
            title=title, message=message,
            app_name="Fovea", timeout=8
        )
    except Exception:
        pass


def _open_capture(src, cam_type: str):
    """
    Open a VideoCapture with the best backend for the source type.

    Supports:
    - webcam:  Built-in or USB camera by index (0, 1, 2...)
    - rtsp:    IP/security cameras via RTSP stream URL
    - http:    WiFi cameras streaming MJPEG over HTTP
    - auto:    Detect type from URL (rtsp://, http://, https://)

    Returns a cv2.VideoCapture or None if connection failed.
    """
    cap = None

    # Auto-detect type from URL if not specified
    src_str = str(src).lower()
    if cam_type == "rtsp" or src_str.startswith("rtsp://"):
        cam_type = "rtsp"
    elif cam_type == "http" or src_str.startswith("http://") or src_str.startswith("https://"):
        cam_type = "http"

    if cam_type == "rtsp":
        # RTSP — used by most IP security cameras (Hikvision, Dahua, Reolink etc)
        # TCP transport is more reliable than UDP, especially over WiFi
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

        cap = cv2.VideoCapture(src, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            cap.release()
            return None

    elif cam_type == "http":
        # HTTP/MJPEG — used by many cheap WiFi cameras, IP webcams, and phone camera apps
        # Examples:
        #   http://192.168.1.100:8080/video  (IP Webcam app for Android)
        #   http://192.168.1.100/mjpeg       (many cheap cameras)
        #   http://192.168.1.100:80/stream   (TP-Link, Xiaomi etc)
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = ""
        cap = cv2.VideoCapture(src, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            cap.release()
            return None

    elif cam_type == "http":
        # HTTP/MJPEG streams — used by cheap WiFi cameras and phone camera apps
        # OpenCV can open these directly with VideoCapture
        # No special transport setting needed — just use the URL directly
        cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            cap.release()
            return None

    elif cam_type == "webcam":
        # Webcam — built-in laptop camera or USB camera
        idx = int(src) if str(src).isdigit() else 0
        if platform.system() == "Windows":
            # DirectShow backend on Windows — fastest, most compatible
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap.release()
                cap = cv2.VideoCapture(idx)
        elif platform.system() == "Linux":
            # V4L2 backend on Linux — works with most USB cams
            cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
            if not cap.isOpened():
                cap.release()
                cap = cv2.VideoCapture(idx)
        else:
            cap = cv2.VideoCapture(idx)

        if not cap.isOpened():
            cap.release()
            return None

    else:
        # Generic fallback — let OpenCV figure it out
        cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            cap.release()
            return None

    # Set a read timeout so we don't hang forever on bad streams
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)   # minimal buffer — reduces latency

    # Cap resolution to 1280x720 max for performance — enough for AI analysis
    # (cameras often default to 4K which is unnecessary and slow)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    if cam_type == "rtsp":
        # Give RTSP streams a timeout
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)   # 10 second open timeout
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)    # 5 second read timeout

    return cap


class CaptureThread(QThread):
    frame_captured   = pyqtSignal(int, str, str)   # cam_id, filepath, timestamp
    frame_ready      = pyqtSignal(int, object)      # cam_id, numpy array
    error_signal     = pyqtSignal(int, str)         # cam_id, error message
    status_signal    = pyqtSignal(int, str)         # cam_id, status string
    disconnect_alert = pyqtSignal(int, str)         # cam_id, camera name
    storage_error    = pyqtSignal(str)

    def __init__(self, camera_id: int, camera_name: str, source,
                 cam_type: str, capture_interval: int = 5):
        super().__init__()
        self.camera_id        = camera_id
        self.camera_name      = camera_name
        self.source           = source
        self.cam_type         = cam_type
        self.capture_interval = capture_interval
        self.running          = False
        self._cap             = None
        self._fail_count      = 0
        self._last_reconnect  = 0

    def run(self):
        self.running = True
        src     = str(self.source)
        cam_dir = os.path.join(FRAMES_PATH, str(self.camera_id))
        os.makedirs(cam_dir, exist_ok=True)

        self.status_signal.emit(self.camera_id, "connecting")

        # Initial connection attempt
        self._cap = _open_capture(src, self.cam_type)
        if self._cap is None:
            self.error_signal.emit(
                self.camera_id,
                f"Could not connect to camera.\n"
                f"Source: {src}\n"
                f"For RTSP: check IP address, username, password, and port.\n"
                f"For webcam: try a different index (0, 1, 2...)."
            )
            self.status_signal.emit(self.camera_id, "disconnected")
            return

        self.status_signal.emit(self.camera_id, "connected")
        self._fail_count = 0
        last_save        = 0

        while self.running:
            if self._cap is None:
                time.sleep(0.1)
                continue

            ret, frame = self._cap.read()

            if not ret or frame is None:
                self._fail_count += 1

                if self._fail_count == DISCONNECT_THRESHOLD:
                    self.status_signal.emit(self.camera_id, "disconnected")
                    self.error_signal.emit(
                        self.camera_id,
                        "Connection lost. Attempting to reconnect..."
                    )
                    self.disconnect_alert.emit(self.camera_id, self.camera_name)
                    add_camera_alert(
                        self.camera_id, "disconnect",
                        f"'{self.camera_name}' lost connection"
                    )
                    _send_os_notification(
                        "Fovea — Camera Alert",
                        f"'{self.camera_name}' disconnected or signal lost"
                    )

                # Try to reconnect after enough failures
                now = time.time()
                if (self._fail_count >= DISCONNECT_THRESHOLD and
                        now - self._last_reconnect >= RECONNECT_INTERVAL):
                    self._last_reconnect = now
                    self.status_signal.emit(self.camera_id, "reconnecting")

                    if self._cap:
                        self._cap.release()
                        self._cap = None

                    new_cap = _open_capture(src, self.cam_type)
                    if new_cap is not None:
                        self._cap        = new_cap
                        self._fail_count = 0
                        self.status_signal.emit(self.camera_id, "connected")
                        if self.running:  # Only notify if we didn't stop intentionally
                            _send_os_notification(
                                "Fovea — Camera Reconnected",
                                f"'{self.camera_name}' is back online"
                            )
                    else:
                        self.error_signal.emit(
                            self.camera_id,
                            f"Reconnect failed. Retrying in {RECONNECT_INTERVAL}s..."
                        )

                time.sleep(0.1)
                continue

            # Good frame
            if self._fail_count >= DISCONNECT_THRESHOLD:
                self.status_signal.emit(self.camera_id, "connected")
            self._fail_count = 0

            # Emit for live preview
            self.frame_ready.emit(self.camera_id, frame.copy())

            # Save at interval
            now = time.time()
            if now - last_save >= self.capture_interval:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                filename  = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".jpg"
                filepath  = os.path.join(cam_dir, filename)
                try:
                    cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    save_frame(self.camera_id, filepath, timestamp)
                    self.frame_captured.emit(self.camera_id, filepath, timestamp)

                    # Auto-describe the frame locally so it can be searched later.
                    # We only do this when NO AI API is configured — if an AI key
                    # is set, the AI will describe frames during search instead.
                    # We run this in a try/except so a description failure never
                    # stops the capture loop.
                    try:
                        provider = get_setting("ai_provider", "")
                        api_key  = get_setting("ai_api_key", "")
                        if not provider or not api_key:
                            # Build a local description using computer vision
                            local_desc = build_frame_description(filepath)
                            if local_desc:
                                # We need the frame ID — get it from the last inserted row
                                from core.storage import DB_PATH
                                import sqlite3 as _sqlite3
                                conn = _sqlite3.connect(DB_PATH)
                                c    = conn.cursor()
                                c.execute(
                                    "SELECT id FROM frames WHERE filepath=? ORDER BY id DESC LIMIT 1",
                                    (filepath,)
                                )
                                row = c.fetchone()
                                conn.close()
                                if row:
                                    update_frame_description(row[0], local_desc)
                    except Exception:
                        pass  # Description failure never breaks capture

                except RuntimeError as e:
                    self.storage_error.emit(str(e))
                except Exception as e:
                    self.storage_error.emit(f"Frame save error: {e}")
                last_save = now

            time.sleep(0.033)

        # Cleanup
        if self._cap:
            self._cap.release()
            self._cap = None
        self.status_signal.emit(self.camera_id, "disconnected")

    def stop(self):
        self.running = False
        self.wait(5000)