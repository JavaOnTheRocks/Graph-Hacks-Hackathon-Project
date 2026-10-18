
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.chat import create_chat_service
from app.agent.graph import build_graph
from app.api.routes import router
from app.config import get_settings
from app.memory.conversation_store import ConversationStore
from app.memory.long_term import LongTermMemory
from app.memory.short_term import create_checkpointer

from dotenv import load_dotenv

load_dotenv()
os.environ["MEM0_TELEMETRY"] = "false"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("personal_assistant")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Configure LangSmith tracing before creating LangChain components.
    if settings.langsmith_tracing and settings.langsmith_api_key:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    else:
        os.environ["LANGSMITH_TRACING"] = "false"

    pg_connection = None
    conversation_store = None

    try:
        # Existing LangGraph short-term memory.
        pg_connection, checkpointer = create_checkpointer(settings)

        # New persistent conversation history.
        conversation_store = ConversationStore(settings)
        app.state.conversation_store = conversation_store

        # Existing long-term memory.
        long_term_memory = LongTermMemory(settings)
        graph = build_graph(settings, checkpointer)

        app.state.chat_service = create_chat_service(
            graph,
            long_term_memory,
        )
        app.state.settings = settings
        app.state.logger = logger

        logger.info(
            "Personal Assistant started. LangSmith tracing: %s",
            settings.langsmith_tracing,
        )

        yield

    finally:
        if conversation_store is not None:
            conversation_store.close()

        if pg_connection is not None:
            pg_connection.close()

        logger.info("Personal Assistant PostgreSQL connections closed.")


app = FastAPI(
    title="Personal Assistant",
    description=(
        "A memory-aware assistant with LangGraph, PostgreSQL, "
        "Mem0, FalkorDB, and LangSmith observability."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
