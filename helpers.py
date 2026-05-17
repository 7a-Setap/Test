"""Test helpers used to fake database behaviour in route tests.

Why this file exists:
- The coursework app uses a PostgreSQL-backed DBContext context manager.
- We want route tests that are fast, deterministic, and easy to understand.
- Using a fake DB context lets us test route logic without requiring a real
  database server for every scenario.

The helpers below are deliberately simple and heavily commented so they can
also serve as explanation in coursework discussions.
"""

from collections import deque
from dataclasses import dataclass, field


def _compact_sql(query_text):
    """Collapse whitespace so SQL assertions are easier to read.

    Real route files format SQL across multiple lines. Tests usually only care
    that the correct statement type was executed, not about the exact spacing.
    """

    return " ".join(str(query_text).split())


class RecordingCursor:
    """Small fake cursor that records SQL and replays scripted fetch results.

    The route code normally calls:
    - cursor.execute(...)
    - cursor.fetchone()
    - cursor.fetchall()

    This fake object supports those same methods so the route can run unchanged.
    The test controls the returned values by providing scripted fetch results in
    advance.
    """

    def __init__(self, fetchone_results=None, fetchall_results=None):
        self.fetchone_results = deque(fetchone_results or [])
        self.fetchall_results = deque(fetchall_results or [])
        self.executed_statements = []
        self.closed = False

    def execute(self, query_text, params=None):
        """Record every executed SQL statement for later assertions."""

        self.executed_statements.append(
            {
                "query": _compact_sql(query_text),
                "params": params,
            }
        )

    def fetchone(self):
        """Return the next scripted fetchone result, or None if exhausted."""

        return self.fetchone_results.popleft() if self.fetchone_results else None

    def fetchall(self):
        """Return the next scripted fetchall result, or an empty list."""

        return self.fetchall_results.popleft() if self.fetchall_results else []

    def close(self):
        """Mirror the real cursor API so context-manager cleanup works."""

        self.closed = True


@dataclass
class RecordingTransactionState:
    """Track whether the fake context manager would have committed or rolled back."""

    committed: bool = False
    rolled_back: bool = False
    entered: bool = False
    exited: bool = False


class RecordingDBContext:
    """Context manager that behaves like the project's DBContext.

    The production DBContext returns `(connection, cursor)` from `__enter__`.
    Route code then unpacks it inside a `with DBContext() as (_, cursor):` block.

    This fake version does the same, but instead of opening a real database
    connection it reuses the scripted cursor provided by the test.
    """

    def __init__(self, cursor, transaction_state):
        self.cursor = cursor
        self.transaction_state = transaction_state

    def __enter__(self):
        self.transaction_state.entered = True
        # Returning `self` as the connection placeholder is enough because the
        # tests only care about cursor interactions, not a real connection API.
        return self, self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.transaction_state.exited = True
        if exc_type:
            self.transaction_state.rolled_back = True
        else:
            self.transaction_state.committed = True
        self.cursor.close()
        return False


@dataclass
class DBContextPatch:
    """Bundle returned by `build_dbcontext_patch` for easy monkeypatching.

    Attributes:
    - factory: patch target to assign over the real DBContext symbol
    - cursor: lets the test inspect executed SQL
    - transaction_state: lets the test assert commit/rollback behaviour
    """

    factory: object
    cursor: RecordingCursor
    transaction_state: RecordingTransactionState = field(default_factory=RecordingTransactionState)


def build_dbcontext_patch(fetchone_results=None, fetchall_results=None):
    """Create a ready-to-monkeypatch fake DBContext factory.

    Example usage in a test:

        db_patch = build_dbcontext_patch(fetchone_results=[None, {"id": 1}])
        monkeypatch.setattr(target_module, "DBContext", db_patch.factory)

    The route code will then run against the scripted results while the test can
    inspect `db_patch.cursor.executed_statements`.
    """

    cursor = RecordingCursor(
        fetchone_results=fetchone_results,
        fetchall_results=fetchall_results,
    )
    transaction_state = RecordingTransactionState()

    def factory(*args, **kwargs):
        # The real DBContext accepts options such as dict_cursor=True.
        # We intentionally ignore them here because the scripted return values
        # already control whether rows look like tuples or dictionaries.
        return RecordingDBContext(cursor, transaction_state)

    return DBContextPatch(
        factory=factory,
        cursor=cursor,
        transaction_state=transaction_state,
    )
