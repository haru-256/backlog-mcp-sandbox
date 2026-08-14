from chat.store import Connection, MemoryStore


def test_put_connection_overwrites_same_user() -> None:
    store = MemoryStore()
    store.put_connection(
        Connection(
            user_id="alice",
            org_id="org-1",
            domain="a.backlog.com",
            refresh_token="rtk-a",
        )
    )
    store.put_connection(
        Connection(
            user_id="alice",
            org_id="org-1",
            domain="b.backlog.com",
            refresh_token="rtk-b",
        )
    )
    alice = store.get_connection("alice")
    assert alice is not None
    assert alice.domain == "b.backlog.com"
