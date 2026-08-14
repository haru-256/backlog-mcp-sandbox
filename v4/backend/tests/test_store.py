from chat.space import normalize_space_domain
from chat.store import Connection, MemoryStore, PendingOAuth


def test_normalize_bare_name() -> None:
    assert normalize_space_domain("acme") == "acme.backlog.com"


def test_normalize_url() -> None:
    assert normalize_space_domain("https://acme.backlog.jp/projects/FOO") == "acme.backlog.jp"


def test_store_one_connection_per_user() -> None:
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
    store.put_connection(
        Connection(
            user_id="bob",
            org_id="org-1",
            domain="a.backlog.com",
            refresh_token="rtk-bob",
        )
    )
    alice = store.get_connection("alice")
    assert alice is not None
    assert alice.domain == "b.backlog.com"
    assert alice.refresh_token == "rtk-b"
    assert not hasattr(alice, "access_token")
    bob = store.get_connection("bob")
    assert bob is not None
    assert bob.refresh_token == "rtk-bob"
    assert store.get_connection("carol") is None


def test_pending_pop_is_one_shot() -> None:
    store = MemoryStore()
    store.put_pending("s", PendingOAuth(user_id="alice", org_id="acme", domain="a.backlog.com"))
    assert store.pop_pending("s") is not None
    assert store.pop_pending("s") is None
