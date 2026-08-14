from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace

import jwt
import pytest
from fastapi.testclient import TestClient
from openai.types.chat import ChatCompletionMessageParam

from chat.agent import mcp_bearer_token
from chat.settings import Settings
from chat.store import MemoryStore, PendingOAuth


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("OPENCODE_GO_API_KEY", "test-key")
    monkeypatch.setenv("MCP_JWT_SECRET", "dev-mcp-jwt-secret-change-me-please!!")
    monkeypatch.setenv("MCP_PUBLIC_URL", "http://localhost:3333")
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
    assert conn.access_token == "access-acme.backlog.com-abc"


@pytest.mark.anyio
async def test_chat_opens_mcp_with_jwt(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

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
    async def fake_open(
        used_settings: Settings, user_id: str, org_id: str
    ) -> AsyncIterator[FakeSession]:
        captured["token"] = mcp_bearer_token(used_settings, user_id, org_id)
        captured["user_id"] = user_id
        captured["org_id"] = org_id
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
    payload = jwt.decode(
        captured["token"],
        settings.mcp_jwt_secret,
        algorithms=["HS256"],
        issuer=settings.host_public_url,
    )
    assert payload["typ"] == "mcp"
    assert payload["sub"] == "alice"
    assert payload["org"] == "acme"
    assert captured["user_id"] == "alice"


def test_mcp_bearer_token_has_no_audience(settings: Settings) -> None:
    token = mcp_bearer_token(settings, "alice", "acme")
    payload = jwt.decode(
        token,
        settings.mcp_jwt_secret,
        algorithms=["HS256"],
        issuer=settings.host_public_url,
    )
    assert payload["typ"] == "mcp"
    assert "aud" not in payload


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
