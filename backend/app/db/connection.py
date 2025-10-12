import os
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor


@contextmanager
def get_conn():
    """Yield a psycopg2 connection with RealDictCursor as default cursor.

    Usage:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(...)
    """
    dsn = os.getenv("DATABASE_URL")
    conn = psycopg2.connect(dsn)
    # Set default cursor factory for all cursor() calls
    conn.cursor_factory = RealDictCursor
    try:
        yield conn
    finally:
        conn.close()
