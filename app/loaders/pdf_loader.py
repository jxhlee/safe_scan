"""Loads raw text from a PDF file. Same contract as txt_loader.load_txt:
takes a path (or an in-memory byte stream, for the web server's uploads),
returns a plain-text str - core never needs to know a PDF was involved.

Scanned/image-only PDFs have no embedded text layer and will extract to
an empty (or near-empty) string; OCR is out of scope, so callers should
treat that as "couldn't read this file" rather than "empty document".
"""
from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

from pypdf import PdfReader


def load_pdf(source: str | Path | BinaryIO) -> str:
    reader = PdfReader(source if hasattr(source, "read") else str(source))
    pages_text = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages_text).strip()
