
from datetime import datetime, timezone

from app.config import Settings
from app.db import create_postgres_connection


class ConversationStore:
    """Persist conversation metadata and messages in PostgreSQL."""

    def __init__(self, settings: Settings):
        self.connection = create_postgres_connection(settings)
        self.initialize()

    def initialize(self):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    user_id VARCHAR(128) NOT NULL,
                    thread_id VARCHAR(128) NOT NULL,
                    title TEXT NOT NULL DEFAULT 'New chat',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (user_id, thread_id)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id BIGSERIAL PRIMARY KEY,
                    user_id VARCHAR(128) NOT NULL,
                    thread_id VARCHAR(128) NOT NULL,
                    role VARCHAR(20) NOT NULL
                        CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    FOREIGN KEY (user_id, thread_id)
                        REFERENCES conversations (user_id, thread_id)
                        ON DELETE CASCADE
                )
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_conversation_messages_thread
                ON conversation_messages
                (user_id, thread_id, id)
                """
            )

    def ensure_conversation(
        self,
        user_id: str,
        thread_id: str,
        first_message: str,
    ):
        title = " ".join(first_message.split())[:60] or "New chat"

        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO conversations
                    (user_id, thread_id, title)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, thread_id) DO NOTHING
                """,
                (user_id, thread_id, title),
            )

    def add_message(
        self,
        user_id: str,
        thread_id: str,
        role: str,
        content: str,
    ):
        if role not in ("user", "assistant"):
            raise ValueError("Invalid message role.")

        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO conversation_messages
                    (user_id, thread_id, role, content)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, thread_id, role, content),
            )

            cursor.execute(
                """
                UPDATE conversations
                SET updated_at = NOW()
                WHERE user_id = %s AND thread_id = %s
                """,
                (user_id, thread_id),
            )

    def list_conversations(self, user_id: str):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    c.thread_id,
                    c.title,
                    c.created_at,
                    c.updated_at,
                    COUNT(m.id) AS message_count
                FROM conversations c
                LEFT JOIN conversation_messages m
                    ON m.user_id = c.user_id
                    AND m.thread_id = c.thread_id
                WHERE c.user_id = %s
                GROUP BY c.user_id, c.thread_id
                ORDER BY c.updated_at DESC
                """,
                (user_id,),
            )
            return cursor.fetchall()

    def get_messages(self, user_id: str, thread_id: str):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, role, content, created_at
                FROM conversation_messages
                WHERE user_id = %s AND thread_id = %s
                ORDER BY id ASC
                """,
                (user_id, thread_id),
            )
            return cursor.fetchall()

    def delete_conversation(self, user_id: str, thread_id: str):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM conversations
                WHERE user_id = %s AND thread_id = %s
                RETURNING thread_id
                """,
                (user_id, thread_id),
            )
            return cursor.fetchone() is not None

    def close(self):
        self.connection.close()
