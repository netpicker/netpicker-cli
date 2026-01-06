"""
HTTP API wrapper for NetPicker MCP Server

Provides a simple HTTP interface for language models (Llama, etc.) to interact
with NetPicker CLI through the MCP server. This bridges the gap between models
that don't natively understand MCP and the MCP server.

Can integrate with AI router for intelligent query routing.
"""

import asyncio
import json
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import uvicorn

from netpicker_cli.mcp.server import mcp
from netpicker_cli.ai import router as ai_router

app = FastAPI(
    title="NetPicker API",
    description="HTTP API wrapper for NetPicker CLI via MCP Server",
    version="0.1.0"
)

# Request/Response Models
class ToolCall(BaseModel):
    """Request to execute a specific tool with parameters."""
    tool_name: str
    arguments: Dict[str, Any] = {}


class QueryRequest(BaseModel):
    """Natural language query that will be routed to appropriate tool."""
    query: str
    use_llm: bool = True  # Use Mistral if available


class ToolInfo(BaseModel):
    """Information about an available tool."""
    name: str
    description: str


class QueryResponse(BaseModel):
    """Response from executing a tool."""
    success: bool
    tool: str
    result: str
    error: Optional[str] = None
    reasoning: Optional[str] = None


# Simple tool routing - maps keywords to tools
TOOL_ROUTES = {
    # Device queries
    "list.*device": "devices_list",
    "show.*device": "devices_show",
    "device.*list": "devices_list",
    "device.*show": "devices_show",
    "get.*device": "devices_show",
    "find.*device": "devices_list",
    "create.*device": "devices_create",
    "delete.*device": "devices_delete",
    
    # Backup queries
    "backup": "backups_history",
    "history": "backups_history",
    "diff": "backups_diff",
    "compare": "backups_diff",
    "upload.*config": "backups_upload",
    
    # Compliance queries
    "policy": "policy_list",
    "compliance": "policy_list",
    "check.*compliance": "policy_list",
    "test.*rule": "policy_test_rule",
    
    # Automation queries
    "automation": "automation_list_jobs",
    "job": "automation_list_jobs",
    "execute.*job": "automation_execute_job",
    
    # Health queries
    "health": "health_check",
    "status": "health_check",
}


async def route_query_with_ai(query: str) -> tuple[str | None, str]:
    """
    Route query using AI router (if available).
    Falls back to keyword matching.

    Returns:
        Tuple of (tool_name, reasoning)
    """
    # Get available tools
    tools = await mcp.list_tools()
    available_tool_names = [t.name for t in tools]

    # Try AI routing first
    tool_name, reasoning = await ai_router.route_query(query, available_tool_names)

    if tool_name:
        return tool_name, reasoning

    # Fallback to keyword matching
    tool_name = find_tool_by_keywords(query)
    return tool_name, "Used keyword matching"


def find_tool_by_keywords(query: str) -> str:
    """Find tool using keyword matching (fallback)."""
    query_text = query.lower()
    
    for pattern, tool in TOOL_ROUTES.items():
        if any(keyword in query_text for keyword in pattern.split("|")):
            return tool
    
    return "devices_list"  # Default


@app.get("/")
async def root():
    """Health check endpoint."""
    ai_available = await ai_router.is_available()

    return {
        "name": "NetPicker API",
        "status": "running",
        "description": "HTTP wrapper for NetPicker CLI MCP Server",
        "ai_enabled": ai_router.enabled,
        "ai_available": ai_available,
        "ai_url": ai_router.mistral_url if ai_available else None
    }


@app.get("/tools")
async def list_tools() -> Dict[str, Any]:
    """
    List all available tools.
    
    Returns a list of tool names and descriptions that can be called.
    """
    tools = await mcp.list_tools()
    return {
        "tools": [
            {
                "name": tool.name,
                "description": tool.description
            }
            for tool in tools
        ],
        "count": len(tools)
    }


@app.get("/tools/{tool_name}")
async def get_tool_info(tool_name: str) -> Dict[str, Any]:
    """Get detailed information about a specific tool."""
    tools = await mcp.list_tools()
    tool = next((t for t in tools if t.name == tool_name), None)
    
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    
    return {
        "name": tool.name,
        "description": tool.description,
        "inputSchema": tool.inputSchema
    }


@app.post("/query")
async def query(request: QueryRequest) -> QueryResponse:
    """
    Natural language query endpoint.

    Uses AI router (if available) to understand the query and route to appropriate tool.
    Falls back to keyword matching if AI is unavailable.

    Example:
    {
      "query": "List all production devices",
      "use_llm": true
    }
    """
    # Route query using AI (with fallback to keywords)
    if request.use_llm:
        tool_name, reasoning = await route_query_with_ai(request.query)
    else:
        tool_name = find_tool_by_keywords(request.query)
        reasoning = "Used keyword matching"

    try:
        # Call the tool with minimal arguments (rely on defaults)
        result = await mcp.call_tool(tool_name, {})
        content_blocks, metadata = result
        
        if content_blocks and len(content_blocks) > 0:
            response_text = content_blocks[0].text
        else:
            response_text = "No response"
        
        return QueryResponse(
            success=True,
            tool=tool_name,
            result=response_text,
            reasoning=reasoning
        )
    except Exception as e:
        return QueryResponse(
            success=False,
            tool=tool_name or "unknown",
            result="",
            error=str(e),
            reasoning=reasoning
        )


@app.post("/tool/{tool_name}")
async def call_tool(tool_name: str, request: ToolCall) -> QueryResponse:
    """
    Direct tool execution endpoint.
    
    Call a specific tool with custom parameters.
    
    Example:
    POST /tool/devices_list
    {
      "arguments": {
        "json_output": true,
        "limit": 10
      }
    }
    """
    try:
        # Verify tool exists
        tools = await mcp.list_tools()
        if not any(t.name == tool_name for t in tools):
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
        
        # Call the tool
        result = await mcp.call_tool(tool_name, request.arguments)
        content_blocks, metadata = result
        
        if content_blocks and len(content_blocks) > 0:
            response_text = content_blocks[0].text
        else:
            response_text = "No response"
        
        return QueryResponse(
            success=True,
            tool=tool_name,
            result=response_text
        )
    except HTTPException:
        raise
    except Exception as e:
        return QueryResponse(
            success=False,
            tool=tool_name,
            result="",
            error=str(e)
        )


@app.post("/devices/list")
async def devices_list_shortcut(
    tag: Optional[str] = Query(None),
    json_output: bool = Query(False),
    limit: int = Query(50)
) -> QueryResponse:
    """Shortcut endpoint for listing devices."""
    try:
        args = {"json_output": json_output, "limit": limit}
        if tag:
            args["tag"] = tag
        
        result = await mcp.call_tool("devices_list", args)
        content_blocks, metadata = result
        
        response_text = content_blocks[0].text if content_blocks else "No devices found"
        
        return QueryResponse(
            success=True,
            tool="devices_list",
            result=response_text
        )
    except Exception as e:
        return QueryResponse(
            success=False,
            tool="devices_list",
            result="",
            error=str(e)
        )


@app.post("/devices/show")
async def devices_show_shortcut(ip: str, json_output: bool = False) -> QueryResponse:
    """Shortcut endpoint for showing device details."""
    if not ip:
        raise HTTPException(status_code=400, detail="IP address is required")
    
    try:
        args = {"ip": ip, "json_output": json_output}
        result = await mcp.call_tool("devices_show", args)
        content_blocks, metadata = result
        
        response_text = content_blocks[0].text if content_blocks else "Device not found"
        
        return QueryResponse(
            success=True,
            tool="devices_show",
            result=response_text
        )
    except Exception as e:
        return QueryResponse(
            success=False,
            tool="devices_show",
            result="",
            error=str(e)
        )


@app.post("/backups/history")
async def backups_history_shortcut(
    ip: str,
    limit: int = 20,
    json_output: bool = False
) -> QueryResponse:
    """Shortcut endpoint for viewing backup history."""
    if not ip:
        raise HTTPException(status_code=400, detail="IP address is required")
    
    try:
        args = {"ip": ip, "limit": limit, "json_output": json_output}
        result = await mcp.call_tool("backups_history", args)
        content_blocks, metadata = result
        
        response_text = content_blocks[0].text if content_blocks else "No backups found"
        
        return QueryResponse(
            success=True,
            tool="backups_history",
            result=response_text
        )
    except Exception as e:
        return QueryResponse(
            success=False,
            tool="backups_history",
            result="",
            error=str(e)
        )


@app.post("/health")
async def health_check() -> QueryResponse:
    """Health check endpoint."""
    try:
        result = await mcp.call_tool("health_check", {})
        content_blocks, metadata = result
        
        response_text = content_blocks[0].text if content_blocks else "System healthy"
        
        return QueryResponse(
            success=True,
            tool="health_check",
            result=response_text
        )
    except Exception as e:
        return QueryResponse(
            success=False,
            tool="health_check",
            result="",
            error=str(e)
        )


@app.get("/ai/status")
async def ai_status() -> Dict[str, Any]:
    """Check AI router status and configuration."""
    available = await ai_router.is_available()

    return {
        "enabled": ai_router.enabled,
        "available": available,
        "url": ai_router.mistral_url,
        "status": "connected" if available else "unavailable"
    }


def main():
    """Run the HTTP API server."""
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )


if __name__ == "__main__":
    main()



@app.get("/tools")
async def list_tools() -> Dict[str, Any]:
    """
    List all available tools.
    
    Returns a list of tool names and descriptions that can be called.
    """
    tools = await mcp.list_tools()
    return {
        "tools": [
            {
                "name": tool.name,
                "description": tool.description
            }
            for tool in tools
        ],
        "count": len(tools)
    }


@app.get("/tools/{tool_name}")
async def get_tool_info(tool_name: str) -> Dict[str, Any]:
    """Get detailed information about a specific tool."""
    tools = await mcp.list_tools()
    tool = next((t for t in tools if t.name == tool_name), None)
    
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    
    return {
        "name": tool.name,
        "description": tool.description,
        "inputSchema": tool.inputSchema
    }


@app.post("/tool/{tool_name}")
async def call_tool(tool_name: str, request: ToolCall) -> QueryResponse:
    """
    Direct tool execution endpoint.
    
    Call a specific tool with custom parameters.
    
    Example:
    POST /tool/devices_list
    {
      "arguments": {
        "json_output": true,
        "limit": 10
      }
    }
    """
    try:
        # Verify tool exists
        tools = await mcp.list_tools()
        if not any(t.name == tool_name for t in tools):
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
        
        # Call the tool
        result = await mcp.call_tool(tool_name, request.arguments)
        content_blocks, metadata = result
        
        if content_blocks and len(content_blocks) > 0:
            response_text = content_blocks[0].text
        else:
            response_text = "No response"
        
        return QueryResponse(
            success=True,
            tool=tool_name,
            result=response_text
        )
    except HTTPException:
        raise
    except Exception as e:
        return QueryResponse(
            success=False,
            tool=tool_name,
            result="",
            error=str(e)
        )


@app.post("/devices/list")
async def devices_list_shortcut(
    tag: Optional[str] = None,
    json_output: bool = False,
    limit: int = 50
) -> QueryResponse:
    """Shortcut endpoint for listing devices."""
    try:
        args = {"json_output": json_output, "limit": limit}
        if tag:
            args["tag"] = tag
        
        result = await mcp.call_tool("devices_list", args)
        content_blocks, metadata = result
        
        response_text = content_blocks[0].text if content_blocks else "No devices found"
        
        return QueryResponse(
            success=True,
            tool="devices_list",
            result=response_text
        )
    except Exception as e:
        return QueryResponse(
            success=False,
            tool="devices_list",
            result="",
            error=str(e)
        )


@app.post("/devices/show")
async def devices_show_shortcut(ip: str, json_output: bool = False) -> QueryResponse:
    """Shortcut endpoint for showing device details."""
    if not ip:
        raise HTTPException(status_code=400, detail="IP address is required")
    
    try:
        args = {"ip": ip, "json_output": json_output}
        result = await mcp.call_tool("devices_show", args)
        content_blocks, metadata = result
        
        response_text = content_blocks[0].text if content_blocks else "Device not found"
        
        return QueryResponse(
            success=True,
            tool="devices_show",
            result=response_text
        )
    except Exception as e:
        return QueryResponse(
            success=False,
            tool="devices_show",
            result="",
            error=str(e)
        )


@app.post("/backups/history")
async def backups_history_shortcut(
    ip: str,
    limit: int = 20,
    json_output: bool = False
) -> QueryResponse:
    """Shortcut endpoint for viewing backup history."""
    if not ip:
        raise HTTPException(status_code=400, detail="IP address is required")
    
    try:
        args = {"ip": ip, "limit": limit, "json_output": json_output}
        result = await mcp.call_tool("backups_history", args)
        content_blocks, metadata = result
        
        response_text = content_blocks[0].text if content_blocks else "No backups found"
        
        return QueryResponse(
            success=True,
            tool="backups_history",
            result=response_text
        )
    except Exception as e:
        return QueryResponse(
            success=False,
            tool="backups_history",
            result="",
            error=str(e)
        )


@app.post("/health")
async def health_check() -> QueryResponse:
    """Health check endpoint."""
    try:
        result = await mcp.call_tool("health_check", {})
        content_blocks, metadata = result
        
        response_text = content_blocks[0].text if content_blocks else "System healthy"
        
        return QueryResponse(
            success=True,
            tool="health_check",
            result=response_text
        )
    except Exception as e:
        return QueryResponse(
            success=False,
            tool="health_check",
            result="",
            error=str(e)
        )


def main():
    """Run the HTTP API server."""
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )


if __name__ == "__main__":
    main()
