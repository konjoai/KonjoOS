# MCP Server

Kyro ships an [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that exposes its RAG capabilities as tools consumable by any MCP-compatible AI agent (Claude Desktop, etc.).

## Installation

```bash
pip install mcp>=1.0
```

## Start the server

```bash
# Default: connect to Kyro API at http://localhost:8000
python -m konjoai.mcp

# With credentials
python -m konjoai.mcp --base-url http://localhost:8000 --api-key sk-...

# With JWT
python -m konjoai.mcp --base-url http://localhost:8000 --jwt-token eyJ...

# Environment variables
KYRO_API_KEY=sk-... python -m konjoai.mcp
KYRO_JWT_TOKEN=eyJ... python -m konjoai.mcp
```

## Claude Desktop integration

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "kyro": {
      "command": "python",
      "args": ["-m", "konjoai.mcp", "--base-url", "http://localhost:8000"],
      "env": {
        "KYRO_API_KEY": "sk-..."
      }
    }
  }
}
```

## Available tools

### `kyro_query`

Query the RAG pipeline. Returns a synthesised answer with source citations.

```json
{
  "question": "What is the refund policy?",
  "top_k": 5,
  "use_hyde": false
}
```

### `kyro_ingest`

Ingest a local file or directory into the vector store.

```json
{
  "path": "/path/to/documents",
  "strategy": "recursive",
  "chunk_size": 512
}
```

### `kyro_health`

Check API health — no arguments required.

### `kyro_agent_query`

Run the bounded ReAct agent loop with step tracing.

```json
{
  "question": "Find all compliance requirements and summarise them",
  "top_k": 5,
  "max_steps": 5
}
```

## Programmatic use

```python
from konjoai.mcp import KyroMCPServer
from konjoai.sdk import KonjoClient

client = KonjoClient("http://localhost:8000", api_key="sk-...")
server = KyroMCPServer(client)

# List available tools
tools = server.list_tools()

# Dispatch a tool call directly
import asyncio
result = asyncio.run(server.dispatch("kyro_query", {"question": "What is X?"}))
print(result)  # JSON string
```
