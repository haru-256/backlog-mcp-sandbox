from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace

import jwt
import pytest
from fastapi.testclient import TestClient
from openai.types.chat import ChatCompletionMessageParam

from chat.agent import mcp_bearer_token
from chat.jwt_tokens import sign_token
from chat.settings import Settings


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("OPENCODE_GO_API_KEY", "test-key")
    monkeypatch.setenv("MCP_JWT_SECRET", "dev-mcp-jwt-secret-change-me-please!!")
    monkeypatch.setenv("MCP_PUBLIC_URL", "http://localhost:3333")
    monkeypatch.setenv("HOST_PUBLIC_URL", "http://localhost:8003")
    monkeypatch.setenv("MCP_SERVER_URL", "http://localhost:3333/mcp")
    return Settings.from_env()


def test_connect_redirect_signs_state(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("chat.api.settings", settings)
    from chat.api import app

    client = TestClient(app, follow_redirects=False)
    response = client.get("/backlog/connect", params={"user_id": "alice", "org_id": "acme"})
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("http://localhost:3333/connect?state=")
    state = location.split("state=", 1)[1]
    payload = jwt.decode(
        state,
        settings.mcp_jwt_secret,
        algorithms=["HS256"],
        issuer=settings.host_public_url,
    )
    assert payload["typ"] == "connect"
    assert payload["sub"] == "alice"
    assert payload["org"] == "acme"


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
    )
    assert result[-1].get("content") == "ok"
    payload = jwt.decode(
        captured["token"],
        settings.mcp_jwt_secret,
        algorithms=["HS256"],
        audience=settings.mcp_public_url,
        issuer=settings.host_public_url,
    )
    assert payload["typ"] == "mcp"
    assert payload["sub"] == "alice"
    assert payload["org"] == "acme"
    assert captured["user_id"] == "alice"


def test_sign_connect_token_roundtrip(settings: Settings) -> None:
    token = sign_token(
        secret=settings.mcp_jwt_secret,
        typ="connect",
        user_id="bob",
        org_id="org",
        issuer=settings.host_public_url,
        ttl_seconds=60,
    )
    payload = jwt.decode(
        token, settings.mcp_jwt_secret, algorithms=["HS256"], issuer=settings.host_public_url
    )
    assert payload["typ"] == "connect"
    assert payload["sub"] == "bob"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
