"""
Central configuration — all values loaded from .env via pydantic-settings.
Import `settings` anywhere in the project; never hardcode keys.
"""

import os
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))


class Settings(BaseSettings):
    # ------------------------------------------------------------------
    # LLM — OpenRouter
    # ------------------------------------------------------------------
    openrouter_api_key: str = Field(..., env="OPENROUTER_API_KEY")
    openrouter_model: str = Field(
        default="meta-llama/llama-3.1-8b-instruct:free", env="OPENROUTER_MODEL"
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", env="OPENROUTER_BASE_URL"
    )

    # ------------------------------------------------------------------
    # External APIs
    # ------------------------------------------------------------------
    aviationstack_api_key: str = Field(..., env="AVIATIONSTACK_API_KEY")
    openweather_api_key: str = Field(..., env="OPENWEATHER_API_KEY")
    tavily_api_key: str = Field(..., env="TAVILY_API_KEY")
    tavily_mcp_port: int = Field(default=8001, env="TAVILY_MCP_PORT")

    # ------------------------------------------------------------------
    # PostgreSQL (LangGraph Checkpointing)
    # ------------------------------------------------------------------
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/travel_planner",
        env="DATABASE_URL",
    )

    # ------------------------------------------------------------------
    # LangSmith
    # ------------------------------------------------------------------
    langsmith_api_key: str = Field(default="", env="LANGSMITH_API_KEY")
    langsmith_project: str = Field(
        default="travel-planning-agent", env="LANGSMITH_PROJECT"
    )
    langchain_tracing_v2: bool = Field(default=True, env="LANGCHAIN_TRACING_V2")
    langchain_endpoint: str = Field(
        default="https://api.smith.langchain.com", env="LANGCHAIN_ENDPOINT"
    )

    # ------------------------------------------------------------------
    # FastAPI Server
    # ------------------------------------------------------------------
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


settings = Settings()

# Push LangSmith env vars so the SDK can pick them up
os.environ["LANGCHAIN_TRACING_V2"] = str(settings.langchain_tracing_v2).lower()
os.environ["LANGCHAIN_ENDPOINT"] = settings.langchain_endpoint
os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
