# Kyro — Production Release Plan
**Version:** KORE v1.0 | **Owner:** Wes Scholl / Konjo AI  
**Horizon:** ~20 sprints → PyPI + public v1.0 release  
**Dual objective:** Maximum user value · Maximum AI/ML interview depth

---

## Executive Summary

Kyro is currently a well-engineered Sprint-6-stage RAG pipeline kernel: hybrid search, HyDE, ColBERT reranking, RAGAS eval, semantic cache, and Vectro compression. The architecture is clean and the 226-test suite is solid.

**The gap between here and v1.0 is not more retrieval features — it is:**
1. The shift from "pipeline" to "context engine" (what the market calls post-naive RAG)
2. Production-grade operability: observability, auth, multi-tenancy, async
3. A Python SDK + Helm chart that makes Kyro installable in two commands
4. Interview-anchored depth: every sprint produces a technique you can reason about in a whiteboard

The plan is structured in five phases. Each phase maps to a distinct set of ML interview topics and delivers a concrete, shippable capability increment.

---

## Market Analysis

### What the Market Has (and its gaps)

| Framework | Strength | Gap |
|---|---|---|
| LangChain / LlamaIndex | Ecosystem breadth | 200+ transitive deps; abstraction maze |
| Haystack | Modular, mature | No local-first story; no SIMD embedding |
| RAGFlow | Visual DAG UI | Heavy; not embeddable as a library |
| Verba | Great UX | Weaviate lock-in; no eval harness built in |
| DSPy | Programmatic optimization | Not a runtime pipeline; no server |

### What the Market Needs (Kyro's opportunities)

1. **GraphRAG without the complexity tax** — multi-hop reasoning that works without a full knowledge graph cluster. Lightweight entity extraction + local graph traversal.
2. **Self-correcting pipelines** — CRAG (Corrective RAG) and Self-RAG patterns. The market is screaming for pipelines that critique their own output before returning it.
3. **Agentic retrieval** — an agent that decides *when* and *how* to retrieve, not a hardcoded pipeline. This is the #1 trend in every 2026 interview guide.
4. **Adaptive chunking** — chunk size tuned per query difficulty, not fixed at ingest time. Standard RAG's flat chunking is widely cited as its primary failure mode.
5. **Built-in observability** — OpenTelemetry traces for every pipeline step. Every ops team asks "where is my latency?" and the answer should be one dashboard.
6. **Multi-tenant namespace isolation** — the enterprise cannot use a shared vector namespace. This is table stakes for any B2B deployment.
7. **Streaming responses** — users expect token-by-token output. No production app uses blocking generation.
8. **MCP server exposure** — Kyro as a tool in an agentic workflow is the direction the entire ecosystem is moving.

### Interview Signal by Technique

Every feature below is cross-referenced to what an interviewer will actually ask about:

| Technique | Interview frequency | Concepts tested |
|---|---|---|
| Hybrid search + RRF | ★★★★★ | Dense vs sparse, fusion, α weighting |
| HyDE | ★★★★☆ | Query-document distribution gap, zero-shot retrieval |
| ColBERT MaxSim reranking | ★★★★☆ | Late interaction, token-level similarity |
| Semantic cache | ★★★☆☆ | Cosine threshold, LRU, cache invalidation |
| CRAG / Self-RAG | ★★★★★ | Retrieval critique, iterative refinement |
| Agentic RAG (ReAct) | ★★★★★ | Tool use, planning, loop detection |
| GraphRAG | ★★★★☆ | Entity extraction, multi-hop, community summaries |
| Adaptive chunking | ★★★★☆ | Chunk size ablation, late chunking |
| OpenTelemetry | ★★★☆☆ | Distributed tracing, P95 latency |
| Multi-tenancy | ★★★☆☆ | Namespace isolation, row-level security |
| Streaming generation | ★★★☆☆ | Server-sent events, backpressure |
| Fine-tuning vs RAG | ★★★★★ | Trade-off analysis (always asked) |

---

## Phase Overview

```
Phase 1: Hardening + Async          Sprints  7–9    v0.3→v0.5
Phase 2: Self-Correcting Retrieval  Sprints 10–12   v0.5→v0.7
Phase 3: Agentic + GraphRAG         Sprints 13–15   v0.7→v0.8
Phase 4: Production Ops             Sprints 16–18   v0.8→v0.9
Phase 5: SDK + Public Release       Sprints 19–20   v0.9→v1.0
```

---

## Phase 1: Hardening + Async (Sprints 7–9, v0.3→v0.5)

**Goal:** Turn the prototype-quality async story into production-grade throughput. Fix the three biggest production failure modes before adding new features.

### Sprint 7 — Adapter Architecture + Backend Abstraction (v0.3.0)

**Why first:** The current backend coupling makes testing a nightmare and forces users to pick a backend at install time. The adapter pattern is a prerequisite for everything else.

**What to build:**
- `konjoai/adapters/` package with `VectorStoreAdapter`, `EmbedAdapter`, `GeneratorAdapter` abstract base classes
- Qdrant adapter (extract from current `store/qdrant.py`) + stub `ChromaAdapter`, `PineconeAdapter` (raise `NotImplementedError` with helpful message)
- `AdapterRegistry` — `get_vector_store(name)`, `get_generator(name)` factory functions
- Settings: `VECTOR_BACKEND=qdrant|chroma|pinecone`, `GENERATOR_BACKEND=openai|anthropic|squish`
- All existing tests must pass without modification (K6)

**Interview depth:** Dependency inversion principle, factory pattern, adapter vs strategy pattern. "How do you make a system backend-agnostic without abstract base class hell?"

**Gates:** 226+ tests pass; swap Qdrant for a mock adapter via env var; no breaking API changes.

---

### Sprint 8 — Async Pipeline + Connection Pooling (v0.4.0)

**Why here:** Every production system requires non-blocking I/O. The current synchronous pipeline cannot handle concurrent requests without thread contention. P99 latency degrades linearly with concurrency.

**What to build:**
- Convert `dense_search`, `hybrid_search`, `reranker.rerank` to `async def`
- `AsyncQdrantClient` wrapper (qdrant-client has async support) with connection pool (`max_connections=10` default)
- `asyncio.gather` for parallel dense + sparse retrieval (current RRF runs them sequentially)
- Concurrent BM25 + Qdrant: wall-clock latency drops from `t_dense + t_sparse` to `max(t_dense, t_sparse)`
- `POST /query` route becomes fully async; `POST /ingest` uses background tasks for embedding
- Throughput benchmark: `locust` load test, 50 concurrent users, assert P95 < 500ms

**Interview depth:** `asyncio.gather` vs `asyncio.wait`, event loop blocking, connection pool sizing, the `sync_to_async` wrapper pattern. "How do you parallelize I/O-bound operations in Python?"

**Gates:** P95 latency < 500ms at 50 concurrent users; parallel retrieval reduces combined search time by ≥30% vs sequential.

---

### Sprint 9 — Streaming Generation + SSE (v0.5.0)

**Why here:** Every production UI requires streaming. Token-by-token output is not optional — it's the difference between a usable product and one that appears frozen.

**What to build:**
- `GeneratorAdapter.stream()` async generator method alongside existing `generate()`
- Streaming implementations for OpenAI (`stream=True`), Anthropic (`stream=True`), Squish (OpenAI-compatible)
- `GET /query/stream` SSE endpoint using FastAPI `StreamingResponse` with `text/event-stream`
- SSE event format: `data: {"token": "...", "done": false}` + final `data: {"done": true, "telemetry": {...}}`
- CLI: `konjoai query --stream "..."` pipes tokens to stdout
- Graceful degradation: `stream=False` in `.env` falls back to blocking (K3)

**Interview depth:** Server-sent events vs WebSockets vs HTTP/2, backpressure, async generator patterns, `yield from`. "When would you use SSE vs WebSockets for streaming AI output?"

**Gates:** Token-to-first-byte < 200ms; streaming endpoint passes load test at 20 concurrent SSE connections; `cache_hit=True` responses still fast-path without streaming overhead.

---

## Phase 2: Self-Correcting Retrieval (Sprints 10–12, v0.5→v0.7)

**Goal:** Implement the three most-cited advanced RAG techniques in every 2026 interview guide. This phase alone makes Kyro demonstrably beyond naive RAG.

### Sprint 10 — Adaptive Chunking (v0.5.5)

**Why:** Fixed-size chunking at ingest is the #1 cited failure mode of standard RAG. Chunk size should be a function of query complexity, not a config constant.

**What to build:**
- `LateChunker` — embed full documents, then split post-embedding using cosine similarity boundary detection (sliding window, threshold-based split). Produces semantically coherent chunks rather than arbitrary token windows.
- `SemanticSplitter` — uses `sentence-transformers` to find natural paragraph boundaries by embedding pairs of adjacent sentences and splitting where cosine similarity drops below threshold
- `QueryComplexityRouter` — extend existing `router.py` to classify SIMPLE / MEDIUM / COMPLEX; SIMPLE queries use small chunks (256 tokens), COMPLEX queries use larger chunks (1024 tokens)
- `CHUNK_STRATEGY=late|sentence|recursive|semantic` config option
- Ablation harness: run RAGAS eval corpus against all 4 strategies, emit comparison JSON to `evals/runs/`

**Interview depth:** Late chunking paper (Jina AI), semantic vs syntactic chunking, chunk size ablation, the trade-off between retrieval precision and context completeness. "How do you choose chunk size?"

**Gates:** RAGAS faithfulness ≥ 0.80 with semantic chunking on eval corpus; ablation report generated; 0 regressions.

---

### Sprint 11 — CRAG: Corrective RAG (v0.6.0)

**Why:** CRAG is the most frequently asked advanced RAG technique in 2026 interviews. It adds a critique step that evaluates retrieved documents before generation, discarding low-confidence retrievals and optionally re-querying with a refined query.

**What to build:**
- `konjoai/retrieve/crag.py` — `CRAGEvaluator`:
  - Score each retrieved chunk against the query (use cross-encoder already in pipeline for consistency)
  - Classify each chunk: CORRECT (score > 0.7) / AMBIGUOUS (0.3–0.7) / INCORRECT (< 0.3)
  - If all chunks are INCORRECT: trigger `web_fallback()` (stub returning empty list with warning, or optional Tavily/SearXNG integration)
  - If mix: use CORRECT chunks only; re-embed query with decomposed sub-queries for AMBIGUOUS
- `QueryRequest.use_crag: bool = False` — opt-in per request
- Settings: `crag_correct_threshold`, `crag_ambiguous_threshold`
- Telemetry: `crag_scores`, `crag_classification`, `crag_refinement_triggered` in response
- `POST /query` with `use_crag=true` header shows per-chunk quality signal in response

**Interview depth:** The CRAG paper (Yan et al., 2024), precision vs recall trade-off in retrieval critique, iterative query refinement, when CRAG helps vs hurts (high-quality corpus → no benefit; noisy web corpus → significant benefit).

**Gates:** CRAG path tested with synthetic low-quality corpus showing recall improvement; zero regression on clean corpus; all chunk classifications logged to telemetry.

---

### Sprint 12 — Self-RAG: Reflective Generation (v0.7.0)

**Why:** Self-RAG is the evolution of CRAG — instead of critiquing *before* generation, it interleaves generation with retrieval decisions. The model decides token-by-token whether more retrieval is needed.

**Kyro's implementation (pragmatic, without fine-tuning):**
- `SelfRAGOrchestrator` — multi-turn loop using the existing generator:
  1. Generate a partial answer (max 100 tokens)
  2. Score the partial answer for: `ISREL` (is retrieval relevant?), `ISSUP` (is answer supported by context?), `ISUSE` (is output useful?)
  3. If `ISSUP < 0.5`: trigger additional retrieval with refined query derived from partial answer
  4. If `ISREL > 0.8`: continue generation without retrieval
  5. Loop max 3 iterations (configurable `self_rag_max_iterations`)
- Critique prompts are LLM calls using the existing generator backend (no fine-tuning required)
- `QueryRequest.use_self_rag: bool = False`
- Telemetry: iteration count, critique scores per iteration, total tokens used

**Interview depth:** Self-RAG paper (Asai et al., 2023), the critique tokens (ISREL/ISSUP/ISUSE), the retrieval-on-demand vs always-retrieve trade-off, why this matters for fact-dense domains, computational cost analysis (2–4x token usage).

**Gates:** Self-RAG produces better RAGAS faithfulness scores on multi-hop eval questions than single-pass RAG; iteration telemetry visible in response; max_iterations guard prevents infinite loops.

---

## Phase 3: Agentic + GraphRAG (Sprints 13–15, v0.7→v0.8)

**Goal:** Implement the two most advanced techniques that separate senior AI engineers from mid-level. These are the features that drive "oh wow" reactions in demos and interviews alike.

### Sprint 13 — Query Decomposition + Multi-Step Retrieval (v0.7.5)

**Why first:** Before full agentic RAG, query decomposition is the simpler, safer version. Complex questions get broken into sub-questions, each answered independently, then synthesized. This is the "parallel sub-agent" pattern without requiring a full agent framework.

**What to build:**
- `QueryDecomposer` — LLM call that takes a complex query and returns 2–4 sub-queries as JSON
  - Prompt: "Decompose this into N simpler sub-questions, each answerable independently"
  - Output schema: `{"sub_queries": ["...", "..."], "synthesis_hint": "..."}`
- `ParallelRetriever` — `asyncio.gather` over all sub-queries → deduplicated chunk pool
- `AnswerSynthesizer` — LLM call that takes sub-answers + synthesis hint → final coherent answer
- `QueryRequest.use_decomposition: bool = False`
- Compare: single-pass vs decomposed on multi-hop RAGAS questions; log improvement to eval runs

**Interview depth:** Query decomposition as a form of chain-of-thought prompting, multi-hop question answering, deduplication strategies for merged chunk pools, synthesis vs concatenation.

---

### Sprint 14 — Agentic RAG with ReAct (v0.8.0)

**Why:** Agentic RAG is the #1 interview topic for senior AI/ML roles in 2026. Every serious company is moving toward retrieval agents. This is the sprint that transforms Kyro from a pipeline to an intelligent system.

**What to build:**
- `konjoai/agent/` package:
  - `RAGAgent` — ReAct (Reasoning + Acting) loop using existing generator
  - `ToolRegistry` — register tools with name, description, input schema
  - Built-in tools:
    - `retrieve(query: str, top_k: int)` — calls hybrid_search
    - `search_metadata(filter: dict)` — Qdrant metadata filtering
    - `compute_stats(collection: str)` — aggregation queries (count, date range)
    - `clarify(question: str)` — asks user for clarification (signals agent uncertainty)
  - ReAct loop: `Thought → Action → Observation → Thought → ... → Final Answer`
  - Loop guard: `max_steps=10`, loop detection (same action+args twice → break)
  - Agent trace logged to telemetry: full thought/action/observation chain
- `POST /agent/query` endpoint: accepts question, returns final answer + full reasoning trace
- `konjoai agent "..."` CLI command

**Interview depth:** ReAct paper (Yao et al., 2022), the Thought/Action/Observation cycle, tool use vs function calling, loop detection, budget-bounded retrieval, why agents beat pipelines for open-ended questions. This is a guaranteed whiteboard topic.

**Gates:** Agent solves multi-hop questions that single-pass RAG fails; max_steps guard verified; reasoning trace in response; 0 infinite loops in test suite.

---

### Sprint 15 — Lightweight GraphRAG (v0.8.5)

**Why:** GraphRAG is the most-asked advanced technique after agentic RAG. The Microsoft implementation is heavy (requires Azure OpenAI, full indexing pipeline). Kyro's version targets the 80% use case without the complexity.

**What to build:**
- `konjoai/graph/` package:
  - `EntityExtractor` — uses generator to extract `(entity, relation, entity)` triples from each chunk at ingest time. LLM prompt returns JSON: `{"triples": [["Apple Inc", "CEO", "Tim Cook"], ...]}`
  - `KnowledgeGraph` — in-memory NetworkX graph built from triples; serialized to `graph.pkl` alongside Qdrant collection
  - `GraphRetriever` — given a query:
    1. Extract entities from query using `EntityExtractor`
    2. Find 1-hop and 2-hop neighbors in graph
    3. Retrieve chunks associated with neighbor entities
    4. Merge with standard hybrid search results via RRF
  - `CommunityDetector` — Louvain algorithm on NetworkX graph; produces community summaries (small LLM call per community)
  - `QueryRequest.use_graph: bool = False`
- Ingest pipeline: entity extraction is async, non-blocking (K3: if extraction fails, ingest continues without graph)
- New eval questions targeting multi-hop: "Which entities are connected to X?" → compare graph vs standard retrieval

**Interview depth:** GraphRAG paper (Edge et al., 2024 Microsoft), entity-relationship triples, community detection (Louvain vs Leiden), when graph outperforms vector (multi-hop, relationship queries), when it doesn't (single-fact lookup), the cost of entity extraction at ingest.

**Gates:** Multi-hop RAGAS questions score ≥15% higher with graph enabled; graph serializes/deserializes correctly; ingest does not fail when LLM extraction returns malformed JSON (K1).

---

## Phase 4: Production Ops (Sprints 16–18, v0.8→v0.9)

**Goal:** Everything ops teams require before approving a production deployment: observability, auth, multi-tenancy.

### Sprint 16 — OpenTelemetry + Prometheus (v0.8.7)

**What to build:**
- `opentelemetry-sdk` + `opentelemetry-exporter-otlp` integration
- Trace spans for every pipeline step: ingest, embed, search, rerank, generate, cache
- Prometheus metrics endpoint `GET /metrics`: `kyro_query_duration_seconds` (histogram), `kyro_cache_hit_total`, `kyro_retrieval_count`, `kyro_generation_tokens_total`
- Docker compose: add `otel-collector`, `prometheus`, `grafana` services with pre-built Kyro dashboard JSON
- Settings: `OTEL_ENDPOINT`, `METRICS_ENABLED`

**Interview depth:** Distributed tracing vs logging vs metrics, P50/P95/P99 latency, exemplars, the four signals (latency, traffic, errors, saturation), why tracing is better than print debugging for async pipelines.

---

### Sprint 17 — Multi-Tenant Namespace Isolation (v0.9.0)

**What to build:**
- `tenant_id` parameter on all ingest and query endpoints
- Qdrant collection per tenant OR payload filtering with `tenant_id` field (configurable; collection-per-tenant is more isolated, payload filtering is cheaper)
- `TenantManager` — create, list, delete tenant namespaces; quota enforcement (max_docs, max_queries_per_day)
- JWT-based auth middleware: `Authorization: Bearer <token>` → decode → extract `tenant_id` → inject into pipeline
- `POST /tenants` (admin), `GET /tenants/{id}/stats` endpoints
- Audit log: every query logged with `tenant_id`, `timestamp`, `query_hash` (no raw query text — OWASP LLM Top 10)

**Interview depth:** Namespace isolation strategies, the security trade-off between collection-per-tenant vs payload filtering, RBAC vs ABAC, why you log query hashes not query text (PII), JWT vs API key auth patterns.

---

### Sprint 18 — Auth, API Keys, Rate Limiting (v0.9.5)

**What to build:**
- API key generation: `POST /keys` returns hashed key; stored in SQLite (lightweight, no external dep)
- Key scopes: `read` (query only), `write` (ingest + query), `admin` (all + tenant management)
- Rate limiting middleware: token bucket per API key; `RATE_LIMIT_RPM=60` default
- `GET /keys/{id}/usage` — daily query count, token usage, cache hit rate per key
- Rate limit headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- `429 Too Many Requests` with `Retry-After` header

**Interview depth:** Token bucket vs leaky bucket vs sliding window rate limiting, API key security (hash storage, rotation), scope-based authorization.

---

## Phase 5: SDK + Public Release (Sprints 19–20, v0.9→v1.0)

### Sprint 19 — Python SDK + MCP Server (v0.9.8)

**What to build:**
- `konjoai-sdk` package (separate from server): typed client wrapping all REST endpoints
  ```python
  from konjoai import KyroClient
  client = KyroClient(base_url="http://localhost:8000", api_key="...")
  result = await client.query("What is the main architecture?")
  ```
- Async-first with sync wrappers via `asyncio.run()`
- `KyroMCPServer` — expose Kyro as an MCP tool server:
  - `kyro_retrieve` tool: query the knowledge base
  - `kyro_ingest` tool: add documents at runtime
  - MCP manifest: `mcp.json` at repo root
- This makes Kyro usable as a tool in Claude, Cursor, any MCP-compatible agent

**Interview depth:** MCP protocol, tool schemas, async client patterns, the SDK-as-first-class-citizen philosophy.

---

### Sprint 20 — Helm Chart + PyPI + Documentation Site (v1.0.0)

**What to build:**
- `helm/kyro/` chart: Deployment, Service, ConfigMap, optional Ingress; `values.yaml` with sane defaults
- PyPI publish: `pip install konjoai` installs server + SDK + CLI
- GitHub Actions: test → lint → build → publish pipeline
- Documentation site (mkdocs-material): quickstart, architecture deep-dive, API reference, eval guide, interview reference (yes, include this — it drives GitHub stars)
- `CONTRIBUTING.md`, issue templates, PR template
- `v1.0.0` tag + GitHub Release with binaries

**Gates:** `pip install konjoai && konjoai serve` works from zero. `helm install kyro ./helm/kyro` deploys to Kubernetes. PyPI publish succeeds. Docs site live.

---

## Seven Konjo Invariants — Extended

The existing K1–K7 carry forward. Two additions for v1.0:

| # | Invariant | Contract |
|---|---|---|
| K8 | Agent budget bounds | Every agentic loop has a `max_steps` guard. No infinite retrieval. |
| K9 | PII-clean audit log | Query hashes only in audit log. Raw text never persisted. |

---

## Interview Preparation Map

Every sprint below maps directly to a high-signal interview topic. Build these in order, and by Sprint 15 you can answer every question on the DataCamp/Analytics Vidhya "Top 30 RAG Interview Questions 2026" lists from working code, not theory.

| Sprint | You can now answer... |
|---|---|
| 7 | "How do you make a RAG pipeline backend-agnostic?" |
| 8 | "How do you handle concurrent requests in a Python async service?" |
| 9 | "How do you stream LLM output to a UI?" |
| 10 | "How do you choose chunk size? What is late chunking?" |
| 11 | "What is CRAG and when would you use it?" |
| 12 | "Explain Self-RAG. How does the model decide when to retrieve?" |
| 13 | "How do you handle multi-hop questions in RAG?" |
| 14 | "Explain the ReAct architecture. Build me a retrieval agent." |
| 15 | "What is GraphRAG and how does it differ from standard RAG?" |
| 16 | "How do you observe and debug a production RAG pipeline?" |
| 17 | "How do you handle multi-tenant data isolation in a vector store?" |
| 18 | "How would you rate-limit and authenticate an LLM API?" |
| All | "Compare RAG vs fine-tuning. When would you use each?" |

---

## Dependency Budget

Kyro's competitive moat includes staying lean. Every new hard dep must be justified:

| Addition | Justification | Sprint |
|---|---|---|
| `networkx` | GraphRAG (Louvain community detection) | 15 |
| `opentelemetry-sdk` | Production observability | 16 |
| `opentelemetry-exporter-otlp` | Trace export | 16 |
| `prometheus-client` | Metrics endpoint | 16 |
| `python-jose` | JWT auth | 17 |
| `mcp` (Anthropic SDK) | MCP server | 19 |
| `mkdocs-material` | Docs (dev dep only) | 20 |

Everything else reuses what is already installed. The core query path must not acquire new deps at any point.

---

## Test Strategy

Current: 226 unit + integration tests.  
Target: 500+ tests at v1.0.

| Phase | Test additions |
|---|---|
| Phase 1 | Async concurrency tests, streaming SSE tests, adapter mock tests |
| Phase 2 | CRAG classification accuracy, Self-RAG loop termination, chunk quality unit tests |
| Phase 3 | Agent tool call sequences, graph triple extraction, multi-hop retrieval tests |
| Phase 4 | Auth middleware, tenant isolation, rate limit behavior, OTel span assertions |
| Phase 5 | SDK contract tests, MCP tool schema validation, Helm chart lint |

**CI/CD:** GitHub Actions on every PR: `pytest → ruff → mypy → docker build`. Fail fast, no merging red.

---

## Release Checklist for v1.0

- [ ] All 500+ tests passing, 0 failures
- [ ] `pip install konjoai && konjoai serve` works on macOS, Linux, Windows (WSL)
- [ ] `helm install` deploys cleanly to k3s
- [ ] Docs site live with quickstart that works in < 5 minutes
- [ ] RAGAS faithfulness ≥ 0.80 on public eval corpus
- [ ] P95 query latency < 500ms at 50 concurrent users
- [ ] MCP manifest published and tested in Claude Desktop
- [ ] PyPI package published with correct classifiers
- [ ] GitHub release with signed binaries
- [ ] `SECURITY.md` with responsible disclosure policy

---

## Sprint Roadmap Summary

| Sprint | Version | Focus | Key technique |
|---|---|---|---|
| 6 | 0.3.0 | Semantic cache ✅ | Cosine similarity cache, LRU |
| 7 | 0.3.5 | Adapter architecture | Factory pattern, DI |
| 8 | 0.4.0 | Async + connection pooling | asyncio.gather, parallel retrieval |
| 9 | 0.5.0 | Streaming SSE | Async generators, SSE |
| 10 | 0.5.5 | Adaptive chunking | Late chunking, semantic splitting |
| 11 | 0.6.0 | CRAG | Retrieval critique, refinement |
| 12 | 0.7.0 | Self-RAG | Reflective generation, ISREL/ISSUP |
| 13 | 0.7.5 | Query decomposition | Parallel sub-retrieval, synthesis |
| 14 | 0.8.0 | Agentic RAG (ReAct) | Tool use, planning, loop guard |
| 15 | 0.8.5 | Lightweight GraphRAG | Entity triples, community detection |
| 16 | 0.8.7 | OpenTelemetry + Prometheus | Distributed tracing, metrics |
| 17 | 0.9.0 | Multi-tenancy | Namespace isolation, JWT |
| 18 | 0.9.5 | Auth + rate limiting | Token bucket, API keys |
| 19 | 0.9.8 | Python SDK + MCP | SDK design, MCP protocol |
| 20 | 1.0.0 | Helm + PyPI + Docs | Public release |

---

*Owner: wesleyscholl / Konjo AI Research*  
*"Make it konjo — build, ship, repeat."*
