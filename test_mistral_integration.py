#!/usr/bin/env python
"""
Test script for NetPicker API with Mistral integration.

This demonstrates how to use the HTTP API with your Mistral LLM running on 192.168.1.155:8000
"""

import asyncio
import httpx
import json
from typing import Optional

# Configuration
API_URL = "http://localhost:8001"
MISTRAL_URL = "http://192.168.2.155:8000"


async def check_mistral():
    """Check if Mistral server is available."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{MISTRAL_URL}/v1/models")
            return response.status_code == 200
    except Exception as e:
        print(f"❌ Mistral check failed: {e}")
        return False


async def query_api(query: str, use_llm: bool = True) -> dict:
    """Send a query to the NetPicker API."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{API_URL}/query",
                json={
                    "query": query,
                    "use_llm": use_llm
                }
            )
            return response.json()
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "tool": "unknown",
            "result": ""
        }


async def main():
    """Run test queries."""
    print("=" * 60)
    print("NetPicker API - Mistral Integration Test")
    print("=" * 60)
    
    # Check Mistral availability
    print("\n[1] Checking Mistral availability...")
    mistral_available = await check_mistral()
    if mistral_available:
        print("✓ Mistral is AVAILABLE at", MISTRAL_URL)
    else:
        print("✗ Mistral is NOT available - will use keyword matching")
    
    # Test queries
    test_queries = [
        "List all devices",
        "Show me the production devices",
        "What are the recent backups",
        "Check system health",
        "Show device 192.168.1.194",
        "List compliance policies"
    ]
    
    print("\n[2] Testing queries with Mistral routing...")
    print("-" * 60)
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        result = await query_api(query, use_llm=True)
        
        if result["success"]:
            print(f"  ✓ Tool: {result['tool']}")
            if result.get("reasoning"):
                print(f"  📝 Reasoning: {result['reasoning']}")
            print(f"  Result preview: {result['result'][:100]}...")
        else:
            print(f"  ✗ Error: {result.get('error', 'Unknown error')}")
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)
    
    # Show how to run the servers
    print("\nTo run the full stack:\n")
    print("1. Start Mistral (on your remote machine):")
    print("   ./mistral-7b-instruct-v0.2.Q4_K_M.gguf -ngl 99 -m 192.168.2.155 -p 8000")
    print("\n2. Start NetPicker API (with Mistral URL set):")
    print("   MISTRAL_URL='http://192.168.2.155:8000' netpicker-api")
    print("\n3. Test the API:")
    print("   curl -X POST http://localhost:8001/query \\")
    print("     -H 'Content-Type: application/json' \\")
    print("     -d '{\"query\": \"List all devices\", \"use_llm\": true}'")


if __name__ == "__main__":
    asyncio.run(main())
