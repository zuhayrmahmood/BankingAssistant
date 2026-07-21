# Retrieval (RAG) architecture

The assistant grounds its conversation prompts in the product corpus under
`docs/products/` so it references **real** rates, fees, and eligibility instead
of inventing them. Retrieval lives in [`rag.py`](../rag.py) and is wired into
`BankingAssistantModule` in [`assistant.py`](../assistant.py).

## Pipeline

```
client profile
      │
      ▼
analyze_opportunities()      deterministic gap/cross-sell analysis
      │  ├─ opportunity notes ─────────────┐  (steer the LLM)
      │  └─ category filter                │
      ▼                                    │
metadata pre-filter          restrict search to relevant product families
      │                                    │
      ▼                                    │
hybrid fetch (RRF)           dense (embeddings) ⊕ BM25 lexical
      │                                    │
      ▼                                    │
cross-encoder rerank         precision on the shortlist (O(k))
      │                                    │
      ▼                                    ▼
   top-n docs ──────────▶ product_context ─▶ GenerateConversationPrompts
```

## Why each stage

| Stage | Purpose | Failure mode it fixes |
|-------|---------|-----------------------|
| **Metadata pre-filter** | Search within a product family, not the whole index | Keeps retrieval sub-linear at corpus scale |
| **Dense (embeddings)** | Semantic recall — paraphrase / intent matching | Misses exact-token distinctions |
| **BM25 lexical** | Weights distinguishing tokens ("Infinite", "Privilege") directly | Rescues near-duplicate products dense search collapses together |
| **RRF fusion** | Merges the two ranked lists without score calibration | — |
| **Cross-encoder rerank** | Joint query+doc attention over the shortlist | Precision on near-duplicates; O(k), independent of corpus size |
| **Contextual prefixing** | Prepends `[category] Title` before indexing | Distinguishing signal in the embedding vector itself |

The near-duplicate problem is the one to watch: embeddings alone rank
`cash_back_visa_infinite` above `cash_back_visa` for a "no annual fee cash back"
query; BM25 puts the right doc in the pool and the cross-encoder promotes it.

## Reranker backends

- `cross-encoder` — `cross-encoder/ms-marco-MiniLM-L-6-v2` via sentence-transformers.
  Best precision. Needs `requirements-rerank.txt` (torch stack).
- `llm` — pointwise 0–10 scoring by the Ollama chat model. No extra deps.
- `auto` (default) — cross-encoder if installed, else LLM.
- `none` — use the RRF fusion order directly.

## Graceful degradation

- Embedding model unreachable → dense index off, **BM25-only** hybrid.
- Cross-encoder not installed → **LLM reranker**.
- No reranker → **fusion order**.

Nothing here hard-crashes the assistant; each missing piece degrades one level.

## Caching / scale

Embeddings are cached on disk (`.rag_cache/`, keyed by model+content hash), so
re-indexing an unchanged corpus is free and only new/edited docs are re-embedded.
For a larger corpus, swap the in-memory cosine scan for an ANN index (FAISS /
HNSW) behind the same `HybridRetriever` interface — the metadata pre-filter and
rerank stages are unchanged.

## Usage

```bash
python main.py customer.json                              # auto reranker
python main.py customer.json --rerank-backend cross-encoder --raw
python main.py customer.json --rerank-backend llm         # no torch needed
python main.py customer.json --no-rag                     # retrieval off
```

`--raw` also prints the retrieved sources with their rerank scores.
```
