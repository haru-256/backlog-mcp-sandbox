from chat.connections import (
    NEED_SPACE,
    NOT_CONNECTED,
    UNKNOWN_SPACE,
    connected_spaces,
    resolve_connection,
)
from chat.store import Connection, MemoryStore


def _store_with(user: str, domains: list[str]) -> MemoryStore:
    store = MemoryStore()
    for domain in domains:
        store.put_connection(
            Connection(
                user_id=user,
                org_id="org-1",
                domain=domain,
                refresh_token=f"rtk-{domain}",
            )
        )
    return store


def test_connected_spaces_only_that_user() -> None:
    store = _store_with("alice", ["a.backlog.com", "b.backlog.com"])
    store.put_connection(
        Connection(
            user_id="bob",
            org_id="org-1",
            domain="c.backlog.com",
            refresh_token="rtk-c",
        )
    )
    listed = connected_spaces(store, "alice")
    assert [item["domain"] for item in listed] == ["a.backlog.com", "b.backlog.com"]


def test_resolve_zero_connections() -> None:
    assert resolve_connection(MemoryStore(), "alice", None) == NOT_CONNECTED


def test_resolve_one_connection_omits_space() -> None:
    store = _store_with("alice", ["acme.backlog.com"])
    conn = resolve_connection(store, "alice", None)
    assert isinstance(conn, Connection)
    assert conn.domain == "acme.backlog.com"
    assert conn.refresh_token == "rtk-acme.backlog.com"


def test_resolve_two_connections_require_space() -> None:
    store = _store_with("alice", ["a.backlog.com", "b.backlog.com"])
    assert resolve_connection(store, "alice", None) == NEED_SPACE
    conn = resolve_connection(store, "alice", "b.backlog.com")
    assert isinstance(conn, Connection)
    assert conn.domain == "b.backlog.com"


def test_resolve_rejects_foreign_and_other_users_space() -> None:
    store = _store_with("alice", ["a.backlog.com"])
    store.put_connection(
        Connection(
            user_id="bob",
            org_id="org-1",
            domain="b.backlog.com",
            refresh_token="rtk-b",
        )
    )
    assert resolve_connection(store, "alice", "other.backlog.com") == UNKNOWN_SPACE
    assert resolve_connection(store, "alice", "b.backlog.com") == UNKNOWN_SPACE
