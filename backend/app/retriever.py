"""Retrieval: paragraph chunks embedded into a FAISS inner-product index.

TF-IDF keeps the prototype free of model downloads and API keys. The embedder is a
small interface, so a neural embedding model can replace it without touching the index.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import faiss
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from .kb import Article


class Embedder(Protocol):
    def fit(self, texts: list[str]) -> "Embedder": ...
    def embed(self, texts: list[str]) -> np.ndarray: ...


class TfidfEmbedder:
    def __init__(self) -> None:
        self._vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english")

    def fit(self, texts: list[str]) -> "TfidfEmbedder":
        self._vectorizer.fit(texts)
        return self

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors = self._vectorizer.transform(texts).toarray().astype("float32")
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        # A query with no known words has a zero vector; leave it as zeros (score 0) rather than dividing by zero.
        return np.divide(vectors, norms, out=np.zeros_like(vectors), where=norms > 0)


@dataclass(frozen=True)
class Hit:
    article: Article
    score: float


class Retriever:
    def __init__(self, articles: list[Article], embedder: Embedder | None = None) -> None:
        self.articles = articles
        # Each chunk is one paragraph prefixed with its article title, so titles count toward every chunk.
        self._chunks: list[tuple[int, str]] = [
            (i, f"{article.title}. {paragraph}")
            for i, article in enumerate(articles)
            for paragraph in article.paragraphs()
        ]
        texts = [text for _, text in self._chunks]
        self._embedder = (embedder or TfidfEmbedder()).fit(texts)
        vectors = self._embedder.embed(texts)
        self._index = faiss.IndexFlatIP(vectors.shape[1])
        self._index.add(vectors)

    def search(self, query: str, k: int = 3) -> list[Hit]:
        """Top-k articles by their best-matching chunk (cosine similarity)."""
        query_vector = self._embedder.embed([query])
        scores, ids = self._index.search(query_vector, min(len(self._chunks), k * 8))
        best: dict[int, float] = {}
        for score, chunk_id in zip(scores[0], ids[0]):
            if chunk_id < 0:
                continue
            article_id = self._chunks[chunk_id][0]
            best[article_id] = max(best.get(article_id, 0.0), float(score))
        ranked = sorted(best.items(), key=lambda item: item[1], reverse=True)[:k]
        return [Hit(self.articles[i], score) for i, score in ranked if score > 0]
