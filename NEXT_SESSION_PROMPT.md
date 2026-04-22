# KYRO — Next Session Prompt

Read this first before any implementation sprint.

## Current State (as of Sprint 15 session, 2026-04-22)

- **Last commit:** pending push — Sprint 15: Lightweight GraphRAG Community Detection
- **Tests:** 464 passing, 0 failing (`python3 -m pytest tests/unit/ -q --tb=short`)
- **Version:** v0.8.5 (Sprint 15 GraphRAG complete)
- **Active sprint:** Sprint 16 — OTel / Prometheus / Grafana Observability Layer

## What Was Done Last Session (Sprint 15 — GraphRAG)

- Created `konjoai/retrieve/graph_rag.py`: `_tokenize()`, `EntityGraph` (Jaccard similarity graph builder), `CommunityContext`, `GraphRAGResult`, `GraphRAGRetriever`, `get_graph_rag_retriever()` singleton; `_HAS_NETWORKX` guard for graceful fallback when networkx absent
- Added 3 settings to `konjoai/config.py`: `enable_graph_rag: bool = False`, `graph_rag_max_communities: int = 5`, `graph_rag_similarity_threshold: float = 0.3`
- Extended `konjoai/api/schemas.py`: `QueryRequest.use_graph_rag: bool = Field(False, ...)`, `QueryResponse.graph_rag_communities: list[str] | None = None`
- Injected K3-gated GraphRAG block (Step 3c after hybrid retrieval) into `konjoai/api/routes/query.py`; `X-Use-Graph-Rag` response header
- Added `networkx>=3.2` to `requirements.txt`
- Created `tests/unit/test_graph_rag.py` (37 tests — tokenizer, entity graph, communities, retriever, K3 gate, NetworkX-absent fallback)
- Updated `_SettingsStub` in 4 existing route test files with 3 new GraphRAG fields
- Tests: 427 → 464 (+37 new). ruff permanently absent — `python3 -m py_compile` only.

## Active Invariants (K1–K7)

| # | Invariant | Rule |
|---|-----------|------|
| K1 | No silent failures | All exceptions re-raised with `from exc` chain |
| K2 | Telemetry everywhere | `logger.warning(...)` on every error/timeout path |
| K3 | Graceful degradation | Optional features gated `if settings.X` |
| K4 | float32 dtype | All embeddings cast to `np.float32` before Qdrant |
| K5 | No unnecessary hard deps | New packages must be optional or stdlib |
| K6 | Backward-compatible API | New fields `Optional`/nullable, no removals |
| K7 | Reproducible evals | RAGAS seeds fixed; baseline scores locked |

## Known Blockers / Risks

- Full-repo `mypy` still reports baseline issues unrelated to Sprint 14 (missing stubs/external deps and pre-existing typedness gaps). Ignore pre-existing errors; only fix new ones introduced this session.
- `DREX_UNIFIED_SPEC.md` canonical source is shared from the `drex` workspace; kyro keeps a local pointer file.
- ruff is permanently absent from this machine — skip it everywhere. Syntax check via `python3 -m py_compile`.

## Recommended Next Task — Sprint 16: OTel / Prometheus / Grafana Observability Layer

### Goal
Add structured observability using OpenTelemetry (OTel) for tracing and Prometheus for metrics. Feature-flagged off by default (K3). No breaking API changes (K6).

### Files to Create/Modify

| File | Change |
|------|--------|
| `konjoai/telemetry.py` | New: OTel tracer + Prometheus counters/histograms; `_HAS_OTEL` guard |
| `konjoai/config.py` | Add `enable_telemetry: bool = False`, `otel_endpoint: str = ""`, `prometheus_port: int = 8001` |
| `konjoai/api/routes/query.py` | Instrument `/query` span; record latency histogram |
| `konjoai/api/routes/health.py` | Add `/metrics` Prometheus endpoint (conditional on `enable_telemetry`) |
| `requirements.txt` | Add `opentelemetry-sdk>=1.20`, `prometheus-client>=0.19` as optional extras |
| `tests/unit/test_telemetry.py` | New: ≥ 20 tests covering tracer, metrics, K3 gate, OTel-absent fallback |

### Sprint 16 Gate (all required before SHIP)
1. All telemetry behind `if settings.enable_telemetry` (K3) ✅
2. No breaking changes to existing routes when flag is off (K6) ✅
3. New deps optional or guarded with `_HAS_OTEL` (K5) ✅
4. All K1-K7 pass on new code ✅
5. Full suite stays at ≥ 464 tests passing ✅

### Critical Patch Target Rule (NEVER FORGET)
Lazy imports inside closures must be patched at the **source module**, not at the route module.
- ✅ `konjoai.retrieve.hybrid.hybrid_search` → patch at source
- ❌ `konjoai.api.routes.query.hybrid_search` → DO NOT patch here

Route-level `Depends`-injected callables patch at the **route module**:
- ✅ `konjoai.api.routes.query.get_settings` → patch here in ALL route tests
- ✅ `konjoai.cache.get_semantic_cache` → always mock alongside `get_settings` in route tests

## Quick Commands

```bash
cd /Users/wscholl/kyro

# Run full unit suite
python3 -m pytest tests/unit/ -q --tb=short

# Run focused test file (update per sprint)
python3 -m pytest tests/unit/test_telemetry.py -v

# Verify Sprint 15 GraphRAG still passes
python3 -m pytest tests/unit/test_graph_rag.py -v

# CRITIC syntax check (ruff is permanently absent — skip it always)
python3 -m py_compile konjoai/telemetry.py

# Check recent git log
git log --oneline -5
```
