"""
Application entry point.

Startup sequence:
  1. Start FastAPI/uvicorn server (port 8000)
  
Note on MCP servers:
  • flight_mcp_server.py and weather_mcp_server.py are spawned on-demand
    by MCPManager as stdio subprocesses (auto-managed, no manual startup needed).
  • Tavily uses the official MCP server via npx (spawned on-demand by MCPManager).
    Requires Node.js installed: https://nodejs.org

Usage:
  .\\venv\\Scripts\\Activate.ps1
  python main.py
"""

import sys
import logging
from pathlib import Path

import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")

# Ensure project root is on path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from config.Config import settings


def main():
    logger.info("Starting Travel Planning Agent...")
    logger.info(
        "MCPManager will spawn MCP servers on-demand:\n"
        "  • flight  → %s/MCP_Servers/flight_mcp_server.py (stdio)\n"
        "  • weather → %s/MCP_Servers/weather_mcp_server.py (stdio)\n"
        "  • tavily  → npx -y tavily-mcp (stdio, requires Node.js)",
        ROOT, ROOT,
    )

    from app.server import create_app
    app = create_app()

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
