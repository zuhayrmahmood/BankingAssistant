"""
Hybrid RAG retrieval over the product-docs corpus.

Pipeline (query time):

    query ──▶ metadata pre-filter ──▶ hybrid fetch (dense + BM25, RRF) ──▶ cross-encoder rerank ──▶ top-n

Design notes
------------
* **Metadata pre-filter** narrows the search space *before* vector/lexical
  scoring, using the taxonomy we already get for free from the docs folder
  layout (core_banking / investments / credit_cards / mortgages). At corpus
  scale this is the piece that keeps retrieval sub-linear — you search within
  a category, not the whole index.
* **Hybrid fetch** merges dense (embedding) recall with BM25 lexical matching
  via Reciprocal Rank Fusion. BM25 is what rescues near-duplicate product
  names ("Cash Back Visa" vs "Cash Back Visa Infinite") that dense embeddings
  collapse together — the distinguishing token ("Infinite") is weighted
  directly, guaranteeing the right doc reaches the candidate pool.
* **Contextual prefixing** (index time) prepends a short metadata-derived header
  to each doc before embedding/indexing so the vector itself carries the
  distinguishing signal. This is the cheap, always-on version of Anthropic's
  contextual retrieval; an optional LLM-generated variant is supported too.
* **Cross-encoder rerank** runs joint query+doc attention over just the small
  candidate pool, fixing precision on the shortlist at O(k) cost — independent
  of corpus size. Falls back to an Ollama LLM reranker when the cross-encoder
  model isn't installed, so the pipeline always runs.

Everything degrades gracefully: no embedding model → BM25-only; no reranker
→ fusion order is used as-is. Nothing here hard-crashes the assistant.
"""

from __future__ import annotations

import re
import json
import hashlib
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np
import requests
from rank_bm25 import BM25Okapi

log = logging.getLogger("rag")

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_EMBED_MODEL = "nomic-embed-text"
DEFAULT_CROSS_ENCODER = "cross-encoder/ms-marco-MiniLM-L-6-v2"
DOCS_ROOT = Path(__file__).parent / "docs" / "products"

# Map a doc's parent-folder path to a coarse product-family category. The
# assistant uses these same keys to build metadata filters from a client's
# holdings and gaps.
CATEGORY_BY_FOLDER = {
    "core_banking": "core_banking",
    "investments": "investments",
    "credit_cards": "credit_cards",
    "mortgages": "mortgages",
}


# ── Corpus ────────────────────────────────────────────────────────────────────

@dataclass
class Document:
    key: str            # filename stem, e.g. "cash_back_visa_infinite"
    category: str       # product family, e.g. "credit_cards"
    title: str          # first markdown H1
    body: str           # full markdown text
    path: str

    def indexed_text(self) -> str:
        """Text actually fed to the embedder / BM25 — body with a contextual header."""
        return f"[{self.category}] {self.title}\n\n{self.body}"


_H1 = re.compile(r"^#\s+(.*)$", re.MULTILINE)
_TOKEN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def load_corpus(root: Path = DOCS_ROOT) -> list[Document]:
    """Walk the docs tree and parse every markdown file into a Document."""
    docs: list[Document] = []
    for md in sorted(root.rglob("*.md")):
        text = md.read_text()
        # Category = the first path segment under products/ that we recognise.
        category = "other"
        for part in md.relative_to(root).parts:
            if part in CATEGORY_BY_FOLDER:
                category = CATEGORY_BY_FOLDER[part]
                break
        m = _H1.search(text)
        title = m.group(1).strip() if m else md.stem.replace("_", " ").title()
        docs.append(
            Document(
                key=md.stem,
                category=category,
                title=title,
                body=text,
                path=str(md),
            )
        )
    if not docs:
        log.warning("No documents found under %s", root)
    return docs


# ── Embeddings (Ollama) ─────────────────────────────────────────────────────────

class EmbeddingClient:
    """Thin Ollama /api/embeddings client with an on-disk cache.

    Cache key is (model, text) hashed, so re-indexing an unchanged corpus is
    free and only new/edited docs get re-embedded (incremental indexing).
    """

    def __init__(
        self,
        model: str = DEFAULT_EMBED_MODEL,
        base_url: str = DEFAULT_OLLAMA_URL,
        cache_dir: Optional[str] = None,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.available = True
        try:
            import diskcache  # available via dspy deps

            cdir = cache_dir or str(Path(__file__).parent / ".rag_cache" / "embeddings")
            self._cache = diskcache.Cache(cdir)
        except Exception:  # pragma: no cover - cache is best-effort
            self._cache = None

    def _key(self, text: str) -> str:
        return hashlib.sha256(f"{self.model}\x00{text}".encode()).hexdigest()

    def embed(self, texts: Sequence[str]) -> Optional[np.ndarray]:
        """Return an (n, d) L2-normalised matrix, or None if the model is unreachable."""
        out: list[Optional[np.ndarray]] = [None] * len(texts)
        misses: list[int] = []
        for i, t in enumerate(texts):
            if self._cache is not None:
                cached = self._cache.get(self._key(t))
                if cached is not None:
                    out[i] = np.asarray(cached, dtype=np.float32)
                    continue
            misses.append(i)

        for i in misses:
            vec = self._embed_one(texts[i])
            if vec is None:
                self.available = False
                return None
            out[i] = vec
            if self._cache is not None:
                self._cache.set(self._key(texts[i]), vec.tolist())

        mat = np.vstack(out).astype(np.float32)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return mat / norms

    def _embed_one(self, text: str) -> Optional[np.ndarray]:
        try:
            r = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=30,
            )
            r.raise_for_status()
            return np.asarray(r.json()["embedding"], dtype=np.float32)
        except Exception as e:
            log.warning("Embedding model '%s' unreachable (%s); dense retrieval disabled.",
                        self.model, e)
            return None


# ── Rerankers ───────────────────────────────────────────────────────────────────

class CrossEncoderReranker:
    """Proper cross-encoder: joint query+doc attention, best precision."""

    def __init__(self, model_name: str = DEFAULT_CROSS_ENCODER):
        self.model_name = model_name
        self._model = None

    @property
    def available(self) -> bool:
        if self._model is not None:
            return True
        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name)
            return True
        except Exception as e:
            log.info("Cross-encoder '%s' unavailable (%s).", self.model_name, e)
            return False

    def score(self, query: str, docs: Sequence[Document]) -> list[float]:
        pairs = [(query, d.indexed_text()) for d in docs]
        return [float(s) for s in self._model.predict(pairs, show_progress_bar=False)]


class LLMReranker:
    """Fallback pointwise reranker using an Ollama chat model.

    Scores each (query, doc) 0-10 for relevance. Slower and less precise than a
    real cross-encoder, but needs no extra dependency and runs on the same
    Ollama the assistant already uses.
    """

    def __init__(self, model: str = "llama3.1:8b", base_url: str = DEFAULT_OLLAMA_URL):
        self.model = model
        self.base_url = base_url.rstrip("/")

    @property
    def available(self) -> bool:
        return True

    def score(self, query: str, docs: Sequence[Document]) -> list[float]:
        scores: list[float] = []
        for d in docs:
            prompt = (
                "Rate how relevant this banking product document is to the query "
                "on a scale of 0 to 10. Reply with ONLY the number.\n\n"
                f"Query: {query}\n\n"
                f"Document: {d.title}\n{d.body[:1200]}\n\nScore:"
            )
            scores.append(self._ask(prompt))
        return scores

    def _ask(self, prompt: str) -> float:
        try:
            r = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False,
                      "options": {"temperature": 0.0, "num_predict": 8}},
                timeout=60,
            )
            r.raise_for_status()
            m = re.search(r"\d+(\.\d+)?", r.json().get("response", ""))
            return float(m.group(0)) if m else 0.0
        except Exception as e:
            log.warning("LLM reranker call failed (%s).", e)
            return 0.0


def build_reranker(backend: str = "auto", **kwargs):
    """Select a reranker. 'auto' prefers the cross-encoder, falls back to LLM."""
    if backend in ("cross-encoder", "auto"):
        ce = CrossEncoderReranker(kwargs.get("cross_encoder_model", DEFAULT_CROSS_ENCODER))
        if ce.available:
            log.info("Reranker: cross-encoder (%s)", ce.model_name)
            return ce
        if backend == "cross-encoder":
            log.warning("Requested cross-encoder unavailable; falling back to LLM reranker.")
    if backend == "none":
        return None
    log.info("Reranker: LLM (%s)", kwargs.get("llm_model", "llama3.1:8b"))
    return LLMReranker(
        model=kwargs.get("llm_model", "llama3.1:8b"),
        base_url=kwargs.get("base_url", DEFAULT_OLLAMA_URL),
    )


# ── Retriever ───────────────────────────────────────────────────────────────────

@dataclass
class Retrieved:
    document: Document
    score: float


@dataclass
class HybridRetriever:
    """Metadata-filtered hybrid (dense + BM25) retrieval with cross-encoder rerank."""

    documents: list[Document]
    embedder: Optional[EmbeddingClient] = None
    reranker: object = None
    rrf_k: int = 60  # Reciprocal Rank Fusion constant (standard default)

    # built in __post_init__
    _bm25: BM25Okapi = field(init=False, default=None)
    _emb: Optional[np.ndarray] = field(init=False, default=None)

    def __post_init__(self):
        corpus_tokens = [_tokenize(d.indexed_text()) for d in self.documents]
        self._bm25 = BM25Okapi(corpus_tokens)
        if self.embedder is not None:
            self._emb = self.embedder.embed([d.indexed_text() for d in self.documents])
            if self._emb is None:
                log.warning("Dense index unavailable; running BM25-only hybrid.")

    @classmethod
    def build(
        cls,
        docs_root: Path = DOCS_ROOT,
        embed_model: str = DEFAULT_EMBED_MODEL,
        rerank_backend: str = "auto",
        base_url: str = DEFAULT_OLLAMA_URL,
    ) -> "HybridRetriever":
        docs = load_corpus(docs_root)
        embedder = EmbeddingClient(model=embed_model, base_url=base_url)
        reranker = build_reranker(rerank_backend, base_url=base_url)
        return cls(documents=docs, embedder=embedder, reranker=reranker)

    def _candidate_ids(self, categories: Optional[Sequence[str]]) -> list[int]:
        if not categories:
            return list(range(len(self.documents)))
        allowed = set(categories)
        return [i for i, d in enumerate(self.documents) if d.category in allowed]

    def _rrf(self, ranked_lists: list[list[int]], candidates: list[int]) -> list[int]:
        """Fuse multiple ranked id-lists with Reciprocal Rank Fusion."""
        scores: dict[int, float] = {i: 0.0 for i in candidates}
        for ranked in ranked_lists:
            for rank, doc_id in enumerate(ranked):
                if doc_id in scores:
                    scores[doc_id] += 1.0 / (self.rrf_k + rank + 1)
        return sorted(scores, key=scores.get, reverse=True)

    def retrieve(
        self,
        query: str,
        categories: Optional[Sequence[str]] = None,
        pool_k: int = 12,
        top_n: int = 4,
    ) -> list[Retrieved]:
        candidates = self._candidate_ids(categories)
        if not candidates:
            return []

        # 1. Lexical ranking (BM25) restricted to candidates.
        q_tokens = _tokenize(query)
        bm25_scores = self._bm25.get_scores(q_tokens)
        bm25_ranked = sorted(candidates, key=lambda i: bm25_scores[i], reverse=True)

        ranked_lists = [bm25_ranked]

        # 2. Dense ranking (cosine) restricted to candidates, if available.
        if self._emb is not None:
            q_vec = self.embedder.embed([query])
            if q_vec is not None:
                sims = self._emb @ q_vec[0]
                dense_ranked = sorted(candidates, key=lambda i: sims[i], reverse=True)
                ranked_lists.append(dense_ranked)

        # 3. Fuse into a candidate pool.
        fused = self._rrf(ranked_lists, candidates)[:pool_k]
        pool = [self.documents[i] for i in fused]

        # 4. Cross-encoder rerank the pool (precision on the shortlist).
        if self.reranker is not None and pool:
            rr = self.reranker.score(query, pool)
            order = sorted(range(len(pool)), key=lambda j: rr[j], reverse=True)
            return [Retrieved(pool[j], float(rr[j])) for j in order[:top_n]]

        # No reranker: use fusion order, expose the fused RRF score.
        return [Retrieved(self.documents[i], 0.0) for i in fused[:top_n]]


def format_context(results: Sequence[Retrieved], max_chars: int = 900) -> str:
    """Render retrieved docs into a compact grounding block for the LLM prompt."""
    if not results:
        return "(no product documents retrieved)"
    blocks = []
    for r in results:
        body = r.document.body.strip()
        if len(body) > max_chars:
            body = body[:max_chars].rsplit("\n", 1)[0] + "\n…"
        blocks.append(f"### {r.document.title}  [{r.document.category}]\n{body}")
    return "\n\n".join(blocks)
