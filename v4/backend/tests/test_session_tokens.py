import httpx
import pytest

from chat.session_tokens import SessionAuth, issue_session_auth
from chat.store import Connection, MemoryStore


def _conn(user: str, domain: str, refresh: str) -> Connection:
    return Connection(user_id=user, org_id="org-1", domain=domain, refresh_token=refresh)


@pytest.mark.anyio
async def test_issue_session_auth_refreshes_the_one_space(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryStore()
    store.put_connection(_conn("alice", "a.backlog.com", "rtk-a"))
    store.put_connection(_conn("bob", "b.backlog.com", "rtk-bob"))

    async def fake_refresh(
        http: object,
        domain: str,
        client_id: str,
        client_secret: str,
        refresh_token: str,
    ) -> tuple[str, str]:
        del http, client_id, client_secret
        return f"atk-{domain}", f"rtk2-{refresh_token}"

    monkeypatch.setattr("chat.session_tokens.refresh_access_token", fake_refresh)
    async with httpx.AsyncClient() as http:
        auth = await issue_session_auth(http, store, "alice", "cid", "csecret")
    assert auth == SessionAuth(domain="a.backlog.com", access_token="atk-a.backlog.com")
    alice = store.get_connection("alice")
    assert alice is not None
    assert alice.refresh_token == "rtk2-rtk-a"
    bob = store.get_connection("bob")
    assert bob is not None
    assert bob.refresh_token == "rtk-bob"


@pytest.mark.anyio
async def test_issue_session_auth_none_when_refresh_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryStore()
    store.put_connection(_conn("alice", "a.backlog.com", "rtk-a"))

    async def fake_refresh(
        http: object,
        domain: str,
        client_id: str,
        client_secret: str,
        refresh_token: str,
    ) -> tuple[str, str]:
        del http, domain, client_id, client_secret, refresh_token
        raise httpx.HTTPStatusError(
            "no", request=httpx.Request("POST", "https://x"), response=httpx.Response(401)
        )

    monkeypatch.setattr("chat.session_tokens.refresh_access_token", fake_refresh)
    async with httpx.AsyncClient() as http:
        auth = await issue_session_auth(http, store, "alice", "cid", "csecret")
    assert auth is None
    assert store.get_connection("alice") is not None


@pytest.mark.anyio
async def test_issue_session_auth_none_when_unconnected() -> None:
    async with httpx.AsyncClient() as http:
        auth = await issue_session_auth(http, MemoryStore(), "alice", "cid", "csecret")
    assert auth is None


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
