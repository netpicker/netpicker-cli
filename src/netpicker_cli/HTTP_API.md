# Netpicker HTTP API Wrapper

Simple HTTP API wrapper around the Netpicker MCP Server, enabling access for language models that don't natively support MCP (like Llama, etc.).

With **AI Router integration** for intelligent query routing!

## Architecture

The system is now cleanly separated into:

- **HTTP API Layer** (`api_server.py`): REST endpoints, request/response handling
- **AI Router** (`ai/router.py`): Intelligent query routing using Mistral LLM
- **MCP Server** (`mcp/server.py`): MCP protocol implementation, tool execution
- **Netpicker CLI** (`commands/*.py`): Core CLI functionality

## Features

- **Natural Language Queries**: Ask questions in plain English
- **AI Router Integration**: Automatically routes queries to the right tool using Mistral
- **Keyword Fallback**: Falls back to keyword matching if AI is unavailable
- **Direct Tool Execution**: Call specific tools with custom parameters
- **Interactive Documentation**: Built-in Swagger/OpenAPI docs
- **Modular Design**: AI logic separated from core API functionality

## Installation

```bash
pip install -e ".[api]"
```

## Configuration

### Connect to Your AI Router (Mistral)

Point the AI router to your Mistral instance:

```bash
# Environment variables
export MISTRAL_URL="http://localhost:8000"
export USE_MISTRAL="true"

# Check AI router status
curl http://localhost:8000/ai/status
```

### Netpicker Backend Configuration

Configure connection to Netpicker server:

```bash
export NETPICKER_BASE_URL="https://sandbox.netpicker.io"
export NETPICKER_TENANT="DefaultTenant"
export NETPICKER_TOKEN="your-jwt-token"
```

## Running the Server

```bash
# Option 1: Direct command
netpicker-api

# Option 2: With environment variables
MISTRAL_URL="http://localhost:8000" USE_MISTRAL="true" netpicker-api

# Option 3: With Uvicorn and custom settings
uvicorn netpicker_cli.api_server:app --host 0.0.0.0 --port 8001 --reload
```

The API will be available at `http://localhost:8001`

## Architecture

```
Language Model (Llama, etc.)
         ↓
    HTTP API (port 8001)
         ↓
  Mistral Server (localhost:8000) ← [optional, for query understanding]
         ↓
    MCP Server  
         ↓
  Netpicker CLI
```

## API Endpoints

### Core Endpoints

#### List Available Tools
```
GET /tools
```

Returns all available MCP tools with descriptions.

```bash
curl http://localhost:8001/tools
```

#### Check Mistral Status
```
GET /ai/status
```

Check if Mistral LLM is connected and available.

```bash
curl http://localhost:8000/ai/status
```

Response:
```json
{
  "enabled": true,
  "available": true,
  "url": "http://localhost:8000",
  "status": "connected"
}
```

#### Natural Language Query (WITH MISTRAL)
```
POST /query
Content-Type: application/json

{
  "query": "List all production devices",
  "use_llm": true
}
```

**How it works:**
1. Sends your query to Mistral
2. Mistral determines which tool to call
3. Executes that tool
4. Returns the result + Mistral's reasoning

```bash
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show me all devices",
    "use_llm": true
  }'
```

Response:
```json
{
  "success": true,
  "tool": "devices_list",
  "result": "...",
  "reasoning": "User asked to show all devices, selected devices_list tool",
  "error": null
}
```

#### Execute Specific Tool
```
POST /tool/{tool_name}
Content-Type: application/json

{
  "arguments": {
    "json_output": true,
    "limit": 10
  }
}
```

Directly call a tool with custom parameters.

```bash
curl -X POST http://localhost:8001/tool/devices_list \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"json_output": true, "limit": 5}}'
```

### Shortcut Endpoints

Quick endpoints for common operations:

#### List Devices
```
POST /devices/list?tag=production&limit=10
```

#### Show Device Details
```
POST /devices/show?ip=192.168.1.1
```

#### View Backup History
```
POST /backups/history?ip=192.168.1.1&limit=20
```

#### Health Check
```
POST /health
```

## Usage Examples

### Example 1: List devices with Mistral routing
```bash
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show me all devices with their configurations",
    "use_llm": true
  }'
```

### Example 2: Without Mistral (keyword matching)
```bash
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "List all devices",
    "use_llm": false
  }'
```

### Example 3: Direct tool call
```bash
curl -X POST http://localhost:8001/tool/devices_show \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"ip": "192.168.1.100"}}'
```

### Example 4: Get device list with filtering
```bash
curl -X POST "http://localhost:8001/devices/list?tag=production&limit=5"
```

## Using with Language Models

### With Local Llama via Ollama

You can use this API with Llama or other local models:

```python
import requests
import json

def query_netpicker_with_llm(question: str, mistral_url: str = "http://localhost:8000"):
    # Step 1: Send to our HTTP API (which uses Mistral internally if available)
    response = requests.post(
        "http://localhost:8001/query",
        json={
            "query": question,
            "use_llm": True  # Use Mistral for intelligent routing
        }
    )
    
    result = response.json()
    
    if result["success"]:
        print(f"Tool used: {result['tool']}")
        print(f"Reasoning: {result['reasoning']}")
        print(f"Result:\n{result['result']}")
    else:
        print(f"Error: {result['error']}")

# Example usage
query_netpicker_with_llm("List all devices in the network")
```

### Without Mistral (Keyword-based routing)

If you don't have Mistral, the API still works with keyword matching:

```python
import requests

response = requests.post(
    "http://localhost:8001/query",
    json={
        "query": "List devices",
        "use_llm": False  # Use keyword matching only
    }
)
print(response.json()["result"])
```

## Response Format

All tool execution endpoints return:

```json
{
  "success": true,
  "tool": "devices_list",
  "result": "...",
  "reasoning": "optional explanation from Mistral",
  "error": null
}
```

- `success`: Boolean indicating if the tool executed successfully
- `tool`: The tool that was called
- `result`: The output from the tool (usually formatted text)
- `reasoning`: Why Mistral chose that tool (if using LLM)
- `error`: Error message if `success` is false

## Interactive API Documentation

Visit `http://localhost:8001/docs` for interactive Swagger UI documentation where you can test all endpoints directly.

## Configuration

Set environment variables to configure the API server:

```bash
# Mistral configuration
export MISTRAL_URL="http://localhost:8000"
export USE_MISTRAL="true"

# Netpicker configuration (shared with MCP server)
export NETPICKER_BASE_URL="https://your-netpicker-instance.com"
export NETPICKER_TENANT="your-tenant"
export NETPICKER_TOKEN="your-api-token"
```

## Notes

- **Mistral Integration**: The API automatically detects if Mistral is available. If it's down, it falls back to keyword matching
- **Smart Routing**: Mistral analyzes your query and selects the most appropriate tool, with reasoning
- **Concurrent Requests**: The API handles concurrent requests asynchronously
- **Stateless**: No session state - each request is independent
- **Timeout Handling**: Mistral queries timeout after 10 seconds, falling back gracefully

