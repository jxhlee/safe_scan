"""Orchestrates the pipeline: text -> clauses -> matches -> summary/risk
list/checklist/highlights. This is the one function the UI layer calls -
`analyze()` is the entire public surface of core, so the UI (or a future
CLI/web frontend) never needs to know about Aho-Corasick, TextRank, or the
pattern dictionary directly.
"""
from __future__ import annotations

from app.core.checklist import build_checklist
from app.core.dictionary import Dictionary, load_dictionary
from app.core.matcher import annotate_clauses, build_automaton, find_matches
from app.core.models import AnalysisResult, Clause, GRADE_ORDER, HighlightSpan, Match, PatternEntry, RiskItem
from app.core.segmenter import find_clause_id, split_clauses, split_sentences
from app.core.summarizer import summarize

_dictionary_cache: dict[tuple[str, ...], Dictionary] = {}
_automaton_cache: dict[tuple[str, ...], object] = {}

# Below this, a legal document's worth of distinct risk categories can't
# realistically fit - the summary starts silently dropping whole topics
# rather than just getting terser.
MIN_SUMMARY_LENGTH = 3


def _get_dictionary(doc_types: tuple[str, ...]) -> Dictionary:
    if doc_types not in _dictionary_cache:
        _dictionary_cache[doc_types] = load_dictionary(doc_types)
    return _dictionary_cache[doc_types]


def _get_automaton(doc_types: tuple[str, ...], dictionary: Dictionary):
    if doc_types not in _automaton_cache:
        _automaton_cache[doc_types] = build_automaton(dictionary.entries)
    return _automaton_cache[doc_types]


def _build_risk_list(clauses: list[Clause], entries_by_id: dict[str, PatternEntry]) -> list[RiskItem]:
    items: list[RiskItem] = []
    for clause in clauses:
        if not clause.grade:
            continue
        explains = []
        simple_explains = []
        laws = []
        top_entry: PatternEntry | None = None
        for entry_id in clause.matched_entry_ids:
            entry = entries_by_id.get(entry_id)
            if entry and entry.signal_type == "risk":
                explains.append(entry.explain)
                simple_explains.append(entry.simple_explain)
                laws.append(entry.related_law)
                if top_entry is None or GRADE_ORDER[entry.grade] > GRADE_ORDER[top_entry.grade]:
                    top_entry = entry
        excerpt = clause.text.strip()
        if len(excerpt) > 200:
            excerpt = excerpt[:200] + "..."
        title = f"{clause.label} · {top_entry.headline}" if top_entry and clause.label else clause.label
        simple_title = (
            f"{clause.label} · {top_entry.simple_explain}" if top_entry and clause.label else clause.label
        )
        items.append(
            RiskItem(
                clause_id=clause.id,
                grade=clause.grade,
                tags=clause.tags,
                title=title,
                simple_title=simple_title,
                excerpt=excerpt,
                explain=explains,
                simple_explain=simple_explains,
                related_law=sorted(set(laws)),
            )
        )
    items.sort(key=lambda it: (-GRADE_ORDER[it.grade], it.clause_id))
    return items


def _build_highlight_spans(
    clauses: list[Clause], matches: list[Match], entries_by_id: dict[str, PatternEntry]
) -> list[HighlightSpan]:
    """Highlights only the matched risk phrase itself, not its whole clause -
    a clause-wide span would light up nearly the entire document once most
    clauses have at least one match, making the highlighting meaningless.
    """
    spans = []
    for m in matches:
        entry = entries_by_id.get(m.entry_id)
        if entry is None or entry.signal_type != "risk":
            continue
        clause_id = find_clause_id(m.start, clauses)
        if clause_id is None:
            continue
        spans.append(HighlightSpan(start=m.start, end=m.end, clause_id=clause_id, grade=entry.grade))
    spans.sort(key=lambda s: s.start)
    return spans


def analyze(
    text: str,
    summary_length: int = 5,
    risk_weight_ratio: float = 0.6,
    doc_types: tuple[str, ...] = ("common",),
) -> AnalysisResult:
    dictionary = _get_dictionary(doc_types)
    automaton = _get_automaton(doc_types, dictionary)
    entries_by_id = dictionary.entries_by_id()

    clauses = split_clauses(text)
    sentences = split_sentences(text, clauses)
    matches = find_matches(text, automaton)
    annotate_clauses(clauses, matches, entries_by_id)

    clauses_by_id = {c.id: c for c in clauses}
    summary = summarize(sentences, clauses_by_id, max(summary_length, MIN_SUMMARY_LENGTH), risk_weight_ratio)
    risk_list = _build_risk_list(clauses, entries_by_id)
    checklist = build_checklist(clauses, dictionary.checklist_items, entries_by_id)
    highlight_spans = _build_highlight_spans(clauses, matches, entries_by_id)

    return AnalysisResult(
        summary=summary,
        risk_list=risk_list,
        checklist=checklist,
        full_text=text,
        highlight_spans=highlight_spans,
    )
