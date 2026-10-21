"""
Flight Agent Node.
Delegates entirely to MCPManager — no MCP protocol code here.
"""

import logging
from Travel_State import TravelState
from mcp_client.mcp_manager import mcp_manager

logger = logging.getLogger(__name__)


async def flight_node(state: TravelState) -> dict:
    """Search for flights via Aviationstack (local stdio MCP)."""
    logger.info("FlightAgent: %s → %s", state["origin"], state["destination"])
    result = await mcp_manager.search_flights(
        origin=state["origin"],
        destination=state["destination"],
        departure_date=state["departure_date"],
        return_date=state["return_date"],
        num_travelers=state["num_travelers"],
        budget=state["budget"],
        budget_currency=state["budget_currency"],
    )
    logger.info("FlightAgent: got %d options", len(result.get("flights", [])))
    return {"flight_results": result}
