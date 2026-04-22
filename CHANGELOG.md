# Changelog

All notable changes to KonjoOS are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased] — Sprint 15: Lightweight GraphRAG Community Detection (v0.8.5)

### Added
- `konjoai/retrieve/graph_rag.py` — `GraphRAGRetriever` using NetworkX community detection:
  - `_tokenize()` — stopword-stripped, lowercased token sets for Jaccard similarity
  - `EntityGraph` — Jaccard similarity graph construction (O(n²), n≤20 chunk limit)
  - `CommunityContext` — community label + member content container
  - `GraphRAGResult` — final retrieval result with community summaries
  - `GraphRAGRetriever` — full retriever: build graph → Louvain communities → top-K by relevance
  - `get_graph_rag_retriever()` — singleton factory (feature-flagged off by default)
- `tests/unit/test_graph_rag.py` — 37 tests covering entity graph, community detection, retriever, K3 gate, edge cases

### Changed
- `konjoai/config.py`: added `enable_graph_rag: bool = False`, `graph_rag_max_communities: int = 5`, `graph_rag_similarity_threshold: float = 0.3`
- `konjoai/api/schemas.py`: added `QueryRequest.use_graph_rag: bool = Field(False, ...)`, `QueryResponse.graph_rag_communities: list[str] | None = None`
- `konjoai/api/routes/query.py`: K3 gate (`if settings.enable_graph_rag and req.use_graph_rag`) injected after hybrid retrieval; `X-Use-Graph-Rag` header parsed; `graph_rag_communities` threaded to response
- `requirements.txt`: `networkx>=3.2` added
- `tests/unit/test_query_crag_route.py`, `test_query_self_rag_route.py`, `test_query_decomposition_route.py`, `test_query_route_timeout.py`: `_SettingsStub` updated with 3 new GraphRAG fields

### Tests
- Focused run: `python3 -m pytest tests/unit/test_graph_rag.py -v` → **37 passed in 8.53s**
- Full regression: `python3 -m pytest tests/unit/ -q --tb=short` → **464 passed in 10.16s**

## [Unreleased] — Pre-Sprint-15: Query Route Timeout Parity

### Added
- `asyncio.wait_for` timeout enforcement on `POST /query` and `POST /query/stream`.
- Route-level timeout failure contract: both routes return HTTP `504` with duration detail on overrun.
- `logger.warning(...)` telemetry on both timeout paths (K2 compliance).
- `tests/unit/test_query_route_timeout.py` — 4 tests covering 504 path, happy path, stream 504, detail format.

### Changed
- `konjoai/api/routes/query.py`: inner `_execute()` and `_stream_execute()` closures now wrapped with `asyncio.wait_for(timeout=timeout_seconds)`.
- `tests/unit/test_query_crag_route.py`, `test_query_self_rag_route.py`, `test_query_decomposition_route.py`: `_SettingsStub` updated with `request_timeout_seconds: float = 30.0`.

### Tests
- Focused run: `python3 -m pytest tests/unit/test_query_route_timeout.py -v` → **4 passed**
- Full regression: `python3 -m pytest tests/unit/ -q --tb=short` → **427 passed in 34.57s**
- Commit: `e48ed09` on `main`

## [Unreleased] — Sprint 14: Agentic Route Hardening (Wave 1.1)

### Added
- `POST /agent/query` request-timeout guard using `request_timeout_seconds` from settings.
- Route-level timeout failure contract: returns HTTP `504` with explicit timeout detail.
- `tests/unit/test_agent_route.py::test_agent_query_route_returns_504_on_timeout`

### Changed
- `konjoai/api/routes/agent.py` now wraps bounded ReAct execution with `asyncio.timeout(...)`.

### Tests
- Focused run: `python3 -m pytest tests/unit/test_agentic.py tests/unit/test_agent_route.py -q`
- Result: **6 passed, 0 failed**
- Adjacent route regression run: `python3 -m pytest tests/unit/test_query_decomposition_route.py tests/unit/test_query_crag_route.py tests/unit/test_query_self_rag_route.py -q`
- Result: **9 passed, 0 failed**
- Lint (changed files): `python3 -m ruff check konjoai/api/routes/agent.py tests/unit/test_agent_route.py`
- Result: **All checks passed**

## [Unreleased] — Sprint 14: Agentic RAG Foundation (v0.8.0, Wave 1)

### Added
- `konjoai/agent/react.py` — bounded ReAct-style `RAGAgent` with:
	- JSON action parsing (`retrieve` / `finish`)
	- tool registry abstraction (`ToolRegistry`)
	- max-step guard fallback for deterministic termination
	- step-level Thought/Action/Observation trace (`AgentStep`)
- `konjoai/agent/__init__.py` — agent exports for package-level import
- `konjoai/api/routes/agent.py` — `POST /agent/query` endpoint returning:
	- `answer`, `sources`, `model`, `usage`
	- `steps[]` trace
	- optional telemetry payload (aligned with `enable_telemetry`)
- `tests/unit/test_agentic.py` — unit tests for agent core loop and fallback behavior
- `tests/unit/test_agent_route.py` — route tests for response contract and telemetry on/off

### Changed
- `konjoai/api/app.py` — registered `agent` router so `/agent/query` is available in the main API app

### Tests
- Focused run: `python3 -m pytest tests/unit/test_agentic.py tests/unit/test_agent_route.py -q`
- Result: **5 passed, 0 failed**

## [Unreleased] — Sprint 13: Query Decomposition + Multi-Step Retrieval (v0.7.5)

### Added
- `konjoai/retrieve/decomposition.py`:
	- `QueryDecomposer` (LLM JSON decomposition with deterministic fallback)
	- `ParallelRetriever` (`asyncio.gather` fan-out for sub-query retrieval)
	- `AnswerSynthesizer` (sub-answer synthesis using decomposition hint)
- `QueryRequest.use_decomposition: bool = False` — per-request decomposition opt-in
- `/query` header opt-in support: `use_decomposition`, `use-decomposition`, `x-use-decomposition`
- `QueryResponse` decomposition fields:
	- `decomposition_used`
	- `decomposition_sub_queries`
	- `decomposition_synthesis_hint`
- `tests/unit/test_decomposition.py` — decomposition parser/fallback/retriever/synthesizer unit tests
- `tests/unit/test_query_decomposition_route.py` — `/query` decomposition opt-in route tests (body, header, default-off)

### Changed
- `konjoai/api/routes/query.py`:
	- AGGREGATION intent now supports Sprint 13 decomposition orchestration when explicitly enabled
	- parallel retrieval fan-out over decomposed sub-queries
	- sub-query answer generation + synthesized final answer
	- decomposition telemetry propagation in response payload
- `konjoai/config.py`:
	- added `enable_query_decomposition` and `decomposition_max_sub_queries`
- Route test settings stubs updated for new decomposition settings fields:
	- `tests/unit/test_query_crag_route.py`
	- `tests/unit/test_query_self_rag_route.py`

### Tests
- Focused run: `python3 -m pytest tests/unit/test_decomposition.py tests/unit/test_query_decomposition_route.py tests/unit/test_query_crag_route.py tests/unit/test_query_self_rag_route.py tests/unit/test_router.py -q`
- Result: **65 passed, 0 failed**
- Expanded focused run: `python3 -m pytest tests/unit/test_async_pipeline.py tests/unit/test_decomposition.py tests/unit/test_query_decomposition_route.py tests/unit/test_query_crag_route.py tests/unit/test_query_self_rag_route.py tests/unit/test_router.py -q`
- Result: **76 passed, 0 failed**

## [Unreleased] — Sprint 12: Self-RAG (v0.7.0 refresh)

### Added
- `QueryRequest.use_self_rag: bool = False` — per-request Self-RAG opt-in
- `/query` header opt-in support for Self-RAG: `use_self_rag`, `use-self-rag`, or `x-use-self-rag`
- `QueryResponse` Self-RAG telemetry fields:
	- `self_rag_iteration_scores`
	- `self_rag_total_tokens`
- `tests/unit/test_query_self_rag_route.py` — `/query` Self-RAG opt-in behavior tests (body, header, default-off)

### Changed
- `konjoai/retrieve/self_rag.py` — refreshed Sprint 12 contract implementation:
	- `SelfRAGOrchestrator` bounded iterative loop (max iterations configurable)
	- `SelfRAGCritic` reflection scoring for ISREL / ISSUP / ISUSE
	- refined retrieval callback when `ISSUP < 0.5`
	- compatibility alias retained: `SelfRAGPipeline = SelfRAGOrchestrator`
- `konjoai/api/routes/query.py` — Self-RAG now runs when globally enabled **or** request/header opt-in is set; telemetry carries per-iteration reflection scores and cumulative token usage
- `konjoai/config.py` — `self_rag_max_iterations` default updated to `3` per Sprint 12 contract

### Tests
- Focused run: `python3 -m pytest tests/unit/test_self_rag.py tests/unit/test_query_crag_route.py tests/unit/test_query_self_rag_route.py -q`
- Result: **42 passed, 0 failed**

## [Unreleased] — Sprint 11: CRAG (v0.6.0 refresh)

### Added
- `kyro_production_plan.md` — production rollout plan added to repo root and referenced by planning docs
- `QueryRequest.use_crag: bool = False` — per-request CRAG opt-in
- `/query` header opt-in support: `use_crag`, `use-crag`, or `x-use-crag`
- `QueryResponse` CRAG diagnostics: `crag_scores`, `crag_classification`, `crag_refinement_triggered`
- `tests/unit/test_query_crag_route.py` — `/query` opt-in path tests (body flag, header flag, default-off behavior)

### Changed
- `konjoai/retrieve/crag.py` — replaced legacy CRAG pipeline with `CRAGEvaluator` contract:
	- normalized score classification (`CORRECT > 0.7`, `AMBIGUOUS 0.3–0.7`, `INCORRECT < 0.3`)
	- all-incorrect fallback via `web_fallback()` stub
	- ambiguous refinement path with decomposed sub-queries
- `konjoai/config.py` — replaced `crag_relevance_threshold` with `crag_correct_threshold` and `crag_ambiguous_threshold`
- `konjoai/api/routes/query.py` — CRAG runs when globally enabled or per-request opt-in is set; telemetry includes
	`crag_scores`, `crag_classification`, `crag_refinement_triggered`
- `tests/unit/test_crag.py` — rewritten for Sprint 11 contract gates and synthetic quality checks

### Tests
- Focused run: `python3 -m pytest tests/unit/test_crag.py tests/unit/test_query_crag_route.py -q`
- Result: **11 passed, 0 failed**

## [Unreleased] — Sprint 6: Semantic Cache

### Added
- `konjoai/cache/semantic_cache.py` — two-level semantic cache: exact dict lookup O(1) + cosine-similarity scan O(n); `OrderedDict` LRU eviction; `threading.Lock` singleton with double-checked locking; `SemanticCacheEntry` dataclass; `_reset_cache()` test helper
- `konjoai/cache/__init__.py` — package with `SemanticCache`, `get_semantic_cache` exports
- `QueryResponse.cache_hit: bool = False` — backward-compatible field; true when response served from cache
- Settings: `cache_enabled: bool = False`, `cache_similarity_threshold: float = 0.95`, `cache_max_size: int = 500`
- `tests/unit/test_semantic_cache.py` — 21 tests covering exact/semantic hit, miss, LRU, invalidate, thread safety, sub-5ms latency gate ✅

### Changed
- `konjoai/retrieve/dense.py` — added `q_vec: np.ndarray | None = None` param; skips re-embed when pre-computed vector is supplied
- `konjoai/retrieve/hybrid.py` — added `q_vec: np.ndarray | None = None` param forwarded to `dense_search`
- `konjoai/api/routes/query.py` — Step 2b: embed → cache lookup → early return on hit; cache store on miss
- `konjoai/api/routes/ingest.py` — cache invalidated after BM25 rebuild to prevent stale hits

### Performance
- Cache hit path: < 5 ms (validated by `test_cache_hit_under_5ms` ✅)
- Zero LLM cost on repeated queries when `CACHE_ENABLED=true`

### Tests
- Suite: **226 passed, 0 failed** (up from 205)



## [Unreleased] — Sprint 10: Adaptive Chunking (v0.5.5)

### Added

**`konjoai/ingest/chunkers.py`**
- `SemanticSplitter` — embeds sentences with an optional context buffer (`buffer_size`), inserts chunk boundaries where cosine similarity between adjacent sentence embeddings drops below `similarity_threshold`. Implements the Semantic Chunking technique (Kamradt 2023). Produces chunks with `metadata["splitter"] = "semantic"` and `sentence_count`.
- `LateChunker` — encodes *all* sentences in a single batch call (approximating the Jina AI Late Chunking paper, 2024), then finds boundaries post-embedding. Respects `max_chunk_tokens` ceiling. Produces chunks with `metadata["chunker"] = "late"`, `sentence_count`, and `boundary_sim`.
- `_cosine_similarities()` — shared helper for adjacent cosine similarity computation from `(N, dim)` float32 arrays.
- `get_chunker()` updated — now supports `"semantic"` and `"late"` strategies in addition to existing `"recursive"` and `"sentence_window"`. Accepts optional `_encoder` and `similarity_threshold` kwargs.

**`konjoai/retrieve/router.py`**
- `ChunkComplexity(str, Enum)` — SIMPLE / MEDIUM / COMPLEX tiers with docstring explaining counter-intuitive chunk-size ordering.
- `CHUNK_SIZE_MAP: dict[ChunkComplexity, int]` — `{SIMPLE: 256, MEDIUM: 512, COMPLEX: 1024}`.
- `classify_chunk_complexity(query) -> tuple[ChunkComplexity, int]` — maps query via `QueryComplexityScorer` to a complexity tier and its associated chunk size. Lazy-loads the scorer singleton.

**`konjoai/config.py`**
- `chunk_strategy` comment updated to document all four strategies: `"recursive" | "sentence_window" | "semantic" | "late"`.
- `semantic_split_threshold: float = 0.4` — cosine similarity boundary for `SemanticSplitter`.
- `late_chunk_threshold: float = 0.4` — cosine similarity boundary for `LateChunker`.

**`scripts/ablation_chunking.py`** (new)
- CLI ablation harness; runs all four chunking strategies against `evals/corpus/eval_questions.json`.
- Computes offline proxy metrics: `chunk_count`, `avg_chunk_chars`, `std_chunk_chars`, `min/max_chunk_chars`, `within_coherence`, `boundary_sharpness`, `coverage_score`.
- Gate checks: no strategy produces zero/empty chunks; embedding-aware strategies must not be less coherent than recursive by > 0.05.
- Writes `evals/runs/<timestamp>_chunking_ablation/comparison.json`.
- Usage: `python scripts/ablation_chunking.py --quiet` (full metrics) or `--no-encoder` (CI-safe offline mode, skips embedding metrics).

**Tests**
- `tests/unit/test_semantic_splitter.py` — 32 tests: construction validation, empty/single-sentence edge cases, uniform/alternating/block mock encoders, no-empty-chunks invariant, full-content coverage, metadata tags, factory integration.
- `tests/unit/test_late_chunker.py` — 33 tests: construction validation, `max_chunk_tokens` enforcement, `boundary_sim` metadata, semantic vs late tag distinction, factory `chunk_size` → `max_chunk_tokens` wiring.
- `tests/unit/test_router.py` — 28 new tests: `ChunkComplexity` enum values, `CHUNK_SIZE_MAP` ordering, `classify_chunk_complexity` return type, size-map consistency, simple/complex query sizing, empty-query error, monotonicity.

### Tests
- Suite: **423 passed, 0 failed** (up from 329)

---

## [Unreleased] — Sprint 12 (initial scaffold, superseded above)

### Added
- `konjoai/retrieve/self_rag.py` — Self-RAG pipeline (Asai et al. 2023): `RetrieveDecision`, `RelevanceToken`, `SupportToken`, `UsefulnessToken` (IntEnum), `DocumentCritique`, `SupportScorer`, `SelfRAGPipeline`
- `tests/unit/test_self_rag.py` — 27 tests ✅

### Fixed
- `UsefulnessToken` changed from `str, Enum` to `IntEnum` to fix comparison operators
- Module-level import of `QueryIntent`, `classify_intent` from `konjoai.retrieve.router` (was local-only, caused `NameError` at runtime)
- `@patch("sentence_transformers.CrossEncoder")` in test fixtures to prevent SSL certificate errors during `SupportScorer` initialisation in sandboxed CI

### Tests
- Suite: **329 passed, 0 failed** (up from 302)

---

## [Unreleased] — Sprint 11: CRAG (Corrective RAG)

### Added
- `konjoai/retrieve/crag.py` — Corrective Retrieval-Augmented Generation pipeline: relevance grading, web fallback, knowledge refinement
- `tests/unit/test_crag.py` — tests ✅

### Tests
- Suite: **302 passed, 0 failed** (up from 280)

---

## [Unreleased] — Sprint 10 (initial scaffold, superseded above)

> **Note:** Sprint 10 scaffolding (`konjoai/ingest/adaptive_chunker.py`) was committed prior to this session.  The full Sprint 10 deliverables (SemanticSplitter, LateChunker, QueryComplexityRouter, ablation harness) are documented in the entry above.

---

## [Unreleased] — Sprint 7: Adapter Architecture

### Added
- `konjoai/adapters/base.py` — `BaseAdapter` abstract interface for retrieval backends
- `konjoai/adapters/registry.py` — `AdapterRegistry`: runtime registration and resolution of named adapters
- `konjoai/adapters/__init__.py`
- `tests/unit/test_adapters.py` — tests ✅

### Changed
- Retrieval backends refactored to implement `BaseAdapter` interface; backwards-compatible

### Tests
- Suite: **255 passed, 0 failed** (up from 226)

---

## [Unreleased] — RAGAS Eval Sprint

### Added
- `konjoai/eval/ragas_eval.py` — RAGAS evaluation harness: `threading.Lock` throttle, `asyncio.sleep` non-blocking gap, `RunConfig(timeout=600)`, `--mock` upper-bound mode, `--run-name`, `--n-samples` CLI; JSON results + gate check output
- `evals/corpus/eval_questions.json` — 3-question synthetic eval corpus (expandable to 25)
- Squish local LLM server support as RAGAS judge (`GENERATOR_BACKEND=squish`)
- **Mock upper-bound baseline PASSED** (v12, 2026-04-15): faithfulness=0.9333 ✅, context_precision=1.0000 ✅, context_recall=1.0000; run saved to `evals/runs/20260415T054040Z_mock_upper_bound_v12/`

### Fixed
- RAGAS harness: replaced `asyncio.Semaphore` (cross-loop bug) with `threading.Lock` + `asyncio.sleep` throttle
- RAGAS judge: upgraded from 1B model (LLMDidNotFinishException) to `Qwen2.5-7B-Instruct-int3`
- `max_tokens` bumped `2048 → 4096` to prevent truncated RAGAS structured-output responses
- SSL cert: `SSL_CERT_FILE` + `REQUESTS_CA_BUNDLE` → `/tmp/konjoai_certs.pem` (certifi bundle)

## [Unreleased] — Phase 2a

### Added
- Per-step pipeline telemetry (`konjoai/telemetry.py`): `StepTiming`, `PipelineTelemetry`, `timed()` context manager; zero new dependencies (stdlib `time` only)
- HyDE retrieval mode (`konjoai/retrieve/hyde.py`): hypothetical document embedding (Gao et al. 2022, arXiv:2212.10496); reuses existing generator singleton
- Query intent router (`konjoai/retrieve/router.py`): O(1) heuristic classification into `RETRIEVAL / AGGREGATION / CHAT`; CHAT queries short-circuit before any Qdrant call
- Vectro quantization bridge (`konjoai/embed/vectro_bridge.py`): INT8 compression with graceful float32 passthrough when Vectro is unavailable; logs compression ratio and mean cosine similarity
- `QueryRequest.use_hyde` (`bool`, default `False`) — per-request HyDE override
- `QueryResponse.telemetry` (`dict | None`, default `None`) — per-step latency breakdown in ms
- `QueryResponse.intent` (`str`, default `"retrieval"`) — classifier result for observability
- Settings: `enable_hyde`, `enable_query_router`, `enable_telemetry`, `vectro_quantize`, `vectro_method`
- 5-step timed query pipeline: route → hyde → hybrid_search → rerank → generate

## [0.1.0] — 2026-04-14

### Added
- Production RAG pipeline with hybrid dense + sparse retrieval
- Document ingestion: PDF, Markdown, HTML, and 10+ code file types
- Chunking strategies: `recursive` (default) and `sentence_window`
- Embedding encoder: `sentence-transformers` with enforced `float32` contract
- Qdrant vector store integration (cosine similarity, auto-collection creation)
- BM25 sparse index via `rank-bm25`
- Reciprocal Rank Fusion (RRF) hybrid retrieval with configurable `alpha`
- Cross-encoder reranking (`cross-encoder/ms-marco-MiniLM-L-6-v2`)
- Generation backends: OpenAI, Anthropic, Squish/Ollama (OpenAI-compatible)
- RAGAS evaluation harness: faithfulness, answer relevancy, context precision, context recall
- FastAPI server: `POST /ingest`, `POST /query`, `POST /eval`, `GET /health`
- Click CLI: `konjoai ingest`, `konjoai query`, `konjoai serve`, `konjoai status`
- Docker + docker-compose with Qdrant service wired
- `pydantic-settings` config with `.env` override support
- Unit tests: chunker shapes, encoder dtype contract, BM25, RRF
- Integration tests: ingest → embed → upsert pipeline smoke test
