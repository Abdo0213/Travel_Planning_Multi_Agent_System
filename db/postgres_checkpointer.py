"""
PostgreSQL Checkpointer for LangGraph.
Used to persist graph state across API calls (human-in-the-loop support).
"""

import logging
from contextlib import contextmanager
from typing import Generator

from langgraph.checkpoint.postgres import PostgresSaver
from config.Config import settings

logger = logging.getLogger(__name__)


def _get_pg_conn_string() -> str:
    """
    Convert the DATABASE_URL (which uses +psycopg dialect) to a plain
    psycopg3 connection string that PostgresSaver expects.
    """
    url = settings.database_url
    # Strip SQLAlchemy dialect prefix if present
    url = url.replace("postgresql+psycopg://", "postgresql://")
    url = url.replace("postgres+psycopg://", "postgresql://")
    return url


@contextmanager
def get_checkpointer() -> Generator[PostgresSaver, None, None]:
    """
    Sync context manager that yields a ready-to-use PostgresSaver.
    LangGraph supports using a sync checkpointer in an async graph.

    Usage:
        with get_checkpointer() as checkpointer:
            graph = build_graph(checkpointer)
    """
    conn_string = _get_pg_conn_string()
    with PostgresSaver.from_conn_string(conn_string) as checkpointer:
        try:
            checkpointer.setup()
            logger.info("PostgreSQL checkpointer ready (Sync mode).")
        except Exception as e:
            logger.warning("Checkpointer setup warning (may already exist): %s", e)
        yield checkpointer
