"""Aho-Corasick multi-pattern matching and clause-level risk grouping."""
from __future__ import annotations

import ahocorasick

from app.core.models import Clause, GRADE_ORDER, Match, PatternEntry


def build_automaton(entries: list[PatternEntry]) -> ahocorasick.Automaton:
    """One trie over every phrase from every pattern entry (risk + safe)."""
    phrase_to_entry_ids: dict[str, list[str]] = {}
    for entry in entries:
        for phrase in entry.patterns:
            phrase_to_entry_ids.setdefault(phrase, []).append(entry.id)

    automaton = ahocorasick.Automaton()
    for phrase, entry_ids in phrase_to_entry_ids.items():
        automaton.add_word(phrase, (phrase, tuple(entry_ids)))
    automaton.make_automaton()
    return automaton


def find_matches(text: str, automaton: ahocorasick.Automaton) -> list[Match]:
    """Single pass over the document text finds every pattern hit."""
    matches: list[Match] = []
    for end_index, (phrase, entry_ids) in automaton.iter(text):
        start_index = end_index - len(phrase) + 1
        for entry_id in entry_ids:
            matches.append(Match(entry_id=entry_id, start=start_index, end=end_index + 1, text=phrase))
    return matches


def annotate_clauses(
    clauses: list[Clause], matches: list[Match], entries_by_id: dict[str, PatternEntry]
) -> None:
    """Groups matches into their containing clause and derives grade/tags.

    A clause's grade is the highest-severity risk match inside it; tags are
    the union of matched risk categories. Mutates clauses in place.
    """
    for clause in clauses:
        clause_matches = [m for m in matches if clause.start <= m.start < clause.end]

        entry_ids: list[str] = []
        seen_ids: set[str] = set()
        risk_grades: list[str] = []
        tags: set[str] = set()

        for m in clause_matches:
            entry = entries_by_id.get(m.entry_id)
            if entry is None:
                continue
            if m.entry_id not in seen_ids:
                entry_ids.append(m.entry_id)
                seen_ids.add(m.entry_id)
            if entry.signal_type == "risk":
                risk_grades.append(entry.grade)
                tags.add(entry.category)

        clause.matched_entry_ids = entry_ids
        clause.tags = sorted(tags)
        clause.grade = max(risk_grades, key=lambda g: GRADE_ORDER[g]) if risk_grades else None
