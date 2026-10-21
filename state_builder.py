"""
Builds the initial TravelState from user form input.
Called once when the user submits the travel planning form.
"""

from Travel_State import TravelState
from typing import List


def build_initial_state(user_input: dict) -> TravelState:
    """
    Convert raw user form data into a valid TravelState.

    Args:
        user_input: dict with keys matching the form fields.

    Returns:
        TravelState ready to be passed to graph.ainvoke().
    """
    return TravelState(
        thread_id=user_input.get("thread_id", ""),
        origin=user_input["origin"].strip(),
        destination=user_input["destination"].strip(),
        departure_date=user_input["departure_date"],
        return_date=user_input["return_date"],
        num_travelers=int(user_input.get("num_travelers", 1)),
        activities=_parse_activities(user_input.get("activities", [])),
        budget=float(user_input.get("budget", 2000)),
        budget_currency=user_input.get("budget_currency", "USD").upper(),
        # Agent results — empty at start
        flight_results=None,
        weather_results=None,
        hotel_results=None,
        activity_results=None,
        # Plan iteration — empty at start
        plan_draft=None,
        user_feedback=None,
        approved=False,
        revision_count=0,
        # No messages yet
        messages=[],
    )


def _parse_activities(activities) -> List[str]:
    """Normalise activities from various input forms (list, comma string)."""
    if isinstance(activities, list):
        return [a.strip() for a in activities if a.strip()]
    if isinstance(activities, str):
        return [a.strip() for a in activities.split(",") if a.strip()]
    return []
