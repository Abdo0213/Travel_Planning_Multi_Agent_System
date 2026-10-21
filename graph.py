"""
LangGraph StateGraph definition for the Travel Planning Multi-Agent System.

Graph flow:
  START
    → flight_agent          (Aviationstack via stdio MCP)
    → weather_agent         (OpenWeatherMap via stdio MCP)
    → hotel_agent           (Tavily via HTTP MCP)
    → activities_agent      (Tavily via HTTP MCP)
    → planner_agent         (OpenRouter LLM)
    → human_review          (interrupt — waits for user approval/feedback)
    → (approved) → END
    → (feedback) → planner_agent  (revision loop)
"""

import logging
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt

from Travel_State import TravelState
from graph_nodes.flight_node import flight_node
from graph_nodes.weather_node import weather_node
from graph_nodes.hotel_node import hotel_node
from graph_nodes.activities_node import activities_node
from graph_nodes.planner_node import planner_node

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Human Review Node (uses LangGraph interrupt)
# ---------------------------------------------------------------------------

def human_review_node(state: TravelState) -> dict:
    """
    Pause graph execution and wait for the user to review the plan draft.
    The graph will resume when graphController calls graph.ainvoke(Command(resume=...)).
    """
    logger.info(
        "HumanReview: pausing for review (revision #%d)", state.get("revision_count", 0)
    )

    # interrupt() checkpoints the state and pauses execution.
    # The dict passed to interrupt() is exposed to the API caller via get_state().
    human_response = interrupt(
        {
            "plan_draft": state.get("plan_draft", ""),
            "revision_count": state.get("revision_count", 0),
            "message": "Please review your travel plan. Approve it or provide feedback for revision.",
        }
    )

    # human_response is the value passed to Command(resume=...) by graphController
    if human_response.get("approved", False):
        logger.info("HumanReview: plan approved!")
        return {"approved": True, "user_feedback": None}
    else:
        feedback = human_response.get("feedback", "Please improve the plan.")
        revision_count = state.get("revision_count", 0) + 1
        logger.info("HumanReview: revision requested — %s", feedback[:80])
        return {
            "approved": False,
            "user_feedback": feedback,
            "revision_count": revision_count,
        }


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def route_after_review(state: TravelState) -> str:
    """Route to END if approved, back to planner for revision otherwise."""
    if state.get("approved", False):
        return END
    return "planner_agent"


# ---------------------------------------------------------------------------
# Graph Builder
# ---------------------------------------------------------------------------

def build_graph(checkpointer):
    """
    Build and compile the LangGraph StateGraph with the given checkpointer.

    Args:
        checkpointer: An AsyncPostgresSaver instance for state persistence.

    Returns:
        Compiled LangGraph ready for ainvoke / astream.
    """
    builder = StateGraph(TravelState)

    # --- Register nodes ---
    builder.add_node("flight_agent", flight_node)
    builder.add_node("weather_agent", weather_node)
    builder.add_node("hotel_agent", hotel_node)
    builder.add_node("activities_agent", activities_node)
    builder.add_node("planner_agent", planner_node)
    builder.add_node("human_review", human_review_node)

    # --- Define flow ---
    builder.add_edge(START, "flight_agent")
    builder.add_edge("flight_agent", "weather_agent")
    builder.add_edge("weather_agent", "hotel_agent")
    builder.add_edge("hotel_agent", "activities_agent")
    builder.add_edge("activities_agent", "planner_agent")
    builder.add_edge("planner_agent", "human_review")

    # After human_review: approved → END, feedback → planner (revision loop)
    builder.add_conditional_edges("human_review", route_after_review)

    return builder.compile(checkpointer=checkpointer)
