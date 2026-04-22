# Kyro — Master Plan

> **ቆንጆ** — Beautiful. **根性** — Fighting spirit. **康宙** — Health of the universe. **खोजो** — Search and discover.
> *Make it konjo — build, ship, rest, repeat.*

**Strategic documents:**
- [`KORE_PLAN.md`](KORE_PLAN.md) — full market analysis, sprint roadmap, licensing recommendation.
- [`kyro_production_plan.md`](kyro_production_plan.md) — production execution plan and operational rollout notes.

---

## Current State: Sprint 15 Complete (v0.8.5)

- **Tests:** 464 passing, 0 failing
- **Branch:** `main`
- **Stack:** FastAPI + HyDE + ColBERT + hybrid search + RAGAS + Vectro bridge + streaming + semantic cache + adaptive chunking + CRAG + Self-RAG + Query Decomposition + Agentic RAG + **GraphRAG (Sprint 15)**

---

## Active Sprint Delta: Sprint 14 — Agentic RAG Foundation (v0.8.0, Wave 1)

**Goal:** Add a bounded ReAct loop with tool-use traceability and expose it via `/agent/query`.

### Implementation Checklist — Sprint 14 (Wave 1)

| # | File | Change | Status |
|---|---|---|---|
| 1 | `konjoai/agent/react.py` | Add `RAGAgent`, `ToolRegistry`, action parser, bounded ReAct loop | ✅ |
| 2 | `konjoai/agent/__init__.py` | Export `RAGAgent`, `AgentResult`, `AgentStep` | ✅ |
| 3 | `konjoai/api/routes/agent.py` | Add `POST /agent/query` endpoint + telemetry wrapping | ✅ |
| 4 | `konjoai/api/app.py` | Register `agent` router | ✅ |
| 5 | `tests/unit/test_agentic.py` | Add agent core tests (retrieve/finish, parser fallback, max-step guard) | ✅ |
| 6 | `tests/unit/test_agent_route.py` | Add route tests for telemetry on/off and response contract | ✅ |
| 7 | `konjoai/api/routes/agent.py` + `tests/unit/test_agent_route.py` | Enforce `request_timeout_seconds` on `/agent/query`; return HTTP 504 on timeout | ✅ |

### Sprint 14 Gate (Wave 1)

1. Agent loop is bounded (`max_steps`) and never runs unbounded. ✅
2. Tool action trace is returned in API response (`steps[]`). ✅
3. Endpoint preserves K3/K6 behavior (telemetry optional, no breaking change to `/query`). ✅
4. Focused unit tests pass for new agent core and route. ✅
5. Endpoint timeout is enforced and returns deterministic 504 on overrun. ✅

---

## Completed Sprint: Sprint 15 — Lightweight GraphRAG (v0.8.5)

**Goal:** Group semantically related retrieved chunks into communities via Louvain-style community detection. Surface one representative per community to the reranker — reducing near-duplicate context while preserving topical diversity. Feature-flagged off by default (K3).

### Implementation Checklist — Sprint 15

| # | File | Change | Status |
|---|---|---|---|
| 1 | `konjoai/retrieve/graph_rag.py` | `EntityGraph` (Jaccard-weighted graph), `GraphRAGRetriever` (community detection via `greedy_modularity_communities`), `CommunityContext`, `GraphRAGResult`, singleton factory | ✅ |
| 2 | `konjoai/config.py` | `enable_graph_rag=False`, `graph_rag_max_communities=5`, `graph_rag_similarity_threshold=0.3` | ✅ |
| 3 | `konjoai/api/schemas.py` | `QueryRequest.use_graph_rag: bool = False`; `QueryResponse.graph_rag_communities: list[str] \| None = None` | ✅ |
| 4 | `konjoai/api/routes/query.py` | Step 3c injection (after hybrid retrieval, before CRAG); `x-use-graph-rag` header support; `graph_rag_enabled` K3 gate | ✅ |
| 5 | `requirements.txt` | `networkx>=3.2` | ✅ |
| 6 | `tests/unit/test_graph_rag.py` | 37 tests covering `_tokenize`, `EntityGraph`, `CommunityContext`, `GraphRAGResult`, `GraphRAGRetriever`, singleton, and K3 route gate (disabled / settings / body / header) | ✅ |
| 7 | Existing test stubs (4 files) | Added `enable_graph_rag`, `graph_rag_max_communities`, `graph_rag_similarity_threshold` to `_SettingsStub` dataclasses | ✅ |

### Sprint 15 Gate Results

1. `greedy_modularity_communities` with Jaccard edges — deterministic, no extra embedding cost. ✅
2. K3: disabled by default; graceful networkx-absent fallback returns raw hybrid results. ✅
3. K6: `use_graph_rag=False` default; `graph_rag_communities=None` default — no breaking change. ✅
4. `464 passed, 0 failed` (up from 427 — +37 tests). ✅

---

## Completed Sprints

| Sprint | Version | Focus | Status |
|---|---|---|---|
| 1–5 | v0.2.5 | Foundation: telemetry, routing, HyDE, ColBERT, RAGAS | ✅ |
| 6 | v0.3.0 | Semantic cache: sub-5ms cached responses | ✅ 226 tests |

---

## Active Sprint: Sprint 7 — Adapter Architecture

**Goal:** Sub-5ms cached responses. Eliminate LLM cost for near-duplicate queries (20–40% of prod traffic).

### Implementation Checklist — Sprint 7

| # | File | Change | Status |
|---|---|---|---|
| 1 | `konjoai/adapters/__init__.py` | Package init exporting protocols | ✅ |
| 2 | `konjoai/adapters/base.py` | `VectorStoreAdapter`, `EmbedderAdapter`, `GeneratorAdapter`, `RetrieverAdapter` protocols | ✅ |
| 3 | `tests/unit/test_adapters.py` | Protocol conformance + duck-typing tests | ✅ |

### Sprint 7 Gates

1. All existing 226 tests still pass.
2. `VectorStoreAdapter`, `EmbedderAdapter`, `GeneratorAdapter`, `RetrieverAdapter` protocols defined.
3. Existing `get_store()`, `get_encoder()`, `get_generator()` singletons satisfy the protocols (checked via `isinstance` + `runtime_checkable`).

---

## Phase 1 → Phase 2: Sprint 10 Complete — Adaptive Chunking (v0.5.5)

### Implementation Checklist — Sprint 10 (Full Deliverables)

| # | File | Change | Status |
|---|---|---|---|
| 1 | `konjoai/ingest/adaptive_chunker.py` | `QueryComplexityScorer`, `MultiGranularityChunker`, `AdaptiveRetriever` | ✅ |
| 2 | `konjoai/ingest/chunkers.py` | `SemanticSplitter` — cosine boundary detection via buffered sentence embedding | ✅ |
| 3 | `konjoai/ingest/chunkers.py` | `LateChunker` — Jina-style post-embedding split (single-batch full-doc encoding) | ✅ |
| 4 | `konjoai/ingest/chunkers.py` | `get_chunker()` updated to support `"semantic"` and `"late"` strategies | ✅ |
| 5 | `konjoai/retrieve/router.py` | `ChunkComplexity` enum (SIMPLE/MEDIUM/COMPLEX) + `CHUNK_SIZE_MAP` | ✅ |
| 6 | `konjoai/retrieve/router.py` | `classify_chunk_complexity()` — maps query → `(ChunkComplexity, chunk_size)` | ✅ |
| 7 | `konjoai/config.py` | `chunk_strategy` supports `"recursive"\|"sentence_window"\|"semantic"\|"late"` | ✅ |
| 8 | `konjoai/config.py` | `semantic_split_threshold`, `late_chunk_threshold` settings added | ✅ |
| 9 | `scripts/ablation_chunking.py` | Ablation harness — all 4 strategies, proxy metrics, JSON to `evals/runs/` | ✅ |
| 10 | `tests/unit/test_semantic_splitter.py` | 32 tests — construction, splitting, factory | ✅ |
| 11 | `tests/unit/test_late_chunker.py` | 33 tests — construction, splitting, metadata, factory | ✅ |
| 12 | `tests/unit/test_router.py` | 28 new tests — `ChunkComplexity`, `CHUNK_SIZE_MAP`, `classify_chunk_complexity` | ✅ |

**Sprint 10 Gate Results:** 423 passed, 0 failed (up from 329 — +94 tests)

### Implementation Checklist — Sprint 11: CRAG

| # | File | Change | Status |
|---|---|---|---|
| 1 | `konjoai/retrieve/crag.py` | Replace legacy pipeline with `CRAGEvaluator`: normalized scores, `CORRECT/AMBIGUOUS/INCORRECT`, fallback stub, ambiguous refinement | ✅ |
| 2 | `konjoai/config.py` | Add `crag_correct_threshold`, `crag_ambiguous_threshold` | ✅ |
| 3 | `konjoai/api/schemas.py` + `konjoai/api/routes/query.py` | Add `QueryRequest.use_crag`; support `use_crag` header; emit `crag_scores`, `crag_classification`, `crag_refinement_triggered` | ✅ |
| 4 | `tests/unit/test_crag.py` + `tests/unit/test_query_crag_route.py` | Add Sprint 11 contract tests for quality bands, fallback, refinement, and `/query` opt-in behavior | ✅ |

### Implementation Checklist — Sprint 12: Self-RAG

| # | File | Change | Status |
|---|---|---|---|
| 1 | `konjoai/retrieve/self_rag.py` | `SelfRAGOrchestrator` iterative loop + `SelfRAGCritic` + `SelfRAGTokens` + refined retrieval callback contract | ✅ |
| 2 | `konjoai/config.py` | `enable_self_rag`, `self_rag_max_iterations=3` | ✅ |
| 3 | `konjoai/api/schemas.py` + `konjoai/api/routes/query.py` | `QueryRequest.use_self_rag` opt-in + Self-RAG telemetry fields (`self_rag_iteration_scores`, `self_rag_total_tokens`) | ✅ |
| 4 | `tests/unit/test_self_rag.py` + `tests/unit/test_query_self_rag_route.py` | Critique/orchestrator unit tests + `/query` opt-in route tests (body/header/default-off) | ✅ |

### Implementation Checklist — Sprint 13: Query Decomposition + Multi-Step Retrieval

| # | File | Change | Status |
|---|---|---|---|
| 1 | `konjoai/retrieve/decomposition.py` | Added `QueryDecomposer` (LLM JSON output + deterministic fallback), `ParallelRetriever`, and `AnswerSynthesizer` | ✅ |
| 2 | `konjoai/config.py` | Added `enable_query_decomposition` and `decomposition_max_sub_queries` guards | ✅ |
| 3 | `konjoai/api/schemas.py` | Added `QueryRequest.use_decomposition` and decomposition response fields | ✅ |
| 4 | `konjoai/api/routes/query.py` | Added body/header opt-in, parallel fan-out retrieval, sub-answer synthesis, and decomposition telemetry | ✅ |
| 5 | `tests/unit/test_decomposition.py` + `tests/unit/test_query_decomposition_route.py` | Added decomposition unit coverage and `/query` opt-in route behavior tests | ✅ |

---

## Sprint Roadmap Summary (Production Release Plan)

| Sprint | Version | Phase | Focus | Gate |
|---|---|---|---|---|
| 1–5 | v0.2.5 | — | Foundation: telemetry, routing, HyDE, ColBERT, RAGAS | ✅ 205 tests |
| 6 | v0.3.0 | — | Semantic cache (sub-5ms cached responses) | ✅ 226 tests |
| **7** | **v0.3.5** | **P1** | **Adapter architecture (swap any backend)** | **✅ Active** |
| 8 | v0.4.0 | P1 | Async pipeline + connection pooling (3× throughput) | ⬜ |
| 9 | v0.5.0 | P1 | Streaming SSE (already exists; harden + OTel hooks) | ⬜ |
| 10 | v0.5.5 | P2 | Adaptive chunking (SemanticSplitter, LateChunker, ChunkComplexity router, ablation harness) | ✅ 427 tests |
| 11 | v0.6.0 | P2 | CRAG — retrieval critique + corrective fallback | ✅ |
| 12 | v0.7.0 | P2 | Self-RAG — reflection tokens + critique loop | ✅ |
| 13 | v0.7.5 | P3 | Query decomposition (multi-hop fan-out) | ✅ |
| 14 | v0.8.0 | P3 | Agentic RAG — ReAct loop | ✅ |
| 15 | v0.8.5 | P3 | Lightweight GraphRAG (NetworkX + Louvain) | ✅ 464 tests |
| 16 | v0.8.7 | P4 | OTel + Prometheus + Grafana | ⬜ |
| 17 | v0.9.0 | P4 | Multi-tenancy + JWT | ⬜ |
| 18 | v0.9.5 | P4 | Auth + rate limiting | ⬜ |
| 19 | v0.9.8 | P5 | Python SDK + MCP server | ⬜ |
| 20 | v1.0.0 | P5 | Helm chart + PyPI + Docs site | ⬜ |

---

## The Seven Konjo Invariants

| # | Invariant | Contract |
|---|---|---|
| K1 | No silent failures | Every component returns or raises. No `except: pass`. |
| K2 | Telemetry on every step | `timed()` wraps all hot-path calls. Latency in every response. |
| K3 | Graceful degradation | Vectro unavailable → float32. RAGAS absent → 501. Cache disabled → transparent fallthrough. |
| K4 | Dtype contracts | Encoder: `float32`. Vectro: `float32` in/out. Qdrant: `float32`. Assert, never assume. |
| K5 | Zero new hard deps | Cache uses `collections.OrderedDict` + `numpy` (already required). |
| K6 | Backward-compatible API | New fields are optional with sensible defaults. |
| K7 | Reproducible evals | Every run → `evals/runs/<timestamp>_<name>/`. Never overwrite. |

---

## Hard Stops

- Tests failing from a previous step.
- Cache returns stale data after ingest (invalidation must be verified in tests).
- Dtype assertion fails at any component boundary.
- NaN/Inf passed to Qdrant.
- Audit log (Sprint 11) contains raw question text (PII leak, OWASP violation).
- p95 query latency regression > 5% from current baseline.

---

*Owner: wesleyscholl / Konjo AI Research*
*See KORE_PLAN.md for full strategic roadmap, market analysis, and licensing recommendation.*
