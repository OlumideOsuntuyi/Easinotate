"""Easinotate application entry point."""
import sys
import os

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon, QFont

from easinotate.gui.main_window import MainWindow
from easinotate.gui.style import stylesheet


def _resource_path(rel: str) -> str:
    """Find resource files, working both in source tree and bundled exe."""
    if hasattr(sys, "_MEIPASS"):
        # PyInstaller temp dir
        return os.path.join(sys._MEIPASS, rel)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), rel)


def main():
    # Enable high-DPI scaling on platforms that support it
    if hasattr(QApplication, "setHighDpiScaleFactorRoundingPolicy"):
        from PyQt6.QtCore import Qt
        try:
            QApplication.setHighDpiScaleFactorRoundingPolicy(
                Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
            )
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("Easinotate")
    app.setOrganizationName("Easinotate")
    app.setApplicationDisplayName("Easinotate")

    # Apply default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Apply stylesheet
    app.setStyleSheet(stylesheet())

    # Try to set a window icon if available
    icon_path = _resource_path(os.path.join("resources", "icon.png"))
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    win = MainWindow()
    if os.path.exists(icon_path):
        win.setWindowIcon(QIcon(icon_path))
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()