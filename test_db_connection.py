import pytest
from psycopg2.extras import RealDictCursor

import db.connection as db_connection


class FakeCursor:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.cursor_calls = []
        self.committed = False
        self.rolled_back = False
        self.cursor_instance = FakeCursor()

    def cursor(self, cursor_factory=None):
        self.cursor_calls.append(cursor_factory)
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class FakePool:
    def __init__(self, conn=None, raises=False):
        self.conn = conn
        self.raises = raises
        self.released = []

    def getconn(self):
        if self.raises:
            raise RuntimeError("pool unavailable")
        return self.conn

    def putconn(self, conn):
        self.released.append(conn)


def test_get_db_connection_returns_none_when_pool_is_missing(monkeypatch):
    monkeypatch.setattr(db_connection, "db_pool", None)

    assert db_connection.get_db_connection() is None


def test_get_db_connection_returns_none_when_pool_raises(monkeypatch):
    monkeypatch.setattr(db_connection, "db_pool", FakePool(raises=True))

    assert db_connection.get_db_connection() is None


def test_release_db_connection_returns_connection_to_pool(monkeypatch):
    fake_connection = FakeConnection()
    fake_pool = FakePool(conn=fake_connection)
    monkeypatch.setattr(db_connection, "db_pool", fake_pool)

    db_connection.release_db_connection(fake_connection)

    assert fake_pool.released == [fake_connection]


def test_dbcontext_commits_and_releases_on_success(monkeypatch):
    fake_connection = FakeConnection()
    released = []

    monkeypatch.setattr(db_connection, "get_db_connection", lambda: fake_connection)
    monkeypatch.setattr(db_connection, "release_db_connection", lambda conn: released.append(conn))

    with db_connection.DBContext() as (conn, cursor):
        assert conn is fake_connection
        assert cursor is fake_connection.cursor_instance

    assert fake_connection.committed is True
    assert fake_connection.rolled_back is False
    assert fake_connection.cursor_instance.closed is True
    assert released == [fake_connection]


def test_dbcontext_rolls_back_and_releases_on_error(monkeypatch):
    fake_connection = FakeConnection()
    released = []

    monkeypatch.setattr(db_connection, "get_db_connection", lambda: fake_connection)
    monkeypatch.setattr(db_connection, "release_db_connection", lambda conn: released.append(conn))

    with pytest.raises(ValueError):
        with db_connection.DBContext():
            raise ValueError("boom")

    assert fake_connection.committed is False
    assert fake_connection.rolled_back is True
    assert fake_connection.cursor_instance.closed is True
    assert released == [fake_connection]


def test_dbcontext_uses_real_dict_cursor_when_requested(monkeypatch):
    fake_connection = FakeConnection()

    monkeypatch.setattr(db_connection, "get_db_connection", lambda: fake_connection)
    monkeypatch.setattr(db_connection, "release_db_connection", lambda conn: None)

    with db_connection.DBContext(dict_cursor=True):
        pass

    assert fake_connection.cursor_calls == [RealDictCursor]


def test_dbcontext_raises_when_database_is_unavailable(monkeypatch):
    monkeypatch.setattr(db_connection, "get_db_connection", lambda: None)

    with pytest.raises(RuntimeError, match="Database unavailable"):
        with db_connection.DBContext():
            pass
