"""
Shared state definition for the Travel Planning LangGraph.
Every agent node reads from and writes to this TypedDict.
"""

from typing import TypedDict, List, Optional, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class TravelState(TypedDict):
    # ------------------------------------------------------------------
    # User inputs (set once at graph start)
    # ------------------------------------------------------------------
    thread_id: str
    origin: str                  # e.g. "Cairo, Egypt"
    destination: str             # e.g. "Paris, France"
    departure_date: str          # ISO format YYYY-MM-DD
    return_date: str             # ISO format YYYY-MM-DD
    num_travelers: int
    activities: List[str]        # e.g. ["museums", "food tours", "hiking"]
    budget: float                # Total trip budget
    budget_currency: str         # e.g. "USD"

    # ------------------------------------------------------------------
    # Agent results (populated by specialized nodes)
    # ------------------------------------------------------------------
    flight_results: Optional[dict]
    weather_results: Optional[dict]
    hotel_results: Optional[dict]
    activity_results: Optional[dict]

    # ------------------------------------------------------------------
    # Plan iteration (human-in-the-loop)
    # ------------------------------------------------------------------
    plan_draft: Optional[str]    # Markdown travel plan draft
    user_feedback: Optional[str] # Feedback from user for revision
    approved: bool               # True when user approves
    revision_count: int          # Number of revisions so far

    # ------------------------------------------------------------------
    # Conversation history
    # ------------------------------------------------------------------
    messages: Annotated[List[BaseMessage], add_messages]
