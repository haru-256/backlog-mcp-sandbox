from typing import Any

import pytest
from mcp import Client
from mcp.server.mcpserver import MCPServer

from chat.connections import NOT_CONNECTED, REFRESH_FAILED
from chat.mcp_hub import McpHub, _prefix_tool_name, _split_prefixed, create_inprocess_server
from chat.session_tokens import SessionAuth
from chat.store import Connection, MemoryStore


def _echo_server(name: str, payload: str) -> MCPServer[None]:
    server = MCPServer(name=name)

    @server.tool()
    async def ping() -> str:
        return payload

    return server


@pytest.mark.anyio
async def test_prefix_and_route_two_inprocess_servers() -> None:
    left = _echo_server("left", "L")
    right = _echo_server("right", "R")
    async with Client(left) as a, Client(right) as b:
        hub = McpHub({"docs": a, "wiki": b}, MemoryStore(), "alice", None)
        tools = await hub.list_tools()
        names = [t["function"]["name"] for t in tools]
        assert "docs_ping" in names
        assert "wiki_ping" in names
        assert await hub.call_tool("docs_ping", {}) == '{"result": "L"}'
        assert await hub.call_tool("wiki_ping", {}) == '{"result": "R"}'


def test_split_prefixed_longest_id_wins() -> None:
    assert _split_prefixed("backlog_list_issues", ["back", "backlog"]) == (
        "backlog",
        "list_issues",
    )
    assert _prefix_tool_name("backlog", "list_issues") == "backlog_list_issues"


@pytest.mark.anyio
async def test_backlog_hides_space_and_token_and_injects_session_auth() -> None:
    from backlog_mcp.server import create_server
    from backlog_mcp.settings import Settings as BacklogSettings

    class FakeApi:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        async def list_issues(
            self, domain: str, access_token: str, *, status_id: int | None, count: int
        ) -> list[dict[str, Any]]:
            del status_id, count
            self.calls.append((domain, access_token))
            return []

    api = FakeApi()
    server = create_server(BacklogSettings(), api=api)
    store = MemoryStore()
    store.put_connection(
        Connection(
            user_id="alice",
            org_id="org-1",
            domain="acme.backlog.com",
            refresh_token="rtk",
        )
    )
    auth = SessionAuth(domain="acme.backlog.com", access_token="tok-session")
    async with Client(server) as client:
        hub = McpHub({"backlog": client}, store, "alice", auth)
        tools = await hub.list_tools()
        issues = next(t for t in tools if t["function"]["name"] == "backlog_list_issues")
        props = issues["function"]["parameters"]["properties"]
        assert "access_token" not in props
        assert "space" not in props
        text = await hub.call_tool(
            "backlog_list_issues",
            {"space": "forged.backlog.com", "access_token": "tok-forged"},
        )
    assert api.calls == [("acme.backlog.com", "tok-session")]
    assert "acme.backlog.com" in text


@pytest.mark.anyio
async def test_backlog_unconnected_does_not_call_mcp() -> None:
    from backlog_mcp.server import create_server
    from backlog_mcp.settings import Settings as BacklogSettings

    class FakeApi:
        async def list_issues(
            self, domain: str, access_token: str, *, status_id: int | None, count: int
        ) -> list[dict[str, Any]]:
            raise AssertionError("should not call backlog")

    server = create_server(BacklogSettings(), api=FakeApi())
    async with Client(server) as client:
        hub = McpHub({"backlog": client}, MemoryStore(), "alice", None)
        text = await hub.call_tool("backlog_list_issues", {})
    assert text == NOT_CONNECTED


@pytest.mark.anyio
async def test_backlog_refresh_failed_does_not_call_mcp() -> None:
    from backlog_mcp.server import create_server
    from backlog_mcp.settings import Settings as BacklogSettings

    class FakeApi:
        async def list_issues(
            self, domain: str, access_token: str, *, status_id: int | None, count: int
        ) -> list[dict[str, Any]]:
            raise AssertionError("should not call backlog")

    store = MemoryStore()
    store.put_connection(
        Connection(
            user_id="alice",
            org_id="org-1",
            domain="acme.backlog.com",
            refresh_token="rtk",
        )
    )
    server = create_server(BacklogSettings(), api=FakeApi())
    async with Client(server) as client:
        hub = McpHub({"backlog": client}, store, "alice", None)
        text = await hub.call_tool("backlog_list_issues", {})
    assert text == REFRESH_FAILED


def test_unknown_inprocess_id() -> None:
    with pytest.raises(ValueError, match="unknown in-process MCP id"):
        create_inprocess_server("nope")


@pytest.mark.anyio
async def test_http_kind_client_lists_tools() -> None:
    import asyncio
    import socket

    import uvicorn

    from chat.mcp_hub import open_mcp_hub
    from chat.settings import HttpMcp, Settings

    server = MCPServer(name="echo")

    @server.tool()
    async def ping() -> str:
        return "pong"

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    config = uvicorn.Config(
        app=server.streamable_http_app(host="127.0.0.1"),
        host="127.0.0.1",
        port=port,
        log_level="error",
    )
    uv_server = uvicorn.Server(config)
    task = asyncio.create_task(uv_server.serve())
    try:
        for _ in range(50):
            if uv_server.started:
                break
            await asyncio.sleep(0.05)
        settings = Settings.from_env()
        settings.mcp_servers = [
            HttpMcp(id="echo", kind="http", url=f"http://127.0.0.1:{port}/mcp")
        ]
        async with open_mcp_hub(settings, MemoryStore(), "alice", None) as hub:
            tools = await hub.list_tools()
        names = [t["function"]["name"] for t in tools]
        assert "echo_ping" in names
    finally:
        uv_server.should_exit = True
        await task


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
