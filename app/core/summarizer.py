"""Extractive summarization: TextRank (PageRank over a sentence-similarity
graph), biased toward sentences that sit in risk-flagged clauses.

Sentence similarity uses the classic LexRank/TextRank word-overlap formula
(shared content words normalized by log sentence length) computed over
Kiwi morpheme lemmas, since raw Korean word overlap is unreliable for an
agglutinative language.

PageRank itself is a small hand-rolled power iteration rather than
networkx+scipy: our graphs are one document's worth of sentences (at most
a few hundred nodes), so a plain-Python implementation is plenty fast,
and it avoids pulling scipy's large footprint into the deployed image -
that was blowing past Render's free-tier 512MB memory limit.
"""
from __future__ import annotations

import math

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


def _pagerank(
    adjacency: dict[int, dict[int, float]],
    num_nodes: int,
    personalization: dict[int, float],
    alpha: float = 0.85,
    max_iter: int = 100,
    tol: float = 1.0e-6,
) -> dict[int, float]:
    """Weighted PageRank power iteration, matching networkx's pure-Python
    algorithm (stochastic normalization per node, dangling nodes and the
    teleport step both redistributed via `personalization`)."""
    nodes = range(num_nodes)
    total_p = sum(personalization.values()) or 1.0
    p = {n: personalization.get(n, 0.0) / total_p for n in nodes}

    out_weight = {n: sum(adjacency.get(n, {}).values()) for n in nodes}
    x = {n: 1.0 / num_nodes for n in nodes}

    for _ in range(max_iter):
        x_last = x
        x = dict.fromkeys(nodes, 0.0)
        dangling_sum = alpha * sum(x_last[n] for n in nodes if out_weight[n] == 0.0)
        for n in nodes:
            deg = out_weight[n]
            if deg == 0.0:
                continue
            share = alpha * x_last[n] / deg
            for nbr, w in adjacency.get(n, {}).items():
                x[nbr] += share * w
        for n in nodes:
            x[n] += dangling_sum * p[n] + (1.0 - alpha) * p[n]
        err = sum(abs(x[n] - x_last[n]) for n in nodes)
        if err < num_nodes * tol:
            break
    return x


def summarize(
    sentences: list[Sentence],
    clauses_by_id: dict[str, Clause],
    summary_length: int,
    risk_weight_ratio: float,
) -> list[SummarySentence]:
    if not sentences or summary_length <= 0:
        return []

    num_sentences = len(sentences)
    kiwi = get_kiwi()
    word_sets = [_content_words(kiwi, s.text) for s in sentences]

    adjacency: dict[int, dict[int, float]] = {i: {} for i in range(num_sentences)}
    for i in range(num_sentences):
        for j in range(i + 1, num_sentences):
            weight = _similarity(word_sets[i], word_sets[j])
            if weight > 0:
                adjacency[i][j] = weight
                adjacency[j][i] = weight

    uniform = {i: 1.0 for i in range(num_sentences)}
    base_scores = _pagerank(adjacency, num_sentences, uniform)

    personalization = {}
    for i, sent in enumerate(sentences):
        clause = clauses_by_id.get(sent.clause_id)
        grade = clause.grade if clause else None
        personalization[i] = RISK_WEIGHT_BY_GRADE.get(grade, BASELINE_WEIGHT)
    risk_scores = _pagerank(adjacency, num_sentences, personalization)

    ratio = max(0.0, min(1.0, risk_weight_ratio))
    final_scores = {
        i: (1 - ratio) * base_scores[i] + ratio * risk_scores[i] for i in range(num_sentences)
    }

    ranked = sorted(range(num_sentences), key=lambda i: final_scores[i], reverse=True)
    selected = ranked[:summary_length]

    # Keep at least one purely-important (non-risk-driven) sentence so the
    # summary doesn't turn into an all-risk list when the ratio is high.
    if summary_length >= 3:
        top_base = max(range(num_sentences), key=lambda i: base_scores[i])
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
