# Kyro

Production RAG pipeline with hybrid retrieval, reranking, and RAGAS evaluation.
No vendor lock-in — plug in OpenAI, Anthropic, or a local [Squish](https://github.com/squishai/squish) server.

## Planning Docs

- `PLAN.md` — implementation checklist and sprint gates
- `KORE_PLAN.md` — strategic roadmap and market analysis
- `kyro_production_plan.md` — production rollout and operations plan

## Architecture

```
Documents (PDF/MD/HTML/code)
        │
        ▼
    Ingest & Chunk      RecursiveChunker | SentenceWindowChunker
        │
        ▼
    Embed               sentence-transformers → float32 (384–1536d)
        │
        ▼
    Qdrant Store        cosine similarity index
        │
    ┌───┴───┐
 Dense   Sparse         HNSW search + BM25 (rank-bm25)
    └───┬───┘
        │  Reciprocal Rank Fusion (α=0.7)
        ▼
    Rerank              cross-encoder/ms-marco-MiniLM-L-6-v2
        │
        ▼
    Generate            OpenAI | Anthropic | Squish
        │
        ▼
    Evaluate            RAGAS: faithfulness / relevancy / precision / recall
```

## Quickstart

```bash
git clone https://github.com/konjoai/kyro.git
cd kyro
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

cp .env.example .env
# edit .env — set OPENAI_API_KEY and QDRANT_URL

# Start Qdrant (Docker)
docker compose -f docker/docker-compose.yml up qdrant -d

# Ingest a directory
konjoai ingest docs/

# Ask a question
konjoai query "What is the main architecture?"

# Start the API server
konjoai serve
```

## CLI

```
konjoai ingest <path>     Ingest files/dirs into vector store
konjoai query  <question> Retrieve and answer using indexed documents
konjoai serve             Start FastAPI server (default :8000)
konjoai status            Show collection stats
```

## API

| Method | Path       | Description                        |
|--------|------------|------------------------------------|
| POST   | /ingest    | Ingest a file or directory         |
| POST   | /query     | RAG query with optional decomposition + CRAG + Self-RAG reflective critique |
| POST   | /agent/query | Bounded ReAct-style agent query with step trace (`steps[]`) |
| POST   | /eval      | RAGAS evaluation over QA samples   |
| GET    | /health    | Collection health + document count |

Docs at `http://localhost:8000/docs` after `konjoai serve`.

CRAG and Self-RAG can be enabled per request with request body flags, or with headers:

```bash
curl -s -X POST http://localhost:8000/query \
    -H 'Content-Type: application/json' \
    -H 'use_decomposition: true' \
    -H 'use_crag: true' \
    -H 'use_self_rag: true' \
    -d '{"question":"Compare return policy and exchange policy updates by owner","top_k":5,"use_decomposition":true,"use_crag":true,"use_self_rag":true}'
```

When decomposition is enabled, `/query` includes:
- `decomposition_used`
- `decomposition_sub_queries`
- `decomposition_synthesis_hint`

When Self-RAG is enabled, `/query` telemetry includes:
- `self_rag_iteration_scores` (ISREL/ISSUP/ISUSE per iteration)
- `self_rag_total_tokens` (cumulative generation tokens across iterations)

`/agent/query` is protected by `request_timeout_seconds`; requests exceeding this ceiling return HTTP `504`.

## Configuration

All settings via `.env` (see `.env.example`):

| Variable            | Default                                    | Description                    |
|---------------------|--------------------------------------------|--------------------------------|
| `QDRANT_URL`        | `http://localhost:6333`                    | Qdrant instance URL            |
| `EMBED_MODEL`       | `sentence-transformers/all-MiniLM-L6-v2`  | HuggingFace embedding model    |
| `EMBED_DEVICE`      | `cpu`                                      | `mps` for Apple Silicon        |
| `CHUNK_STRATEGY`    | `recursive`                                | `recursive` \| `sentence_window` |
| `GENERATOR_BACKEND` | `openai`                                   | `openai` \| `anthropic` \| `squish` |
| `OPENAI_API_KEY`    | —                                          | Required for OpenAI backend    |
| `SQUISH_BASE_URL`   | `http://localhost:11434/v1`                | Local Squish/Ollama endpoint   |
| `REQUEST_TIMEOUT_SECONDS` | `30.0`                              | Per-request timeout ceiling for API routes |

## Evaluation

kyro ships RAGAS gates out of the box:

```bash
konjoai serve &
curl -s -X POST http://localhost:8000/eval \
  -H 'Content-Type: application/json' \
  -d '{"samples": [{"question": "...", "answer": "...", "contexts": ["..."], "ground_truth": "..."}]}'
```

Target benchmarks (Weeks 3–7 gate):
- `faithfulness` ≥ 0.75
- `answer_relevancy` ≥ 0.80

## License

MIT
