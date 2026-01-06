"""
AI Router module for NetPicker

Provides intelligent query routing using Mistral LLM.
"""

from .router import QueryRouter, QueryRouterResponse, router

__all__ = ["QueryRouter", "QueryRouterResponse", "router"]