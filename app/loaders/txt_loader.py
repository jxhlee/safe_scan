"""Loads raw text from a .txt file, always normalized to a UTF-8 str.

A PDF loader can be added later behind the same contract (a function that
returns plain text) without the core pipeline needing to change.
"""
from __future__ import annotations

from pathlib import Path

ENCODINGS_TO_TRY = ("utf-8-sig", "utf-8", "cp949")


def load_txt(path: str | Path) -> str:
    data = Path(path).read_bytes()
    for encoding in ENCODINGS_TO_TRY:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")
