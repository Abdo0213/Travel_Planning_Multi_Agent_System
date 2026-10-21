"""
Graph Controller — manages graph lifecycle and the human-in-the-loop cycle.
All public functions are async and use the compiled graph stored at module level.
"""

import logging
from typing import AsyncGenerator, Optional

from langgraph.types import Command

from Travel_State import TravelState

logger = logging.getLogger(__name__)

# Module-level compiled graph — set by app/server.py at startup
_graph = None


def set_graph(graph) -> None:
    """Register the compiled graph. Called once during application startup."""
    global _graph
    _graph = graph
    logger.info("GraphController: graph registered.")


def get_graph():
    """Return the compiled graph. Raises if not yet initialised."""
    if _graph is None:
        raise RuntimeError("Graph has not been initialised. Call set_graph() first.")
    return _graph


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def start_plan(thread_id: str, initial_state: TravelState) -> dict:
    """
    Start a new travel planning session.
    Runs the graph until the human_review interrupt is hit.

    Returns:
        dict with keys: plan_draft, revision_count, interrupted, state_values
    """
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}

    logger.info("GraphController: starting plan for thread %s", thread_id)

    # ainvoke runs until interrupt() — returns at that point
    await graph.ainvoke(initial_state, config)

    # Read the persisted state (contains plan_draft from planner node)
    snapshot = await graph.aget_state(config)
    values = snapshot.values if snapshot else {}

    return {
        "plan_draft": values.get("plan_draft", ""),
        "revision_count": values.get("revision_count", 0),
        "interrupted": bool(snapshot and snapshot.next),
        "state_values": values,
    }


async def resume_with_feedback(thread_id: str, feedback: str) -> dict:
    """
    Resume the graph after the user provides revision feedback.
    The graph will re-run planner_agent and pause again at human_review.

    Args:
        thread_id: The session thread ID
        feedback: User's revision request

    Returns:
        dict with updated plan_draft
    """
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}

    logger.info(
        "GraphController: resuming with feedback for thread %s: %s",
        thread_id,
        feedback[:80],
    )

    await graph.ainvoke(
        Command(resume={"approved": False, "feedback": feedback}),
        config,
    )

    snapshot = await graph.aget_state(config)
    values = snapshot.values if snapshot else {}

    return {
        "plan_draft": values.get("plan_draft", ""),
        "revision_count": values.get("revision_count", 0),
        "interrupted": bool(snapshot and snapshot.next),
        "state_values": values,
    }


async def approve_plan(thread_id: str) -> dict:
    """
    Resume the graph with user approval — graph will complete.

    Args:
        thread_id: The session thread ID

    Returns:
        dict with final plan and approved=True
    """
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}

    logger.info("GraphController: approving plan for thread %s", thread_id)

    await graph.ainvoke(Command(resume={"approved": True}), config)

    snapshot = await graph.aget_state(config)
    values = snapshot.values if snapshot else {}

    return {
        "plan_draft": values.get("plan_draft", ""),
        "revision_count": values.get("revision_count", 0),
        "approved": values.get("approved", True),
        "interrupted": bool(snapshot and snapshot.next),
        "state_values": values,
    }


async def get_plan_state(thread_id: str) -> Optional[dict]:
    """
    Get the current state of a planning session.

    Args:
        thread_id: The session thread ID

    Returns:
        dict with current state values, or None if thread not found.
    """
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}

    snapshot = await graph.aget_state(config)
    if snapshot is None or not snapshot.values:
        return None

    values = snapshot.values
    return {
        "plan_draft": values.get("plan_draft"),
        "revision_count": values.get("revision_count", 0),
        "approved": values.get("approved", False),
        "interrupted": bool(snapshot.next),
        "origin": values.get("origin"),
        "destination": values.get("destination"),
        "departure_date": values.get("departure_date"),
        "return_date": values.get("return_date"),
        "num_travelers": values.get("num_travelers"),
        "budget": values.get("budget"),
        "budget_currency": values.get("budget_currency"),
        "has_flights": values.get("flight_results") is not None,
        "has_weather": values.get("weather_results") is not None,
        "has_hotels": values.get("hotel_results") is not None,
        "has_activities": values.get("activity_results") is not None,
    }


async def stream_plan_events(
    thread_id: str, initial_state: TravelState
) -> AsyncGenerator[dict, None]:
    """
    Stream graph execution events as each node completes.
    Yields dicts describing node completion for SSE streaming.
    """
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}

    node_labels = {
        "flight_agent": {"label": "Searching for flights", "emoji": "✈️"},
        "weather_agent": {"label": "Checking weather forecast", "emoji": "🌤️"},
        "hotel_agent": {"label": "Finding hotels & resorts", "emoji": "🏨"},
        "activities_agent": {"label": "Discovering activities", "emoji": "🎯"},
        "planner_agent": {"label": "Creating your travel plan", "emoji": "📋"},
        "human_review": {"label": "Plan ready for review", "emoji": "✅"},
    }

    async for chunk in graph.astream(initial_state, config, stream_mode="updates"):
        for node_name in chunk:
            meta = node_labels.get(node_name, {"label": node_name, "emoji": "🔄"})
            yield {
                "event": "node_complete",
                "node": node_name,
                "label": meta["label"],
                "emoji": meta["emoji"],
            }

    # After stream ends (interrupt hit), get the plan draft
    snapshot = await graph.aget_state(config)
    values = snapshot.values if snapshot else {}
    yield {
        "event": "plan_ready",
        "plan_draft": values.get("plan_draft", ""),
        "revision_count": values.get("revision_count", 0),
    }


async def stream_revision_events(
    thread_id: str, feedback: str
) -> AsyncGenerator[dict, None]:
    """
    Stream revision events when user provides feedback.
    """
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}

    async for chunk in graph.astream(
        Command(resume={"approved": False, "feedback": feedback}),
        config,
        stream_mode="updates",
    ):
        for node_name in chunk:
            if node_name == "planner_agent":
                yield {
                    "event": "node_complete",
                    "node": node_name,
                    "label": "Revising your travel plan",
                    "emoji": "✏️",
                }

    snapshot = await graph.aget_state(config)
    values = snapshot.values if snapshot else {}
    yield {
        "event": "plan_ready",
        "plan_draft": values.get("plan_draft", ""),
        "revision_count": values.get("revision_count", 0),
    }
