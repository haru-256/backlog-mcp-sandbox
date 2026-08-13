from typing import Any

import pytest

from backlog_mcp.space import normalize_space_domain, resolve_space
from backlog_mcp.store import Connection, MemoryStore, SpaceApp
from backlog_mcp.tools import (
    NEED_SPACE,
    NOT_CONNECTED,
    UNKNOWN_SPACE,
    connected_spaces,
    list_issues_for_user,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_normalize_bare_name() -> None:
    assert normalize_space_domain("acme") == "acme.backlog.com"


def test_normalize_url() -> None:
    assert normalize_space_domain("https://acme.backlog.jp/projects/FOO") == "acme.backlog.jp"


def test_resolve_single_space_without_argument() -> None:
    assert resolve_space(["a.backlog.com"], None) == "a.backlog.com"


def test_resolve_two_spaces_requires_argument() -> None:
    assert resolve_space(["a.backlog.com", "b.backlog.com"], None) is None
    assert resolve_space(["a.backlog.com", "b.backlog.com"], "b.backlog.com") == "b.backlog.com"


class FakeBacklog:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def exchange_code(
        self, domain: str, client_id: str, client_secret: str, code: str, redirect_uri: str
    ) -> tuple[str, str | None]:
        del client_id, client_secret, code, redirect_uri
        return f"token-for-{domain}", None

    async def list_issues(
        self, domain: str, access_token: str, *, status_id: int | None, count: int
    ) -> list[dict[str, Any]]:
        del status_id, count
        self.calls.append((domain, access_token))
        return [{"id": 1, "issueKey": "A-1", "summary": "demo", "status": {"name": "未対応"}}]


def _store_with(user: str, domains: list[str]) -> MemoryStore:
    store = MemoryStore()
    for domain in domains:
        store.put_connection(
            Connection(
                user_id=user,
                org_id="org-1",
                domain=domain,
                access_token=f"tok-{domain}",
            )
        )
    return store


@pytest.mark.anyio
async def test_list_issues_zero_connections() -> None:
    text = await list_issues_for_user(
        MemoryStore(), FakeBacklog(), "alice", space=None, status_id=None, count=20
    )
    assert text == NOT_CONNECTED


@pytest.mark.anyio
async def test_list_issues_one_connection_omits_space() -> None:
    store = _store_with("alice", ["acme.backlog.com"])
    api = FakeBacklog()
    text = await list_issues_for_user(store, api, "alice", space=None, status_id=None, count=20)
    assert "A-1" in text
    assert api.calls == [("acme.backlog.com", "tok-acme.backlog.com")]


@pytest.mark.anyio
async def test_list_issues_two_connections_require_space() -> None:
    store = _store_with("alice", ["a.backlog.com", "b.backlog.com"])
    text = await list_issues_for_user(
        store, FakeBacklog(), "alice", space=None, status_id=None, count=20
    )
    assert text == NEED_SPACE


@pytest.mark.anyio
async def test_list_issues_rejects_foreign_space() -> None:
    store = _store_with("alice", ["a.backlog.com"])
    text = await list_issues_for_user(
        store, FakeBacklog(), "alice", space="other.backlog.com", status_id=None, count=20
    )
    assert text == UNKNOWN_SPACE


@pytest.mark.anyio
async def test_list_issues_does_not_use_another_users_space() -> None:
    store = _store_with("bob", ["a.backlog.com"])
    store.put_connection(
        Connection(
            user_id="alice",
            org_id="org-1",
            domain="b.backlog.com",
            access_token="tok-b",
        )
    )
    text = await list_issues_for_user(
        store, FakeBacklog(), "alice", space="a.backlog.com", status_id=None, count=20
    )
    assert text == UNKNOWN_SPACE


def test_put_space_app_once() -> None:
    store = MemoryStore()
    store.put_space_app(SpaceApp(domain="acme.backlog.com", client_id="id", client_secret="secret"))
    store.put_space_app(
        SpaceApp(domain="acme.backlog.com", client_id="id2", client_secret="secret2")
    )
    app = store.get_space_app("acme.backlog.com")
    assert app is not None
    assert app.client_id == "id2"


def test_connected_spaces() -> None:
    store = _store_with("alice", ["a.backlog.com", "b.backlog.com"])
    listed = connected_spaces(store, "alice")
    assert [item["domain"] for item in listed] == ["a.backlog.com", "b.backlog.com"]
