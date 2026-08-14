from types import SimpleNamespace
from typing import Any

import pytest

from chat.mcp_client import BacklogMCP
from chat.store import Connection, MemoryStore


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def list_tools(self) -> object:
        return SimpleNamespace(
            tools=[
                SimpleNamespace(
                    name="list_issues",
                    description="issues",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "space": {"type": "string"},
                            "access_token": {"type": "string"},
                            "status_id": {"type": "integer"},
                        },
                        "required": ["space", "access_token"],
                    },
                )
            ]
        )

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> object:
        self.calls.append((name, arguments))
        return SimpleNamespace(
            structured_content={"space": arguments.get("space"), "issues": []},
            content=[],
            is_error=False,
        )


@pytest.mark.anyio
async def test_list_tools_hides_access_token_and_adds_connected_spaces() -> None:
    mcp = BacklogMCP(FakeSession(), MemoryStore(), "alice")
    tools = await mcp.list_tools()
    names = [t["function"]["name"] for t in tools]
    assert "list_connected_spaces" in names
    issues = next(t for t in tools if t["function"]["name"] == "list_issues")
    props = issues["function"]["parameters"]["properties"]
    assert "access_token" not in props
    required = issues["function"]["parameters"].get("required") or []
    assert "access_token" not in required


@pytest.mark.anyio
async def test_list_issues_injects_store_token_not_llm_token() -> None:
    store = MemoryStore()
    store.put_connection(
        Connection(
            user_id="alice",
            org_id="org-1",
            domain="acme.backlog.com",
            access_token="tok-real",
        )
    )
    session = FakeSession()
    mcp = BacklogMCP(session, store, "alice")
    text = await mcp.call_tool(
        "list_issues",
        {"space": "acme.backlog.com", "access_token": "tok-forged"},
    )
    assert session.calls == [
        (
            "list_issues",
            {
                "space": "acme.backlog.com",
                "access_token": "tok-real",
                "status_id": None,
            },
        )
    ]
    assert "acme.backlog.com" in text


@pytest.mark.anyio
async def test_list_issues_unconnected_does_not_call_mcp() -> None:
    session = FakeSession()
    mcp = BacklogMCP(session, MemoryStore(), "alice")
    text = await mcp.call_tool("list_issues", {})
    assert text == "Backlog は未接続です。画面の接続ボタンから接続してください。"
    assert session.calls == []


@pytest.mark.anyio
async def test_list_connected_spaces_is_local() -> None:
    store = MemoryStore()
    store.put_connection(
        Connection(
            user_id="alice",
            org_id="org-1",
            domain="a.backlog.com",
            access_token="tok-a",
        )
    )
    session = FakeSession()
    mcp = BacklogMCP(session, store, "alice")
    text = await mcp.call_tool("list_connected_spaces", {})
    assert "a.backlog.com" in text
    assert session.calls == []


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
