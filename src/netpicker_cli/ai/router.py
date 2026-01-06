"""
AI Router Service for NetPicker

Handles intelligent query routing using Mistral LLM.
This module is separate from the core NetPicker API wrapper.
"""

import os
import json
import httpx
from typing import Optional, Tuple
from pydantic import BaseModel


class QueryRouter:
    """AI-powered query router using Mistral LLM."""

    def __init__(self, mistral_url: Optional[str] = None):
        self.mistral_url = mistral_url or os.getenv("MISTRAL_URL", "http://192.168.2.155:8000")
        self.enabled = os.getenv("USE_MISTRAL", "true").lower() == "true"

    async def is_available(self) -> bool:
        """Check if Mistral server is available."""
        if not self.enabled:
            return False

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self.mistral_url}/")
                return response.status_code == 200
        except Exception:
            return False

    async def route_query(self, query: str, available_tools: list) -> Tuple[Optional[str], Optional[str]]:
        """
        Route a natural language query to the appropriate tool using Mistral.

        Args:
            query: Natural language query
            available_tools: List of available tool names

        Returns:
            Tuple of (tool_name, reasoning) or (None, error_message)
        """
        if not self.enabled:
            return None, "AI routing disabled"

        if not await self.is_available():
            return None, "Mistral unavailable"

        try:
            # Build tool list for prompt
            tools_list = "\n".join([f"- {tool}" for tool in available_tools])

            prompt = f"""You are a network management assistant. Based on the user's query,
determine which tool to call from the available tools.

Available tools:
{tools_list}

Respond ONLY with a JSON object in this exact format:
{{"tool": "tool_name", "reasoning": "why this tool"}}

Do not include any other text.

User query: {query}

Response:"""

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.mistral_url}/v1/completions",
                    json={
                        "prompt": prompt,
                        "max_tokens": 200,
                        "temperature": 0.1,
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["text"].strip() if data.get("choices") else ""

                    # Extract JSON from response
                    import re
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(0)
                        result = json.loads(json_str)
                        tool_name = result.get("tool")
                        reasoning = result.get("reasoning", "")

                        # Validate tool exists
                        if tool_name and tool_name in available_tools:
                            return tool_name, reasoning

                return None, f"Mistral returned {response.status_code}"

        except Exception as e:
            return None, f"Mistral error: {str(e)}"


class QueryRouterResponse(BaseModel):
    """Response from query routing."""
    tool: Optional[str] = None
    reasoning: Optional[str] = None
    error: Optional[str] = None
    method: str  # "mistral" or "keyword"


# Global router instance
router = QueryRouter()