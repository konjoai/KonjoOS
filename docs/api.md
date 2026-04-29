# API Reference

Interactive docs available at `http://localhost:8000/docs` after `konjoai serve`.

## Endpoints

### `POST /ingest`

Ingest a file or directory into the vector store.

**Request**
```json
{
  "path": "/path/to/docs",
  "strategy": "recursive",
  "chunk_size": 512,
  "overlap": 64
}
```

**Response**
```json
{
  "chunks_indexed": 42,
  "sources_processed": 3,
  "chunks_deduplicated": 2
}
```

---

### `POST /query`

Run the full RAG pipeline.

**Request**
```json
{
  "question": "What is the refund policy?",
  "top_k": 5,
  "use_hyde": false,
  "use_crag": false,
  "use_self_rag": false,
  "use_decomposition": false,
  "use_graph_rag": false
}
```

**Response** (condensed)
```json
{
  "answer": "...",
  "sources": [{"source": "doc.md", "content_preview": "...", "score": 0.95}],
  "model": "gpt-4o-mini",
  "usage": {"total_tokens": 350},
  "intent": "retrieval",
  "cache_hit": false,
  "telemetry": {"route": 1, "hybrid_search": 45, "rerank": 12, "generate": 820}
}
```

---

### `POST /query/stream`

Stream tokens via Server-Sent Events. Same request body as `/query`.

---

### `POST /agent/query`

Run the bounded ReAct agent loop.

**Request**
```json
{
  "question": "Find all compliance requirements",
  "top_k": 5,
  "max_steps": 5
}
```

---

### `GET /health`

```json
{"status": "ok", "vector_count": 10000, "bm25_built": true}
```

---

### `GET /metrics`

Prometheus exposition format. Requires `OTEL_ENABLED=true` and `pip install prometheus-client`.

---

### `POST /eval`

RAGAS evaluation. Requires `pip install ragas datasets`.

**Request**
```json
{
  "questions": ["What is X?"],
  "answers": ["X is Y."],
  "contexts": [["context chunk 1", "context chunk 2"]],
  "ground_truths": ["X is Y."]
}
```

---

### `POST /vectro/pipeline`

Run the Vectro embedding compression pipeline (NF4 / PQ / INT8).
