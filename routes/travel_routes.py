"""
Travel Planning API Routes.

POST /api/plan/start          — Start a new planning session (returns SSE stream)
GET  /api/plan/stream/{id}    — SSE stream of agent progress + final plan
POST /api/plan/feedback/{id}  — Submit revision feedback (returns SSE stream)
POST /api/plan/approve/{id}   — Approve the plan
GET  /api/plan/status/{id}    — Get current session state
"""

import json
import uuid
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

import graphController
from state_builder import build_initial_state

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory session store: thread_id → initial_state
# (initial state only needed until graph picks it up)
_sessions: dict = {}


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class TravelPlanRequest(BaseModel):
    origin: str = Field(..., description="Departure city (e.g. 'Cairo, Egypt')")
    destination: str = Field(..., description="Destination city (e.g. 'Paris, France')")
    departure_date: str = Field(..., description="YYYY-MM-DD")
    return_date: str = Field(..., description="YYYY-MM-DD")
    num_travelers: int = Field(default=1, ge=1, le=20)
    activities: List[str] = Field(default_factory=list)
    budget: float = Field(..., gt=0, description="Total budget")
    budget_currency: str = Field(default="USD")


class FeedbackRequest(BaseModel):
    feedback: str = Field(..., min_length=5, description="Revision feedback from user")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/plan/start")
async def start_plan(request: TravelPlanRequest):
    """
    Register a new travel planning session.
    Returns a thread_id to use with the /plan/stream endpoint.
    """
    thread_id = str(uuid.uuid4())
    initial_state = build_initial_state(
        {**request.model_dump(), "thread_id": thread_id}
    )
    _sessions[thread_id] = initial_state
    logger.info("Session created: %s — %s → %s", thread_id, request.origin, request.destination)
    return {"thread_id": thread_id, "status": "created"}


@router.get("/plan/stream/{thread_id}")
async def stream_plan(thread_id: str, http_request: Request):
    """
    SSE endpoint — streams agent progress events and delivers the final plan draft.
    Connect immediately after calling /plan/start.
    """
    if thread_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found. Call /api/plan/start first.")

    initial_state = _sessions.pop(thread_id)  # consume it; graph checkpointer takes over

    async def generate():
        try:
            async for event in graphController.stream_plan_events(thread_id, initial_state):
                if await http_request.is_disconnected():
                    break
                yield {"data": json.dumps(event), "event": event.get("event", "update")}
        except Exception as e:
            logger.error("Stream error for %s: %s", thread_id, e)
            yield {
                "data": json.dumps({"event": "error", "message": str(e)}),
                "event": "error",
            }

    return EventSourceResponse(generate())


@router.post("/plan/feedback/{thread_id}")
async def submit_feedback(thread_id: str, request: FeedbackRequest, http_request: Request):
    """
    SSE endpoint — resume graph with user feedback, streams revision progress.
    """
    async def generate():
        try:
            async for event in graphController.stream_revision_events(
                thread_id, request.feedback
            ):
                if await http_request.is_disconnected():
                    break
                yield {"data": json.dumps(event), "event": event.get("event", "update")}
        except Exception as e:
            logger.error("Revision stream error for %s: %s", thread_id, e)
            yield {
                "data": json.dumps({"event": "error", "message": str(e)}),
                "event": "error",
            }

    return EventSourceResponse(generate())


@router.post("/plan/approve/{thread_id}")
async def approve_plan(thread_id: str):
    """
    Approve the current plan draft — finalises the graph run.
    """
    try:
        result = await graphController.approve_plan(thread_id)
        logger.info("Plan approved for thread %s", thread_id)
        return {
            "status": "approved",
            "final_plan": result.get("plan_draft"),
            "revision_count": result.get("revision_count", 0),
        }
    except Exception as e:
        logger.error("Approve error for %s: %s", thread_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plan/status/{thread_id}")
async def get_status(thread_id: str):
    """
    Get the current state of a planning session.
    """
    try:
        state = await graphController.get_plan_state(thread_id)
        if state is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return state
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "Travel Planning Agent"}
