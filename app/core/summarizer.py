"""Extractive summarization: TextRank (PageRank over a sentence-similarity
graph), biased toward sentences that sit in risk-flagged clauses.

Sentence similarity uses the classic LexRank/TextRank word-overlap formula
(shared content words normalized by log sentence length) computed over
Kiwi morpheme lemmas, since raw Korean word overlap is unreliable for an
agglutinative language.
"""
from __future__ import annotations

import math

import networkx as nx

from app.core.models import Clause, Sentence, SummarySentence
from app.core.segmenter import CLAUSE_MARKER_RE, get_kiwi

CONTENT_TAGS = {"NNG", "NNP", "NNB", "VV", "VA", "XR", "SL", "SN"}
RISK_WEIGHT_BY_GRADE = {"높음": 3.0, "중간": 2.0, "낮음": 1.0}
BASELINE_WEIGHT = 0.5


def _content_words(kiwi, text: str) -> set[str]:
    return {t.form for t in kiwi.tokenize(text) if t.tag in CONTENT_TAGS}


def _similarity(words_a: set[str], words_b: set[str]) -> float:
    if not words_a or not words_b:
        return 0.0
    common = len(words_a & words_b)
    if common == 0:
        return 0.0
    denom = math.log(len(words_a) + 1) + math.log(len(words_b) + 1)
    return common / denom if denom > 0 else 0.0


def summarize(
    sentences: list[Sentence],
    clauses_by_id: dict[str, Clause],
    summary_length: int,
    risk_weight_ratio: float,
) -> list[SummarySentence]:
    if not sentences or summary_length <= 0:
        return []

    kiwi = get_kiwi()
    word_sets = [_content_words(kiwi, s.text) for s in sentences]

    graph = nx.Graph()
    graph.add_nodes_from(range(len(sentences)))
    for i in range(len(sentences)):
        for j in range(i + 1, len(sentences)):
            weight = _similarity(word_sets[i], word_sets[j])
            if weight > 0:
                graph.add_edge(i, j, weight=weight)

    base_scores = nx.pagerank(graph, weight="weight")

    personalization = {}
    for i, sent in enumerate(sentences):
        clause = clauses_by_id.get(sent.clause_id)
        grade = clause.grade if clause else None
        personalization[i] = RISK_WEIGHT_BY_GRADE.get(grade, BASELINE_WEIGHT)
    total = sum(personalization.values())
    personalization = {k: v / total for k, v in personalization.items()}

    risk_scores = nx.pagerank(graph, weight="weight", personalization=personalization)

    ratio = max(0.0, min(1.0, risk_weight_ratio))
    final_scores = {
        i: (1 - ratio) * base_scores[i] + ratio * risk_scores[i] for i in range(len(sentences))
    }

    ranked = sorted(range(len(sentences)), key=lambda i: final_scores[i], reverse=True)
    selected = ranked[:summary_length]

    # Keep at least one purely-important (non-risk-driven) sentence so the
    # summary doesn't turn into an all-risk list when the ratio is high.
    if summary_length >= 3:
        top_base = max(range(len(sentences)), key=lambda i: base_scores[i])
        if top_base not in selected:
            selected[-1] = top_base

    ordered = sorted(set(selected), key=lambda i: sentences[i].start)

    result = []
    for i in ordered:
        sent = sentences[i]
        clause = clauses_by_id.get(sent.clause_id)
        is_risk_boosted = bool(clause and clause.grade)
        display_text = sent.text.strip()
        marker = CLAUSE_MARKER_RE.match(display_text)
        if marker:
            display_text = display_text[marker.end():].strip()
        result.append(
            SummarySentence(
                text=display_text,
                clause_id=sent.clause_id,
                is_risk_boosted=is_risk_boosted,
                score=round(final_scores[i], 4),
            )
        )
    return result
