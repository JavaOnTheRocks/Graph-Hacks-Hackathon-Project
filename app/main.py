
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.agent.chat import create_chat_service
from app.agent.graph import build_graph
from app.api.routes import router
from app.config import get_settings
from app.memory.long_term import LongTermMemory
from app.memory.short_term import create_checkpointer


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("continuityos")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Configure tracing before creating/invoking LangChain components.
    if settings.langsmith_tracing and settings.langsmith_api_key:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    else:
        os.environ["LANGSMITH_TRACING"] = "false"

    pg_connection, checkpointer = create_checkpointer(settings)

    try:
        long_term_memory = LongTermMemory(settings)
        graph = build_graph(settings, checkpointer)

        app.state.chat_service = create_chat_service(
            graph,
            long_term_memory,
        )
        app.state.settings = settings
        app.state.logger = logger

        logger.info(
            "ContinuityOS started. LangSmith tracing: %s",
            settings.langsmith_tracing,
        )

        yield

    finally:
        pg_connection.close()
        logger.info("ContinuityOS PostgreSQL connection closed.")


app = FastAPI(
    title="ContinuityOS API",
    description=(
        "A memory-aware agent with LangGraph, PostgreSQL, "
        "Mem0, FalkorDB, and LangSmith observability."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router, prefix="/api/v1")
