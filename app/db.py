
import psycopg
from psycopg.rows import dict_row

from app.config import Settings


def create_postgres_connection(settings: Settings):
    """Create a PostgreSQL connection for the application."""
    connection = psycopg.connect(
        settings.database_url,
        autocommit=True,
        row_factory=dict_row,
    )
    return connection
