"""
PrimeScore - Database helpers
FIXED: Connection pooling + context managers
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from config import DB_CONFIG
import logging

logger = logging.getLogger(__name__)

# Issue #10: Connection pooling
try:
    db_pool = ThreadedConnectionPool(minconn=1, maxconn=20, **DB_CONFIG)
    logger.info("Database connection pool initialized")
except Exception as e:
    logger.error(f"Failed to initialize connection pool: {e}")
    db_pool = None


def get_db_connection():
    """Get connection from pool."""
    if not db_pool:
        return None
    try:
        return db_pool.getconn()
    except Exception as e:
        logger.error(f"Connection pool error: {e}")
        return None


def release_db_connection(conn):
    """Return connection to pool."""
    if conn and db_pool:
        db_pool.putconn(conn)


class DBContext:
    """Context manager for database operations."""

    def __init__(self, dict_cursor: bool = False):
        self._dict_cursor = dict_cursor
        self.conn = None
        self.cursor = None

    def __enter__(self):
        self.conn = get_db_connection()
        if not self.conn:
            raise RuntimeError("Database unavailable")
        factory = RealDictCursor if self._dict_cursor else None
        self.cursor = self.conn.cursor(cursor_factory=factory) if factory else self.conn.cursor()
        return self.conn, self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type:
                if self.conn:
                    self.conn.rollback()
            else:
                if self.conn:
                    self.conn.commit()
        finally:
            if self.cursor:
                self.cursor.close()
            if self.conn:
                release_db_connection(self.conn)
        return False
