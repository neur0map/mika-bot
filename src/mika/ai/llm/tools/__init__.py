"""LLM tool/function-calling support and the built-in tools."""

from __future__ import annotations

from mika.ai.llm.tools.registry import Tool, ToolRegistry
from mika.ai.llm.tools.web_search import web_search_tool

__all__ = ["Tool", "ToolRegistry", "web_search_tool"]
