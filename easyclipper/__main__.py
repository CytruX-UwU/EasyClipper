"""Application entry point for both the CLI and python -m easyclipper."""

import sys

from PySide6.QtWidgets import QApplication
from shiboken6 import delete

from .window import Window


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("EasyClipper")
    app.setStyle("Fusion")
    window = Window()
    window.show()
    try:
        exit_code = app.exec()
    finally:
        # Release multimedia and translator objects before QApplication shuts down.
        app.removeTranslator(window.qt_translator)
        delete(window)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
