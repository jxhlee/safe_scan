"""Shared data models for the core analysis pipeline. UI-agnostic."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Literal

Grade = Literal["높음", "중간", "낮음"]
SignalType = Literal["risk", "safe"]

GRADE_ORDER: dict[str, int] = {"높음": 3, "중간": 2, "낮음": 1}


@dataclass
class PatternEntry:
    id: str
    category: str
    subcategory: str
    signal_type: SignalType
    grade: Grade | None
    patterns: list[str]
    headline: str
    explain: str
    simple_explain: str
    related_law: str


@dataclass
class ChecklistDef:
    id: str
    category: str
    label: str
    question: str
    simple_question: str


@dataclass
class Match:
    entry_id: str
    start: int
    end: int
    text: str


@dataclass
class Sentence:
    text: str
    start: int
    end: int
    clause_id: str | None = None


@dataclass
class Clause:
    id: str
    text: str
    start: int
    end: int
    label: str = ""
    sentences: list[Sentence] = field(default_factory=list)
    matched_entry_ids: list[str] = field(default_factory=list)
    grade: Grade | None = None
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("sentences", None)
        return d


@dataclass
class SummarySentence:
    text: str
    clause_id: str
    is_risk_boosted: bool
    score: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RiskItem:
    clause_id: str
    grade: Grade
    tags: list[str]
    title: str
    simple_title: str
    excerpt: str
    explain: list[str]
    simple_explain: list[str]
    related_law: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ChecklistResult:
    id: str
    category: str
    label: str
    question: str
    simple_question: str
    status: Literal["위험 발견", "언급 없음", "정상 고지 확인"]
    grade: Grade | None
    finding: str
    simple_finding: str
    linked_clause_ids: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class HighlightSpan:
    start: int
    end: int
    clause_id: str
    grade: Grade | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AnalysisResult:
    summary: list[SummarySentence]
    risk_list: list[RiskItem]
    checklist: list[ChecklistResult]
    full_text: str
    highlight_spans: list[HighlightSpan]

    def to_dict(self) -> dict:
        return {
            "summary": [s.to_dict() for s in self.summary],
            "risk_list": [r.to_dict() for r in self.risk_list],
            "checklist": [c.to_dict() for c in self.checklist],
            "full_text": self.full_text,
            "highlight_spans": [h.to_dict() for h in self.highlight_spans],
        }
