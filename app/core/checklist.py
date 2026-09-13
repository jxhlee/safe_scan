"""Derives the 3-state checklist (위험 발견 / 언급 없음 / 정상 고지 확인) from
clause matches. Reuses the same category taxonomy as the risk tags, so it
needs no extra algorithm - just a different view over the same matches.
"""
from __future__ import annotations

from collections import defaultdict

from app.core.models import Clause, ChecklistDef, ChecklistResult, GRADE_ORDER, PatternEntry

NOT_MENTIONED_FINDING = "명시 조항 없음"


def build_checklist(
    clauses: list[Clause],
    checklist_defs: list[ChecklistDef],
    entries_by_id: dict[str, PatternEntry],
) -> list[ChecklistResult]:
    clauses_by_id = {c.id: c for c in clauses}
    # subcategory -> list of (clause_id, grade, entry_id)
    risk_hits: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    # subcategory -> list of (clause_id, entry_id)
    safe_hits: dict[str, list[tuple[str, str]]] = defaultdict(list)

    for clause in clauses:
        for entry_id in clause.matched_entry_ids:
            entry = entries_by_id.get(entry_id)
            if entry is None:
                continue
            if entry.signal_type == "risk":
                risk_hits[entry.subcategory].append((clause.id, entry.grade, entry.id))
            else:
                safe_hits[entry.subcategory].append((clause.id, entry.id))

    def _finding(clause_id: str, entry_id: str) -> tuple[str, str]:
        clause = clauses_by_id.get(clause_id)
        entry = entries_by_id.get(entry_id)
        label = clause.label if clause else ""
        headline = entry.headline if entry else ""
        simple = entry.simple_explain if entry else ""
        if not label:
            return headline, simple
        return f"{label} · {headline}", f"{label} · {simple}"

    results = []
    for item in checklist_defs:
        risky = risk_hits.get(item.id, [])
        safe = safe_hits.get(item.id, [])

        if risky:
            top_clause_id, grade, top_entry_id = max(risky, key=lambda t: GRADE_ORDER[t[1]])
            status = "위험 발견"
            finding, simple_finding = _finding(top_clause_id, top_entry_id)
            linked = sorted({cid for cid, _, _ in risky})
        elif safe:
            grade = None
            status = "정상 고지 확인"
            first_clause_id, first_entry_id = safe[0]
            finding, simple_finding = _finding(first_clause_id, first_entry_id)
            linked = sorted({cid for cid, _ in safe})
        else:
            grade = None
            status = "언급 없음"
            finding = NOT_MENTIONED_FINDING
            simple_finding = NOT_MENTIONED_FINDING
            linked = []

        results.append(
            ChecklistResult(
                id=item.id,
                category=item.category,
                label=item.label,
                question=item.question,
                simple_question=item.simple_question,
                status=status,
                grade=grade,
                finding=finding,
                simple_finding=simple_finding,
                linked_clause_ids=linked,
            )
        )
    return results
