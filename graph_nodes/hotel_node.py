"""
Hotel Agent Node.
Delegates entirely to MCPManager — uses official Tavily MCP (npx stdio).
"""

import logging
from Travel_State import TravelState
from mcp_client.mcp_manager import mcp_manager

logger = logging.getLogger(__name__)


async def hotel_node(state: TravelState) -> dict:
    """Search for hotels via official Tavily MCP."""
    logger.info("HotelAgent: searching in %s", state["destination"])
    result = await mcp_manager.search_hotels(
        destination=state["destination"],
        check_in=state["departure_date"],
        check_out=state["return_date"],
        num_travelers=state["num_travelers"],
        budget=state["budget"],
        budget_currency=state["budget_currency"],
    )
    logger.info("HotelAgent: got %d results", len(result.get("hotels", [])))
    return {"hotel_results": result}
