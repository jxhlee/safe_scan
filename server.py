"""Web entry point: serves the same frontend used by the desktop app over
HTTP instead of a pywebview bridge. Talks to the same UI-agnostic
`app.core` pipeline as `main.py` - only the transport differs.
"""
from __future__ import annotations

import io
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.core.analyze import analyze
from app.loaders.pdf_loader import load_pdf

WEB_DIR = Path(__file__).resolve().parent / "app" / "ui" / "web"

app = FastAPI(title="약관 세이프스캔")


class AnalyzeRequest(BaseModel):
    text: str
    summary_length: int = 5
    risk_weight_ratio: float = 0.6


@app.post("/api/analyze")
def api_analyze(req: AnalyzeRequest) -> dict:
    text = (req.text or "").strip()
    if not text:
        return {"error": "분석할 텍스트가 없습니다."}
    try:
        result = analyze(
            text,
            summary_length=req.summary_length,
            risk_weight_ratio=req.risk_weight_ratio,
        )
    except Exception as exc:  # noqa: BLE001 - surfaced to the UI, not a crash
        return {"error": f"분석 중 오류가 발생했습니다: {exc}"}
    return result.to_dict()


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)) -> dict:
    filename = file.filename or "uploaded"
    suffix = Path(filename).suffix.lower()
    data = await file.read()
    try:
        if suffix == ".pdf":
            text = load_pdf(io.BytesIO(data))
        else:
            text = data.decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        return {"error": f"파일을 읽는 중 오류가 발생했습니다: {exc}"}
    if not text.strip():
        return {"error": "파일에서 텍스트를 추출하지 못했습니다. 스캔된 이미지 PDF는 지원하지 않습니다."}
    return {"text": text, "filename": filename}


# Serves index.html/app.js/style.css - must be mounted last so /api/* above
# takes precedence over the catch-all static route.
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
