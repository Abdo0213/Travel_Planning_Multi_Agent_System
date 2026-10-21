"""
DEPRECATED — Tavily now uses its official MCP server.

This file is NO LONGER used. The Tavily MCP server is the official
open-source package run via npx:

    npx -y tavily-mcp

It is registered in MCPManager under the key "tavily":
    mcp_client/mcp_manager.py → _servers["tavily"]

The official server exposes:
    • tavily_search  — web search with configurable depth
    • tavily_extract — extract content from a list of URLs

Requires Node.js to be installed on your system.
TAVILY_API_KEY must be set in .env (MCPManager passes it automatically).
"""

raise ImportError(
    "tavily_mcp_server.py is deprecated. "
    "Use mcp_client.mcp_manager.mcp_manager.search_hotels() / search_activities() instead."
)
