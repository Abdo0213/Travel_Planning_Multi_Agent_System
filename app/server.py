"""
FastAPI application factory.
Creates the app, registers routes, mounts the static UI directory,
and handles the lifespan (checkpointer + graph initialisation).
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import mimetypes
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Fix common Windows registry issue where CSS/JS are served as text/plain
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/javascript", ".js")

import graphController
from graph import build_graph
from db.postgres_checkpointer import get_checkpointer
from routes.travel_routes import router as travel_router

logger = logging.getLogger(__name__)

# Path to the UI directory
_UI_DIR = Path(__file__).parent.parent / "ui"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialise DB checkpointer and compile graph."""
    logger.info("Starting Travel Planning Agent...")
    with get_checkpointer() as checkpointer:
        graph = build_graph(checkpointer)
        graphController.set_graph(graph)
        logger.info("LangGraph compiled and ready.")
        yield
    logger.info("Travel Planning Agent shutting down.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Travel Planning Multi-Agent System",
        description=(
            "AI-powered travel planner using LangGraph, OpenRouter, "
            "Aviationstack, OpenWeatherMap, and Tavily."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # API routes
    app.include_router(travel_router, prefix="/api")

    # Serve static UI files
    if _UI_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_UI_DIR)), name="static")

        @app.get("/", response_class=FileResponse)
        async def serve_ui():
            return FileResponse(str(_UI_DIR / "index.html"))

    return app
