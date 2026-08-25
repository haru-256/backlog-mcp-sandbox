import httpx
import pytest

from chat.session_tokens import issue_session_tokens
from chat.store import Connection, MemoryStore


def _conn(user: str, domain: str, refresh: str) -> Connection:
    return Connection(user_id=user, org_id="org-1", domain=domain, refresh_token=refresh)


@pytest.mark.anyio
async def test_issue_session_tokens_refreshes_each_space(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryStore()
    store.put_connection(_conn("alice", "a.backlog.com", "rtk-a"))
    store.put_connection(_conn("alice", "b.backlog.com", "rtk-b"))
    store.put_connection(_conn("bob", "a.backlog.com", "rtk-bob"))
    calls: list[str] = []

    async def fake_refresh(
        http: object,
        domain: str,
        client_id: str,
        client_secret: str,
        refresh_token: str,
    ) -> tuple[str, str]:
        del http, client_id, client_secret
        calls.append(f"{domain}:{refresh_token}")
        return f"atk-{domain}", f"rtk2-{domain}"

    monkeypatch.setattr("chat.session_tokens.refresh_access_token", fake_refresh)
    async with httpx.AsyncClient() as http:
        tokens = await issue_session_tokens(http, store, "alice", "cid", "csecret")
    assert tokens == {
        "a.backlog.com": "atk-a.backlog.com",
        "b.backlog.com": "atk-b.backlog.com",
    }
    assert sorted(calls) == ["a.backlog.com:rtk-a", "b.backlog.com:rtk-b"]
    assert store.get_connection("alice", "a.backlog.com").refresh_token == "rtk2-a.backlog.com"
    assert store.get_connection("bob", "a.backlog.com").refresh_token == "rtk-bob"


@pytest.mark.anyio
async def test_issue_session_tokens_omits_failed_space(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryStore()
    store.put_connection(_conn("alice", "a.backlog.com", "rtk-a"))
    store.put_connection(_conn("alice", "b.backlog.com", "rtk-b"))

    async def fake_refresh(
        http: object,
        domain: str,
        client_id: str,
        client_secret: str,
        refresh_token: str,
    ) -> tuple[str, str]:
        del http, client_id, client_secret, refresh_token
        if domain.startswith("b."):
            raise httpx.HTTPStatusError(
                "no", request=httpx.Request("POST", "https://x"), response=httpx.Response(401)
            )
        return "atk-a", "rtk-a"

    monkeypatch.setattr("chat.session_tokens.refresh_access_token", fake_refresh)
    async with httpx.AsyncClient() as http:
        tokens = await issue_session_tokens(http, store, "alice", "cid", "csecret")
    assert tokens == {"a.backlog.com": "atk-a"}
    assert store.get_connection("alice", "b.backlog.com") is not None
    assert store.get_connection("alice", "b.backlog.com").refresh_token == "rtk-b"


@pytest.mark.anyio
async def test_issue_session_tokens_empty() -> None:
    async with httpx.AsyncClient() as http:
        tokens = await issue_session_tokens(http, MemoryStore(), "alice", "cid", "csecret")
    assert tokens == {}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
