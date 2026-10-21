"""
Planner Agent Node.
Uses the OpenRouter LLM (via langchain-openai) to synthesise all agent
results into a rich Markdown travel plan draft.
Also handles revision cycles when the user provides feedback.
"""

import json
import logging
from langchain_core.messages import SystemMessage, HumanMessage

from Travel_State import TravelState
from llm.openrouter import get_llm
from prompts import PLANNER_SYSTEM_PROMPT, PLANNER_REVISION_PROMPT

logger = logging.getLogger(__name__)


async def planner_node(state: TravelState) -> dict:
    """
    LangGraph node: generates or revises the travel plan draft using the LLM.
    """
    llm = get_llm(temperature=0.7)
    is_revision = bool(state.get("user_feedback") and state.get("revision_count", 0) > 0)

    if is_revision:
        logger.info(
            "PlannerAgent: revision #%d for feedback: %s",
            state["revision_count"],
            state["user_feedback"][:80],
        )
        system_prompt = PLANNER_REVISION_PROMPT.format(
            current_plan=state.get("plan_draft", ""),
            user_feedback=state["user_feedback"],
            revision_count=state["revision_count"],
        )
    else:
        logger.info("PlannerAgent: generating initial travel plan draft")
        system_prompt = PLANNER_SYSTEM_PROMPT

    # Build user message with all agent data
    user_message = _build_context_message(state)

    try:
        response = await llm.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_message),
            ]
        )

        plan_draft = response.content
        new_revision_count = state.get("revision_count", 0) + (1 if is_revision else 0)

        logger.info("PlannerAgent: plan draft generated (%d chars)", len(plan_draft))
        return {
            "plan_draft": plan_draft,
            "revision_count": new_revision_count,
            "user_feedback": None,  # Clear feedback after processing
        }

    except Exception as e:
        logger.error("PlannerAgent error: %s", e)
        fallback = _generate_fallback_plan(state)
        return {
            "plan_draft": fallback,
            "revision_count": state.get("revision_count", 0),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_context_message(state: TravelState) -> str:
    """Format all agent results into a structured context for the LLM."""
    flights = state.get("flight_results") or {}
    weather = state.get("weather_results") or {}
    hotels = state.get("hotel_results") or {}
    activities = state.get("activity_results") or {}

    context = f"""Please create a comprehensive travel plan with the following information:

## Trip Details
- **Origin**: {state['origin']}
- **Destination**: {state['destination']}
- **Departure Date**: {state['departure_date']}
- **Return Date**: {state['return_date']}
- **Travelers**: {state['num_travelers']} person(s)
- **Total Budget**: {state['budget']} {state['budget_currency']}
- **Preferred Activities**: {', '.join(state.get('activities', [])) or 'general sightseeing'}

## ✈️ Flight Data
{json.dumps(flights, indent=2, ensure_ascii=False)[:2000]}

## 🌤️ Weather Forecast
{json.dumps(weather, indent=2, ensure_ascii=False)[:1500]}

## 🏨 Hotel Options
{json.dumps(hotels, indent=2, ensure_ascii=False)[:2000]}

## 🎯 Activities & Experiences
{json.dumps(activities, indent=2, ensure_ascii=False)[:2000]}

Please create a detailed, engaging travel plan that:
1. Recommends the best flight option within budget
2. Incorporates the weather forecast into daily activity planning
3. Selects the best hotel from the options
4. Creates a day-by-day itinerary using the discovered activities
5. Includes a realistic budget breakdown
6. Adds practical travel tips specific to {state['destination']}

Format the output as beautiful, readable Markdown."""

    return context


def _generate_fallback_plan(state: TravelState) -> str:
    """Minimal fallback plan if LLM call fails."""
    return f"""# ✈️ Travel Plan: {state['origin']} → {state['destination']}

## Trip Overview
- **Dates**: {state['departure_date']} → {state['return_date']}
- **Travelers**: {state['num_travelers']} person(s)
- **Budget**: {state['budget']} {state['budget_currency']}
- **Activities**: {', '.join(state.get('activities', []))}

## Note
We encountered an issue generating your detailed plan. 
Please try again or check your API keys in the .env file.

## Quick Tips
- Search for flights on Google Flights or Skyscanner
- Find hotels on Booking.com or Hotels.com
- Explore activities on TripAdvisor or Viator

We apologize for the inconvenience!"""
