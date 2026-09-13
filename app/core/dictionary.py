"""Loads risk/safe pattern dictionaries and checklist definitions from data files.

Adding a new document type later (e.g. 근로계약서) means dropping a new folder
under data/patterns/<doc_type>/ with the same JSON shape and adding its name
to DOCUMENT_TYPES below - no other core code needs to change.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.core.models import ChecklistDef, PatternEntry

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "patterns"

# Registry of supported document types -> pattern folder name.
# "common" covers 이용약관 + 개인정보처리방침 (온라인 서비스 가입류).
DOCUMENT_TYPES: dict[str, str] = {
    "common": "common",
}


@dataclass
class Dictionary:
    entries: list[PatternEntry]
    checklist_items: list[ChecklistDef]

    def entries_by_id(self) -> dict[str, PatternEntry]:
        return {e.id: e for e in self.entries}


def _load_entries(folder: Path) -> list[PatternEntry]:
    entries: list[PatternEntry] = []
    for json_file in sorted(folder.glob("*.json")):
        if json_file.name == "checklist_items.json":
            continue
        raw = json.loads(json_file.read_text(encoding="utf-8"))
        for item in raw:
            entries.append(PatternEntry(**item))
    return entries


def _load_checklist(folder: Path) -> list[ChecklistDef]:
    checklist_file = folder / "checklist_items.json"
    if not checklist_file.exists():
        return []
    raw = json.loads(checklist_file.read_text(encoding="utf-8"))
    return [ChecklistDef(**item) for item in raw]


def load_dictionary(doc_types: tuple[str, ...] = ("common",)) -> Dictionary:
    entries: list[PatternEntry] = []
    checklist_items: list[ChecklistDef] = []
    seen_checklist_ids: set[str] = set()

    for doc_type in doc_types:
        folder_name = DOCUMENT_TYPES.get(doc_type)
        if folder_name is None:
            raise ValueError(f"알 수 없는 문서 유형입니다: {doc_type}")
        folder = DATA_DIR / folder_name
        entries.extend(_load_entries(folder))
        for item in _load_checklist(folder):
            if item.id not in seen_checklist_ids:
                checklist_items.append(item)
                seen_checklist_ids.add(item.id)

    return Dictionary(entries=entries, checklist_items=checklist_items)
