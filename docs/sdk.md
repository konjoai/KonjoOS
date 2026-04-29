# Python SDK

The `konjoai.sdk` module provides a typed synchronous HTTP client for all Kyro API endpoints.

## Installation

The SDK is included with `pip install konjoai` — no extra packages required.

## Usage

```python
from konjoai.sdk import KonjoClient

client = KonjoClient("http://localhost:8000", api_key="sk-...")
```

### Query

```python
response = client.query("What is the refund policy?", top_k=5)
print(response.answer)
for src in response.sources:
    print(f"  {src.source}  score={src.score:.3f}")
```

### Streaming tokens

```python
for chunk in client.query_stream("Summarise the onboarding guide"):
    print(chunk.text, end="", flush=True)
```

### Ingest

```python
result = client.ingest("/path/to/docs", strategy="recursive", chunk_size=512)
print(f"Indexed {result.chunks_indexed} chunks from {result.sources_processed} sources")
```

### Health check

```python
health = client.health()
assert health.status == "ok"
```

### ReAct agent

```python
result = client.agent_query("Find all compliance requirements", max_steps=5)
print(result.answer)
for step in result.steps:
    print(f"  [{step.action}] {step.thought}")
```

## Context manager

```python
with KonjoClient("http://localhost:8000") as client:
    response = client.query("...")
# HTTP connection pool closed automatically
```

## Authentication

```python
# API key (X-API-Key header)
client = KonjoClient("http://localhost:8000", api_key="sk-...")

# JWT Bearer token
client = KonjoClient("http://localhost:8000", jwt_token="eyJ...")
```

## Error handling

```python
from konjoai.sdk import (
    KyroError,
    KyroAuthError,       # 401 / 403
    KyroRateLimitError,  # 429; .retry_after gives seconds to wait
    KyroTimeoutError,    # HTTP timeout
    KyroNotFoundError,   # 404
)

try:
    response = client.query("...")
except KyroRateLimitError as e:
    print(f"Rate limited — retry after {e.retry_after}s")
except KyroAuthError:
    print("Invalid credentials")
except KyroError as e:
    print(f"API error {e.status_code}: {e}")
```

## Response models

| Model | Fields |
|---|---|
| `SDKQueryResponse` | `answer`, `sources`, `model`, `usage`, `intent`, `cache_hit`, `telemetry` |
| `SDKIngestResponse` | `chunks_indexed`, `sources_processed`, `chunks_deduplicated` |
| `SDKHealthResponse` | `status`, `vector_count`, `bm25_built` |
| `SDKAgentQueryResponse` | `answer`, `sources`, `model`, `usage`, `steps`, `telemetry` |
| `SDKSourceDoc` | `source`, `content_preview`, `score` |
| `SDKStreamChunk` | `text` |
| `SDKAgentStep` | `thought`, `action`, `action_input`, `observation` |
