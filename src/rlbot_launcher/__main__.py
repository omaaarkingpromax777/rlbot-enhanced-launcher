import sys


def main() -> int:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from . import APP_NAME
    from .ui.context import AppContext
    from .ui.main_window import MainWindow
    from .ui.theme import QSS

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(QSS)
    ctx = AppContext.create()
    if ctx.settings.language == "ar":
        app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    win = MainWindow(ctx)
    if "--section" in sys.argv:
        win.show_section(sys.argv[sys.argv.index("--section") + 1])
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
