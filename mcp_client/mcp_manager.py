"""
Central MCP Client Manager.

This is the SINGLE place that knows about every MCP server in the system.
Graph nodes never touch MCP protocol directly — they call high-level methods here.

Server registry
───────────────
  "flight"  → stdio → MCP_Servers/flight_mcp_server.py   (local Python, Aviationstack)
  "weather" → stdio → MCP_Servers/weather_mcp_server.py  (local Python, OpenWeatherMap)
  "tavily"  → stdio → npx -y tavily-mcp                  (official Tavily MCP, Node.js)

Transport
─────────
  All servers use stdio transport (spawned as subprocesses).
  This is intentional: flight and weather are local scripts; Tavily uses its
  official MCP package via npx so we don't have to maintain that code ourselves.

Usage in nodes
──────────────
  from mcp_client.mcp_manager import mcp_manager
  result = await mcp_manager.search_flights(origin=..., destination=..., ...)
"""

import sys
import os
import json
import logging
from datetime import datetime
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config.Config import settings

logger = logging.getLogger(__name__)
ROOT = Path(__file__).parent.parent   # project root


class MCPManager:
    """
    Central coordinator for all MCP servers.

    Maintains a server registry and provides:
      • call_tool()  — generic, low-level dispatcher
      • Semantic methods used directly by each LangGraph node
    """

    # ------------------------------------------------------------------
    # Server Registry
    # ------------------------------------------------------------------
    @property
    def _servers(self) -> dict[str, StdioServerParameters]:
        """
        Return StdioServerParameters for every registered MCP server.
        Built lazily so settings are available when first accessed.
        """
        return {
            # ── Local Python MCP servers (stdio) ──────────────────────
            "flight": StdioServerParameters(
                command=sys.executable,
                args=[str(ROOT / "MCP_Servers" / "flight_mcp_server.py")],
                env=dict(os.environ),   # inherit all env vars (API keys etc.)
            ),
            "weather": StdioServerParameters(
                command=sys.executable,
                args=[str(ROOT / "MCP_Servers" / "weather_mcp_server.py")],
                env=dict(os.environ),
            ),
            # ── Official Tavily MCP server (npx, stdio) ───────────────
            # Requires Node.js: https://github.com/tavily-ai/tavily-mcp
            # Exposes tools: tavily_search, tavily_extract
            "tavily": StdioServerParameters(
                command="npx",
                args=["-y", "tavily-mcp"],
                env={
                    **os.environ,
                    "TAVILY_API_KEY": settings.tavily_api_key,
                },
            ),
        }

    # ------------------------------------------------------------------
    # Core dispatcher
    # ------------------------------------------------------------------
    async def call_tool(
        self, server_name: str, tool_name: str, args: dict
    ) -> str:
        """
        Connect to a registered MCP server via stdio, call a tool, and
        return the raw text result.

        Args:
            server_name: Key in the server registry ("flight", "weather", "tavily")
            tool_name:   MCP tool name to call
            args:        Tool arguments dict

        Returns:
            Raw text content from the tool response (usually JSON).
        """
        servers = self._servers
        if server_name not in servers:
            raise ValueError(
                f"Unknown MCP server '{server_name}'. "
                f"Registered servers: {list(servers)}"
            )

        server_params = servers[server_name]
        logger.info(
            "MCPManager ▶ [%s] %s(%s)",
            server_name, tool_name, str(args)[:100]
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, args)
                raw = result.content[0].text if result.content else "{}"
                logger.info("MCPManager ◀ [%s] %s — %d bytes", server_name, tool_name, len(raw))
                return raw

    # ------------------------------------------------------------------
    # ✈️  Flight tools
    # ------------------------------------------------------------------
    async def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str,
        num_travelers: int,
        budget: float,
        budget_currency: str = "USD",
    ) -> dict:
        """Search for available flights via Aviationstack (local stdio MCP)."""
        try:
            raw = await self.call_tool("flight", "search_flights", {
                "origin": origin,
                "destination": destination,
                "departure_date": departure_date,
                "return_date": return_date,
                "num_travelers": num_travelers,
                "budget": budget,
                "budget_currency": budget_currency,
            })
            return json.loads(raw)
        except Exception as e:
            logger.error("search_flights failed: %s", e)
            return {
                "origin": origin, "destination": destination,
                "flights": [], "error": str(e),
                "note": "Flight search failed. Check airline websites directly.",
            }

    # ------------------------------------------------------------------
    # 🌤️  Weather tools
    # ------------------------------------------------------------------
    async def get_weather(
        self,
        city: str,
        departure_date: str,
        return_date: str,
    ) -> dict:
        """
        Get multi-day weather forecast for the entire travel period.
        Uses local weather MCP server (OpenWeatherMap).
        """
        try:
            raw = await self.call_tool("weather", "get_weather", {
                "city": city,
                "departure_date": departure_date,
                "return_date": return_date,
            })
            return json.loads(raw)
        except Exception as e:
            logger.error("get_weather failed: %s", e)
            return {
                "city": city, "daily_forecasts": [],
                "overall_summary": f"Weather unavailable ({e}). Check weather.com.",
                "packing_tips": ["Pack layers", "Bring a rain jacket"],
            }

    async def get_forecast_for_date(self, city: str, date: str) -> dict:
        """
        Get weather forecast for a SINGLE specific date.
        Useful for the planner when building day-by-day itineraries.
        Uses local weather MCP server.

        Args:
            city: Destination city name
            date: Date in YYYY-MM-DD format

        Returns:
            Weather data dict for that specific day.
        """
        try:
            raw = await self.call_tool("weather", "get_forecast_for_date", {
                "city": city,
                "date": date,
            })
            return json.loads(raw)
        except Exception as e:
            logger.error("get_forecast_for_date(%s, %s) failed: %s", city, date, e)
            return {
                "city": city, "date": date, "available": False, "error": str(e),
            }

    # ------------------------------------------------------------------
    # 🏨  Hotel tools — official Tavily MCP (npx)
    # ------------------------------------------------------------------
    async def search_hotels(
        self,
        destination: str,
        check_in: str,
        check_out: str,
        num_travelers: int,
        budget: float,
        budget_currency: str = "USD",
    ) -> dict:
        """
        Search for hotels using the official Tavily MCP server (npx stdio).
        Tool called: tavily_search
        """
        try:
            nights = max(1, (
                datetime.strptime(check_out, "%Y-%m-%d") -
                datetime.strptime(check_in, "%Y-%m-%d")
            ).days)
            nightly_budget = round(budget * 0.35 / nights)

            query = (
                f"best hotels resorts {destination} {check_in} to {check_out} "
                f"{num_travelers} guests budget {nightly_budget} {budget_currency} "
                f"per night rating reviews booking"
            )

            raw = await self.call_tool("tavily", "tavily_search", {
                "query": query,
                "search_depth": "advanced",
                "max_results": 6,
                "include_answer": True,
            })
            data = json.loads(raw)

            return {
                "destination": destination,
                "check_in": check_in,
                "check_out": check_out,
                "nights": nights,
                "num_travelers": num_travelers,
                "budget_per_night_usd": nightly_budget,
                "hotels": data.get("results", data) if isinstance(data, dict) else data,
                "search_summary": data.get("answer", "") if isinstance(data, dict) else "",
            }
        except Exception as e:
            logger.error("search_hotels failed: %s", e)
            return {
                "destination": destination,
                "hotels": [], "error": str(e),
                "note": f"Hotel search failed. Try booking.com for {destination}.",
            }

    # ------------------------------------------------------------------
    # 🎯  Activities tools — official Tavily MCP (npx)
    # ------------------------------------------------------------------
    async def search_activities(
        self,
        destination: str,
        activities: list,
        travel_dates: str,
        budget_per_person_per_day: float,
    ) -> dict:
        """
        Search for activities using the official Tavily MCP server (npx stdio).
        Tool called: tavily_search
        """
        try:
            activity_str = " ".join(activities) if activities else "sightseeing culture food"
            query = (
                f"top things to do {destination} {activity_str} "
                f"tours experiences attractions {travel_dates} must-visit"
            )

            raw = await self.call_tool("tavily", "tavily_search", {
                "query": query,
                "search_depth": "advanced",
                "max_results": 8,
                "include_answer": True,
            })
            data = json.loads(raw)

            return {
                "destination": destination,
                "requested_activities": activities,
                "travel_dates": travel_dates,
                "activities": data.get("results", data) if isinstance(data, dict) else data,
                "search_summary": data.get("answer", "") if isinstance(data, dict) else "",
            }
        except Exception as e:
            logger.error("search_activities failed: %s", e)
            return {
                "destination": destination,
                "requested_activities": activities,
                "activities": [], "error": str(e),
                "note": f"Activity search failed. Try tripadvisor.com for {destination}.",
            }

    # ------------------------------------------------------------------
    # 🔍  List available servers & tools (utility)
    # ------------------------------------------------------------------
    def list_servers(self) -> dict:
        """Return a summary of all registered MCP servers."""
        return {
            name: {
                "command": params.command,
                "args": params.args,
                "transport": "stdio",
            }
            for name, params in self._servers.items()
        }


# ── Module-level singleton ─────────────────────────────────────────────────
# Import this in every graph node that needs to call an external service.
# Example:
#   from mcp_client.mcp_manager import mcp_manager
#   result = await mcp_manager.search_flights(...)
mcp_manager = MCPManager()
