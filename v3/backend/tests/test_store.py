from chat.space import normalize_space_domain, resolve_space
from chat.store import Connection, MemoryStore, PendingOAuth


def test_normalize_bare_name() -> None:
    assert normalize_space_domain("acme") == "acme.backlog.com"


def test_normalize_url() -> None:
    assert normalize_space_domain("https://acme.backlog.jp/projects/FOO") == "acme.backlog.jp"


def test_resolve_single_space_without_argument() -> None:
    assert resolve_space(["a.backlog.com"], None) == "a.backlog.com"


def test_resolve_two_spaces_requires_argument() -> None:
    assert resolve_space(["a.backlog.com", "b.backlog.com"], None) is None
    assert resolve_space(["a.backlog.com", "b.backlog.com"], "b.backlog.com") == "b.backlog.com"


def test_store_keys_by_user_and_domain() -> None:
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
            user_id="bob",
            org_id="org-1",
            domain="a.backlog.com",
            refresh_token="rtk-bob",
        )
    )
    alice = store.get_connection("alice", "a.backlog.com")
    assert alice is not None
    assert alice.refresh_token == "rtk-a"
    assert not hasattr(alice, "access_token")
    assert [c.domain for c in store.list_connections("alice")] == ["a.backlog.com"]
    assert store.get_connection("alice", "missing.backlog.com") is None


def test_pending_pop_is_one_shot() -> None:
    store = MemoryStore()
    store.put_pending("s", PendingOAuth(user_id="alice", org_id="acme", domain="a.backlog.com"))
    assert store.pop_pending("s") is not None
    assert store.pop_pending("s") is None
