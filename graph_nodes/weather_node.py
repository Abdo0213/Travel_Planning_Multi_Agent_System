"""
Weather Agent Node.
Delegates entirely to MCPManager — no MCP protocol code here.

Calls TWO weather tools:
  • get_weather()           — full period forecast (for packing tips, overview)
  • get_forecast_for_date() — per-day forecast for each travel day
    (enriches weather_results with day-level detail for the planner)
"""

import logging
from datetime import datetime, timedelta
from Travel_State import TravelState
from mcp_client.mcp_manager import mcp_manager

logger = logging.getLogger(__name__)


async def weather_node(state: TravelState) -> dict:
    """
    Fetch weather for the entire trip AND per-day forecasts.
    Both results are merged into weather_results.
    """
    city = state["destination"]
    departure = state["departure_date"]
    return_date = state["return_date"]
    logger.info("WeatherAgent: fetching forecast for %s (%s → %s)", city, departure, return_date)

    # 1. Full period forecast
    period_forecast = await mcp_manager.get_weather(city, departure, return_date)

    # 2. Per-day forecasts for each day of the trip
    daily_detail = {}
    try:
        dep_dt = datetime.strptime(departure, "%Y-%m-%d")
        ret_dt = datetime.strptime(return_date, "%Y-%m-%d")
        days = (ret_dt - dep_dt).days + 1
        for i in range(min(days, 5)):   # OWM free tier: 5-day window
            day_str = (dep_dt + timedelta(days=i)).strftime("%Y-%m-%d")
            day_forecast = await mcp_manager.get_forecast_for_date(city, day_str)
            if day_forecast.get("available"):
                daily_detail[day_str] = day_forecast
    except Exception as e:
        logger.warning("WeatherAgent: per-day forecast failed: %s", e)

    weather_results = {
        **period_forecast,
        "daily_detail": daily_detail,   # keyed by date string
    }

    logger.info(
        "WeatherAgent: %d period days + %d detailed days",
        len(period_forecast.get("daily_forecasts", [])),
        len(daily_detail),
    )
    return {"weather_results": weather_results}
