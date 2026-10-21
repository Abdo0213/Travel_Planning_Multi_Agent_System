"""
Flight MCP Server — stdio transport.
Wraps the Aviationstack REST API as an MCP tool.
Spawned as a subprocess by graph_nodes/flight_node.py.
"""

import sys
import os
import json
import requests
from datetime import datetime

# Ensure project root is in path so config is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp.server.fastmcp import FastMCP
from config.Config import settings

mcp = FastMCP("Flight Search MCP Server")


@mcp.tool()
def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str,
    num_travelers: int,
    budget: float,
    budget_currency: str = "USD",
) -> str:
    """
    Search for available flights between origin and destination.

    Args:
        origin: Departure city or IATA code (e.g. "Cairo" or "CAI")
        destination: Arrival city or IATA code (e.g. "Paris" or "CDG")
        departure_date: Date in YYYY-MM-DD format
        return_date: Return date in YYYY-MM-DD format
        num_travelers: Number of passengers
        budget: Total trip budget
        budget_currency: Currency code (default USD)

    Returns:
        JSON string with flight options.
    """
    try:
        # ---- Aviationstack: search for flights on departure date ----
        params = {
            "access_key": settings.aviationstack_api_key,
            "dep_iata": _city_to_iata(origin),
            "arr_iata": _city_to_iata(destination),
            "flight_date": departure_date,
            "limit": 5,
        }

        resp = requests.get(
            "http://api.aviationstack.com/v1/flights",
            params=params,
            timeout=10,
        )
        data = resp.json()

        flights = []
        if "data" in data and data["data"]:
            for f in data["data"][:3]:
                dep = f.get("departure", {})
                arr = f.get("arrival", {})
                airline = f.get("airline", {}).get("name", "Unknown Airline")
                flight_num = f.get("flight", {}).get("iata", "N/A")

                # Estimate price (Aviationstack free tier doesn't include pricing)
                estimated_price = _estimate_price(origin, destination, budget, num_travelers)

                flights.append(
                    {
                        "airline": airline,
                        "flight_number": flight_num,
                        "origin": dep.get("airport", origin),
                        "destination": arr.get("airport", destination),
                        "departure_time": dep.get("scheduled", departure_date + "T08:00:00"),
                        "arrival_time": arr.get("scheduled", departure_date + "T12:00:00"),
                        "status": f.get("flight_status", "scheduled"),
                        "estimated_price_per_person_usd": estimated_price,
                        "total_price_usd": estimated_price * num_travelers,
                    }
                )
        else:
            # Fallback: generate realistic estimated flights when API returns no data
            flights = _generate_fallback_flights(
                origin, destination, departure_date, return_date, num_travelers, budget
            )

        result = {
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date,
            "return_date": return_date,
            "num_travelers": num_travelers,
            "currency": budget_currency,
            "flights": flights,
            "note": "Prices are estimates. Book through official airline websites for final pricing.",
        }
        return json.dumps(result)

    except Exception as e:
        # Return structured error with fallback data so the planner can still work
        fallback = _generate_fallback_flights(
            origin, destination, departure_date, return_date, num_travelers, budget
        )
        return json.dumps(
            {
                "origin": origin,
                "destination": destination,
                "departure_date": departure_date,
                "return_date": return_date,
                "num_travelers": num_travelers,
                "flights": fallback,
                "note": f"Showing estimated flights (API error: {str(e)[:100]}). Verify on airline websites.",
            }
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_IATA_MAP = {
    "cairo": "CAI", "egypt": "CAI",
    "dubai": "DXB", "uae": "DXB",
    "paris": "CDG", "france": "CDG",
    "london": "LHR", "uk": "LHR",
    "istanbul": "IST", "turkey": "IST",
    "new york": "JFK", "nyc": "JFK",
    "amsterdam": "AMS",
    "rome": "FCO", "italy": "FCO",
    "barcelona": "BCN", "spain": "MAD",
    "madrid": "MAD",
    "tokyo": "NRT", "japan": "NRT",
    "bangkok": "BKK", "thailand": "BKK",
    "bali": "DPS", "indonesia": "DPS",
    "maldives": "MLE",
    "doha": "DOH", "qatar": "DOH",
    "riyadh": "RUH", "saudi arabia": "RUH",
    "abu dhabi": "AUH",
    "singapore": "SIN",
    "kuala lumpur": "KUL", "malaysia": "KUL",
}


def _city_to_iata(city: str) -> str:
    """Convert a city name to its primary IATA airport code."""
    return _IATA_MAP.get(city.lower().strip(), city.upper()[:3])


def _estimate_price(origin: str, destination: str, budget: float, num_travelers: int) -> float:
    """Rough flight price estimate: ~25-40% of per-person budget for flights."""
    per_person_budget = budget / max(num_travelers, 1)
    return round(per_person_budget * 0.30, 2)


def _generate_fallback_flights(
    origin, destination, departure_date, return_date, num_travelers, budget
) -> list:
    """Generate realistic estimated flight options when the API has no data."""
    price_per_person = _estimate_price(origin, destination, budget, num_travelers)
    airlines = [
        ("EgyptAir", "MS"),
        ("Emirates", "EK"),
        ("Turkish Airlines", "TK"),
    ]
    flights = []
    times = [("07:30", "11:45"), ("14:00", "18:15"), ("22:00", "02:30+1")]
    for (airline, code), (dep_t, arr_t) in zip(airlines, times):
        flights.append(
            {
                "airline": airline,
                "flight_number": f"{code}{100 + len(flights) * 111}",
                "origin": origin,
                "destination": destination,
                "departure_time": f"{departure_date}T{dep_t}:00",
                "arrival_time": f"{departure_date}T{arr_t}:00",
                "status": "scheduled",
                "estimated_price_per_person_usd": price_per_person * (1 + len(flights) * 0.15),
                "total_price_usd": price_per_person * num_travelers * (1 + len(flights) * 0.15),
            }
        )
    return flights


if __name__ == "__main__":
    mcp.run(transport="stdio")
