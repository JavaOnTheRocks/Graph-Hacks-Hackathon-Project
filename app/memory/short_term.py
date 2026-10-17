
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row

from app.config import Settings


def create_checkpointer(settings: Settings):
    """Create the PostgreSQL connection and LangGraph checkpointer."""
    connection = __import__("psycopg").connect(
        settings.database_url,
        autocommit=True,
        row_factory=dict_row,
    )

    checkpointer = PostgresSaver(connection)
    checkpointer.setup()

    return connection, checkpointer


def format_conversation_history(messages, max_turns: int = 8) -> str:
    """Format recent Human/AI messages into readable conversation history."""
    if not messages:
        return "No previous conversation."

    relevant_messages = []

    for message in messages:
        role = getattr(message, "type", "")

        if role not in ("human", "ai"):
            continue

        content = getattr(message, "content", "")

        if isinstance(content, str) and content.strip():
            label = "User" if role == "human" else "Assistant"
            relevant_messages.append(f"{label}: {content.strip()}")

    # Each conversation turn usually contains a user and assistant message.
    relevant_messages = relevant_messages[-(max_turns * 2):]

    if not relevant_messages:
        return "No previous conversation."

    return "\n".join(relevant_messages)
