"""
OpenRouter LLM factory.
Returns a ChatOpenAI instance pointed at OpenRouter's API.
All config comes from config.Config.settings — no hardcoded keys.
"""

from langchain_openai import ChatOpenAI
from config.Config import settings


def get_llm(temperature: float = 0.7) -> ChatOpenAI:
    """Return a ChatOpenAI client configured for OpenRouter."""
    return ChatOpenAI(
        model=settings.openrouter_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        temperature=temperature,
        default_headers={
            "HTTP-Referer": f"http://localhost:{settings.port}",
            "X-Title": "Travel Planning Agent",
        },
    )
