"""pywebview JS<->Python bridge. The only module that touches both core/
and webview, so core/ stays completely UI-agnostic and swappable later.
"""
from __future__ import annotations

from pathlib import Path

import webview

from app.core.analyze import analyze
from app.loaders.pdf_loader import load_pdf
from app.loaders.txt_loader import load_txt


class Api:
    def analyze_text(self, text: str, summary_length: int = 5, risk_weight_ratio: float = 0.6) -> dict:
        text = (text or "").strip()
        if not text:
            return {"error": "분석할 텍스트가 없습니다."}
        try:
            result = analyze(
                text,
                summary_length=int(summary_length),
                risk_weight_ratio=float(risk_weight_ratio),
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI, not a crash
            return {"error": f"분석 중 오류가 발생했습니다: {exc}"}
        return result.to_dict()

    def open_file(self) -> dict:
        window = webview.windows[0]
        paths = window.create_file_dialog(
            webview.FileDialog.OPEN,
            file_types=(
                "지원 파일 (*.txt;*.pdf)",
                "텍스트 파일 (*.txt)",
                "PDF 파일 (*.pdf)",
                "모든 파일 (*.*)",
            ),
        )
        if not paths:
            return {"text": None}
        path = Path(paths[0])
        try:
            if path.suffix.lower() == ".pdf":
                text = load_pdf(path)
            else:
                text = load_txt(path)
        except Exception as exc:  # noqa: BLE001
            return {"error": f"파일을 읽는 중 오류가 발생했습니다: {exc}"}
        if not text.strip():
            return {"error": "파일에서 텍스트를 추출하지 못했습니다. 스캔된 이미지 PDF는 지원하지 않습니다."}
        return {"text": text, "filename": path.name}
