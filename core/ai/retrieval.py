"""Semantic retrieval with lightweight query-aware ranking for DocMitra."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Mapping

import numpy as np
from sentence_transformers import SentenceTransformer

from .knowledge_base import KnowledgeBase


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_MIN_SCORE = 0.25

# Small ranking adjustments. These are initial heuristics, not probabilities.
TAG_MATCH_BONUS = 0.08
NOT_FOUND_PENALTY = 0.05

# Maps common question wording to existing knowledge-base tags.
QUERY_TAG_TERMS: dict[str, tuple[str, ...]] = {
    "documents": (
        "document", "documents", "required document", "paperwork",
        "certificate", "certificates", "upload", "uploads",
        "file", "files", "photo", "signature",
    ),
    "bank": (
        "bank", "account", "dbt", "aadhaar-seeded", "aadhaar seeded",
    ),
    "amount": (
        "amount", "financial assistance", "scholarship amount",
        "money", "funding", "how much", "rupees", "inr",
    ),
    "eligibility": (
        "eligible", "eligibility", "qualify", "qualification",
        "who can apply", "criteria", "girl student", "girl students",
    ),
    "income": (
        "income", "family income", "annual income", "earnings",
    ),
    "renewal": (
        "renewal", "renew", "promotion certificate", "promoted",
    ),
    "dates": (
        "deadline", "last date", "due date", "application date",
        "important dates", "when to apply",
    ),
    "other_scholarship": (
        "other scholarship", "another scholarship",
        "multiple scholarships", "already receiving scholarship",
    ),
}


@dataclass(frozen=True)
class RetrievalResult:
    """A retrieved chunk with raw similarity and adjusted ranking score."""

    chunk: Mapping[str, Any]
    score: float
    ranking_score: float
    matched_tags: tuple[str, ...]

    @property
    def chunk_id(self) -> str:
        return str(self.chunk["chunk_id"])


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    """Load and reuse the embedding model."""
    return SentenceTransformer(MODEL_NAME)


@lru_cache(maxsize=8)
def _embed_chunks(chunk_texts: tuple[str, ...]) -> np.ndarray:
    """Generate and cache normalized chunk embeddings."""
    embeddings = _get_model().encode(
        list(chunk_texts),
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(embeddings, dtype=np.float32)


def _infer_query_tags(query: str) -> set[str]:
    """Infer relevant knowledge-base tags from common query wording."""
    normalized_query = re.sub(r"[^a-z0-9]+", " ", query.lower()).strip()
    matched_tags: set[str] = set()

    for tag, terms in QUERY_TAG_TERMS.items():
        for term in terms:
            normalized_term = re.sub(r"[^a-z0-9]+", " ", term.lower()).strip()

            if re.search(
                rf"\b{re.escape(normalized_term)}\b",
                normalized_query,
            ):
                matched_tags.add(tag)
                break

    return matched_tags


def _adjust_ranking_score(
    similarity: float,
    chunk: Mapping[str, Any],
    query_tags: set[str],
) -> tuple[float, tuple[str, ...]]:
    """Apply metadata adjustments while preserving evidence provenance."""
    raw_tags = chunk.get("tags", ())
    if not isinstance(raw_tags, (list, tuple, set)):
        raw_tags = ()

    chunk_tags = {
        str(tag).strip().lower()
        for tag in raw_tags
        if isinstance(tag, str)
    }

    matched_tags = tuple(sorted(chunk_tags & query_tags))
    ranking_score = similarity

    # Reward chunks whose tags match the query's inferred intent.
    if matched_tags:
        ranking_score += TAG_MATCH_BONUS

    # Give the dedicated document catalogue priority for document-list queries.
    if "documents" in query_tags and "documents" in chunk_tags:
        ranking_score += 0.10

    verification_status = str(
        chunk.get("verification_status", "unknown")
    ).lower()

    if verification_status == "not_found":
        ranking_score -= NOT_FOUND_PENALTY

    return ranking_score, matched_tags


def retrieve_chunks(
    query: str,
    knowledge_base: KnowledgeBase,
    *,
    top_k: int = 3,
    min_score: float | None = DEFAULT_MIN_SCORE,
) -> list[RetrievalResult]:
    """
    Retrieve chunks using semantic similarity and metadata-aware ranking.

    min_score filters on raw cosine similarity, not the adjusted score.
    Set min_score=None to disable similarity filtering.
    """
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise ValueError("top_k must be a positive integer.")

    if min_score is not None:
        if (
            isinstance(min_score, bool)
            or not isinstance(min_score, (int, float))
            or not np.isfinite(min_score)
            or not -1.0 <= min_score <= 1.0
        ):
            raise ValueError("min_score must be between -1 and 1, or None.")

    if not isinstance(query, str) or not query.strip():
        return []

    candidates: list[tuple[Mapping[str, Any], str]] = []

    for chunk in knowledge_base.iter_rag_chunks():
        text = chunk.get("text", "")

        if isinstance(text, str) and text.strip():
            candidates.append((chunk, text.strip()))

    if not candidates:
        return []

    chunk_texts = tuple(text for _, text in candidates)
    chunk_embeddings = _embed_chunks(chunk_texts)

    query_embedding = _get_model().encode(
        [query.strip()],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    query_vector = np.asarray(query_embedding[0], dtype=np.float32)
    similarities = chunk_embeddings @ query_vector
    query_tags = _infer_query_tags(query)

    ranked: list[RetrievalResult] = []

    for index, (chunk, _) in enumerate(candidates):
        raw_similarity = float(similarities[index])

        if min_score is not None and raw_similarity < min_score:
            continue

        adjusted_score, matched_tags = _adjust_ranking_score(
            raw_similarity,
            chunk,
            query_tags,
        )

        ranked.append(
            RetrievalResult(
                chunk=chunk,
                score=raw_similarity,
                ranking_score=adjusted_score,
                matched_tags=matched_tags,
            )
        )

    ranked.sort(
        key=lambda result: (
            -result.ranking_score,
            -result.score,
            result.chunk_id,
        )
    )

    return ranked[:top_k]
