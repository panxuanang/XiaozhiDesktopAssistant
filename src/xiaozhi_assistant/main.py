from __future__ import annotations

import sys

from .logging_setup import setup_logging


def main() -> None:
    setup_logging()
    if "--mcp-server" in sys.argv:
        from .mcp_server import main as mcp_main
        mcp_main()
        return

    from PySide6.QtWidgets import QApplication
    from .app.gui import MainWindow
    from .config import load_settings
    from .secrets_store import get_api_key

    app = QApplication(sys.argv)
    app.setApplicationName("小智电脑助手")
    app.setQuitOnLastWindowClosed(False)
    win = MainWindow()
    settings = load_settings()
    first_run = not settings.xiaozhi_endpoint or not get_api_key()
    minimized = "--minimized" in sys.argv or settings.start_minimized
    if first_run or not minimized:
        win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
