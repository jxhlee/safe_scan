"""Splits raw document text into clauses (조항) and sentences.

Clause detection looks for "제N조" style markers, which cover the vast
majority of Korean 이용약관/개인정보처리방침 documents. When no such markers
are found (e.g. a plain-paragraph policy), it falls back to blank-line
paragraph splitting, and finally to treating the whole document as one
clause.
"""
from __future__ import annotations

import re
from functools import lru_cache

from kiwipiepy import Kiwi

from app.core.models import Clause, Sentence

CLAUSE_MARKER_RE = re.compile(r"제\s*\d+\s*조(?:의\s*\d+)?(?:\s*\([^)\n]{0,30}\))?")
CLAUSE_NUMBER_RE = re.compile(r"제\s*\d+\s*조(?:의\s*\d+)?")
PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")


@lru_cache(maxsize=1)
def get_kiwi() -> Kiwi:
    # Dialect and typo-correction dictionaries roughly double Kiwi's memory
    # footprint (~540MB -> ~310MB without them) and add nothing for the
    # standard-register, correctly-spelled Korean these documents are
    # written in - dropping them was the difference between fitting in
    # Render's free 512MB tier and not.
    return Kiwi(load_multi_dict=False, load_typo_dict=False)


def _clause_spans(text: str) -> list[tuple[str, int, int]]:
    markers = list(CLAUSE_MARKER_RE.finditer(text))
    if markers:
        spans: list[tuple[str, int, int]] = []
        if markers[0].start() > 0 and text[: markers[0].start()].strip():
            spans.append(("전문", 0, markers[0].start()))
        for i, m in enumerate(markers):
            end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
            short_label = CLAUSE_NUMBER_RE.match(m.group()).group()
            spans.append((short_label, m.start(), end))
        return spans

    paragraphs = [
        (m.start(), m.end()) for m in re.finditer(r"[^\n]+(?:\n(?!\s*\n)[^\n]+)*", text)
    ]
    paragraphs = [p for p in paragraphs if text[p[0] : p[1]].strip()]
    if len(paragraphs) > 1:
        return [(f"문단{i+1}", s, e) for i, (s, e) in enumerate(paragraphs)]

    return [("전문", 0, len(text))]


def split_clauses(text: str) -> list[Clause]:
    clauses = []
    for idx, (label, start, end) in enumerate(_clause_spans(text)):
        clause_id = f"c{idx}"
        clauses.append(
            Clause(id=clause_id, text=text[start:end], start=start, end=end, label=label)
        )
    return clauses


def split_sentences(text: str, clauses: list[Clause]) -> list[Sentence]:
    kiwi = get_kiwi()
    sentences: list[Sentence] = []
    for sent in kiwi.split_into_sents(text):
        if not sent.text.strip():
            continue
        clause_id = find_clause_id(sent.start, clauses)
        sentences.append(
            Sentence(text=sent.text, start=sent.start, end=sent.end, clause_id=clause_id)
        )
    return sentences


def find_clause_id(offset: int, clauses: list[Clause]) -> str | None:
    for clause in clauses:
        if clause.start <= offset < clause.end:
            return clause.id
    return clauses[-1].id if clauses else None
