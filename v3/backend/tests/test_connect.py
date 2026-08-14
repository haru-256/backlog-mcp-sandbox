from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from openai.types.chat import ChatCompletionMessageParam

from chat.settings import Settings
from chat.store import Connection, MemoryStore, PendingOAuth


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("OPENCODE_GO_API_KEY", "test-key")
    monkeypatch.setenv("HOST_PUBLIC_URL", "http://localhost:8003")
    monkeypatch.setenv("MCP_SERVER_URL", "http://localhost:3333/mcp")
    return Settings.from_env()


def test_connect_get_renders_form(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("chat.api.settings", settings)
    monkeypatch.setattr("chat.api.store", MemoryStore())
    from chat.api import app

    client = TestClient(app, follow_redirects=False)
    response = client.get("/backlog/connect", params={"user_id": "alice", "org_id": "acme"})
    assert response.status_code == 200
    assert "スペース" in response.text
    assert "alice" in response.text
    assert "Client ID" not in response.text


def test_connect_post_redirects_to_backlog(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = MemoryStore()
    monkeypatch.setattr("chat.api.settings", settings)
    monkeypatch.setattr("chat.api.store", store)
    from chat.api import app

    client = TestClient(app, follow_redirects=False)
    response = client.post(
        "/backlog/connect",
        data={"user_id": "alice", "org_id": "acme", "space": "other.backlog.com"},
    )
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://other.backlog.com/OAuth2AccessRequest.action")
    assert "client_id=" in location
    assert len(store.pending) == 1


@pytest.mark.anyio
async def test_callback_stores_connection(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = MemoryStore()
    store.put_pending(
        "oauth-state",
        PendingOAuth(user_id="alice", org_id="acme", domain="acme.backlog.com"),
    )

    async def fake_exchange(
        http: object,
        domain: str,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
    ) -> tuple[str, str | None]:
        del http, client_id, client_secret, redirect_uri
        return f"access-{domain}-{code}", "refresh"

    monkeypatch.setattr("chat.api.settings", settings)
    monkeypatch.setattr("chat.api.store", store)
    monkeypatch.setattr("chat.connect.exchange_code", fake_exchange)
    from chat.api import app

    client = TestClient(app, follow_redirects=False)
    response = client.get(
        "/backlog/callback",
        params={"code": "abc", "state": "oauth-state"},
    )
    assert response.status_code == 302
    assert "connected=1" in response.headers["location"]
    assert "space=" in response.headers["location"]
    conn = store.get_connection("alice", "acme.backlog.com")
    assert conn is not None
    assert conn.refresh_token == "refresh"
    assert not hasattr(conn, "access_token")


@pytest.mark.anyio
async def test_callback_rejects_missing_refresh(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = MemoryStore()
    store.put_pending(
        "oauth-state",
        PendingOAuth(user_id="alice", org_id="acme", domain="acme.backlog.com"),
    )

    async def fake_exchange(
        http: object,
        domain: str,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
    ) -> tuple[str, str | None]:
        del http, domain, client_id, client_secret, code, redirect_uri
        return "atk-only", None

    monkeypatch.setattr("chat.api.settings", settings)
    monkeypatch.setattr("chat.api.store", store)
    monkeypatch.setattr("chat.connect.exchange_code", fake_exchange)
    from chat.api import app

    client = TestClient(app, follow_redirects=False)
    response = client.get(
        "/backlog/callback",
        params={"code": "abc", "state": "oauth-state"},
    )
    assert response.status_code == 400
    assert "refresh" in response.text
    assert store.get_connection("alice", "acme.backlog.com") is None


@pytest.mark.anyio
async def test_chat_opens_mcp(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    opened = False

    class FakeSession:
        async def initialize(self) -> None:
            return None

        async def list_tools(self) -> object:
            return SimpleNamespace(tools=[])

        async def call_tool(self, name: str, arguments: dict[str, object]) -> object:
            del name, arguments
            raise AssertionError("should not call tools")

    class FakeLLM:
        async def complete(
            self,
            messages: list[ChatCompletionMessageParam],
            tools: object,
        ) -> ChatCompletionMessageParam:
            del messages, tools
            return {"role": "assistant", "content": "ok"}

    @asynccontextmanager
    async def fake_open(_used_settings: Settings) -> AsyncIterator[FakeSession]:
        nonlocal opened
        opened = True
        yield FakeSession()

    monkeypatch.setattr("chat.agent.open_mcp_session", fake_open)
    monkeypatch.setattr("chat.agent.OpencodeGoLLM", lambda _settings: FakeLLM())

    from chat.agent import run_agent

    result = await run_agent(
        [{"role": "user", "content": "hello"}],
        settings,
        "alice",
        "acme",
        MemoryStore(),
    )
    assert result[-1].get("content") == "ok"
    assert opened


@pytest.mark.anyio
async def test_chat_issues_session_tokens_before_mcp(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = MemoryStore()
    store.put_connection(
        Connection(
            user_id="alice",
            org_id="acme",
            domain="acme.backlog.com",
            refresh_token="rtk-1",
        )
    )
    captured: dict[str, object] = {}

    async def fake_issue(
        http: object,
        used_store: MemoryStore,
        user_id: str,
        client_id: str,
        client_secret: str,
    ) -> dict[str, str]:
        del http, used_store, client_id, client_secret
        captured["user_id"] = user_id
        return {"acme.backlog.com": "atk-live"}

    class FakeSession:
        async def initialize(self) -> None:
            return None

        async def list_tools(self) -> object:
            return SimpleNamespace(tools=[])

        async def call_tool(self, name: str, arguments: dict[str, object]) -> object:
            del name, arguments
            raise AssertionError("should not call tools")

    class FakeLLM:
        async def complete(
            self,
            messages: list[ChatCompletionMessageParam],
            tools: object,
        ) -> ChatCompletionMessageParam:
            del messages, tools
            return {"role": "assistant", "content": "ok"}

    @asynccontextmanager
    async def fake_open(_used_settings: Settings) -> AsyncIterator[FakeSession]:
        captured["opened"] = True
        yield FakeSession()

    monkeypatch.setattr("chat.agent.issue_session_tokens", fake_issue)
    monkeypatch.setattr("chat.agent.open_mcp_session", fake_open)
    monkeypatch.setattr("chat.agent.OpencodeGoLLM", lambda _settings: FakeLLM())

    from chat.agent import run_agent

    result = await run_agent(
        [{"role": "user", "content": "hello"}],
        settings,
        "alice",
        "acme",
        store,
    )
    assert result[-1].get("content") == "ok"
    assert captured["user_id"] == "alice"
    assert captured.get("opened") is True


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
