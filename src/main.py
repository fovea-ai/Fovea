import sys
import os
import platform

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(THIS_DIR)
sys.path.insert(0, THIS_DIR)

if platform.system() == "Windows":
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from ui.main_window import MainWindow


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Fovea")
    app.setApplicationVersion("2.0")

    # Set a proper base font so nothing gets clipped on HD monitors
    font = QFont("Segoe UI", 10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)

    app.setStyleSheet("""
        * {
            font-family: 'Segoe UI', sans-serif;
            outline: none;
        }
        QWidget {
            border: none;
        }
        QFrame {
            border: none;
        }
        QLabel {
            border: none;
            background: transparent;
        }
        QAbstractScrollArea {
            border: none;
        }
        QAbstractItemView {
            border: none;
            outline: none;
        }
        QPushButton {
            min-height: 28px;
            padding-left: 12px;
            padding-right: 12px;
        }
        QPushButton:focus {
            outline: none;
        }
        QLineEdit, QComboBox, QSpinBox {
            min-height: 32px;
        }
        QScrollBar:vertical {
            background: #080c10;
            width: 6px;
            border-radius: 3px;
            border: none;
        }
        QScrollBar::handle:vertical {
            background: #2a3f52;
            border-radius: 3px;
            min-height: 30px;
            border: none;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; border: none; }
        QScrollBar:horizontal {
            background: #080c10;
            height: 6px;
            border-radius: 3px;
            border: none;
        }
        QScrollBar::handle:horizontal {
            background: #2a3f52;
            border-radius: 3px;
            border: none;
        }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; border: none; }
        QToolTip {
            background-color: #131d26;
            color: #e8f4f8;
            border: 1px solid #00d4ff;
            padding: 6px;
            border-radius: 4px;
            font-size: 12px;
        }
        QMenu {
            background-color: #131d26;
            color: #e8f4f8;
            border: 1px solid #2a3f52;
            padding: 4px 0;
            font-size: 13px;
        }
        QMenu::item {
            padding: 6px 32px 6px 16px;
            background: transparent;
        }
        QMenu::item:selected {
            background-color: #1e3a4a;
            color: #e8f4f8;
        }
        QMenu::item:disabled {
            color: #4a6070;
        }
        QMenu::separator {
            height: 1px;
            background: #2a3f52;
            margin: 4px 0;
        }
    """)

    window = MainWindow()
    window.showMaximized()

    # Check for updates in background (non-blocking)
    def _check_update():
        try:
            import requests
            r = requests.get(
                "https://api.github.com/repos/Fovea-ai/Fovea/releases/latest",
                timeout=5
            )
            if r.status_code == 200:
                latest = r.json().get("tag_name", "").strip().lstrip("vV")
                current = "2.0"
                # Normalize: treat 2.0, 2.0.0, v2.0 all as the same
                def normalize(v): return ".".join(p for p in v.split(".") if p != "0" or v.split(".").index(p) < 2)
                if latest and normalize(latest) != normalize(current):
                    from PyQt6.QtWidgets import QMessageBox
                    QMessageBox.information(
                        window, "Update Available",
                        f"Fovea v{latest} is available!\n\n"
                        f"You are running v{current}.\n"
                        f"Visit github.com/Fovea-ai/Fovea to download the latest version."
                    )
        except Exception:
            pass  # Silent fail — update check is best-effort only

    from PyQt6.QtCore import QTimer
    QTimer.singleShot(3000, _check_update)  # Check 3 seconds after launch
    sys.exit(app.exec())


if __name__ == "__main__":
    main()