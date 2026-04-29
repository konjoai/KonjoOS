# Quickstart

## Installation

```bash
git clone https://github.com/konjoai/kyro.git
cd kyro
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
cp .env.example .env
# Edit .env — set OPENAI_API_KEY and QDRANT_URL
```

## Start Qdrant

```bash
docker compose -f docker/docker-compose.yml up qdrant -d
```

## Ingest documents

```bash
konjoai ingest docs/
```

## Query

```bash
konjoai query "What is the main architecture?"
```

## Start the API server

```bash
konjoai serve
# API now listening at http://localhost:8000
# Interactive docs at http://localhost:8000/docs
```

## Full stack via Docker Compose

```bash
docker compose -f docker/docker-compose.yml up
```

The full stack (Qdrant + Kyro API) starts in under 60 seconds.

## First API query

```bash
curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the refund policy?", "top_k": 5}'
```

## Optional features

| Feature | Install | Enable |
|---|---|---|
| JWT multi-tenancy | `pip install PyJWT>=2.8` | `MULTI_TENANCY_ENABLED=true` + `JWT_SECRET_KEY=<secret>` |
| MCP server | `pip install mcp` | `python -m konjoai.mcp --base-url http://localhost:8000` |
| Prometheus metrics | `pip install prometheus-client` | `OTEL_ENABLED=true` |
| RAGAS evaluation | `pip install ragas datasets` | call `POST /eval` |
