"""
Activities Agent Node.
Delegates entirely to MCPManager — uses official Tavily MCP (npx stdio).
"""

import logging
from datetime import datetime
from Travel_State import TravelState
from mcp_client.mcp_manager import mcp_manager

logger = logging.getLogger(__name__)


async def activities_node(state: TravelState) -> dict:
    """Search for activities via official Tavily MCP."""
    logger.info(
        "ActivitiesAgent: %s activities in %s",
        state.get("activities", []),
        state["destination"],
    )

    # Calculate per-person daily activity budget (~15% of total)
    try:
        dep = datetime.strptime(state["departure_date"], "%Y-%m-%d")
        ret = datetime.strptime(state["return_date"], "%Y-%m-%d")
        nights = max(1, (ret - dep).days)
    except Exception:
        nights = 5

    budget_per_person_day = (
        state["budget"] * 0.15
        / max(state["num_travelers"], 1)
        / nights
    )

    result = await mcp_manager.search_activities(
        destination=state["destination"],
        activities=state.get("activities") or ["sightseeing", "culture", "food"],
        travel_dates=f"{state['departure_date']} to {state['return_date']}",
        budget_per_person_per_day=budget_per_person_day,
    )
    logger.info("ActivitiesAgent: got %d results", len(result.get("activities", [])))
    return {"activity_results": result}
