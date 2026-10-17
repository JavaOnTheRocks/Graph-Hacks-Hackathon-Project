
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str
    openai_api_key: str
    openai_model: str

    tavily_api_key: str | None
    openweather_api_key: str | None
    weather_units: str

    falkordb_host: str
    falkordb_port: int
    falkordb_password: str | None

    # Final project's long-term memory graph.
    mem0_graph_name: str
    continuity_graph_name: str

    langsmith_tracing: bool
    langsmith_api_key: str | None
    langsmith_project: str
    langsmith_endpoint: str


def get_settings() -> Settings:
    database_url = os.getenv("DATABASE_URL", "").strip()
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()

    if not database_url:
        raise RuntimeError("DATABASE_URL is missing from .env")

    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is missing from .env")

    graph_name = os.getenv(
        "CONTINUITY_GRAPH_NAME",
        "GraphHacks_memory",
    )

    return Settings(
        database_url=database_url,
        openai_api_key=openai_api_key,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),

        tavily_api_key=os.getenv("TAVILY_API_KEY"),
        openweather_api_key=os.getenv("OPENWEATHER_API_KEY"),
        weather_units=os.getenv("WEATHER_UNITS", "metric"),

        falkordb_host=os.getenv("FALKORDB_HOST", "localhost"),
        falkordb_port=int(os.getenv("FALKORDB_PORT", "6379")),
        falkordb_password=os.getenv("FALKORDB_PASSWORD") or None,

        mem0_graph_name=os.getenv(
            "MEM0_GRAPH_NAME",
            graph_name,
        ),
        continuity_graph_name=graph_name,

        langsmith_tracing=os.getenv(
            "LANGSMITH_TRACING", "false"
        ).lower() in {"1", "true", "yes"},

        langsmith_api_key=os.getenv("LANGSMITH_API_KEY"),
        langsmith_project=os.getenv(
            "LANGSMITH_PROJECT", "ContinuityOS"
        ),
        langsmith_endpoint=os.getenv(
            "LANGSMITH_ENDPOINT",
            "https://api.smith.langchain.com",
        ),
    )
