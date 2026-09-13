"""Entry point: launches the desktop app (pywebview window)."""
from __future__ import annotations

from pathlib import Path

import webview

from app.ui.bridge import Api

WEB_DIR = Path(__file__).resolve().parent / "app" / "ui" / "web"


def main() -> None:
    api = Api()
    webview.create_window(
        "약관 세이프스캔",
        str(WEB_DIR / "index.html"),
        js_api=api,
        width=1280,
        height=860,
        min_size=(1000, 700),
    )
    webview.start()


if __name__ == "__main__":
    main()
