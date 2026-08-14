import json

import pytest
from mcp import Client
from mcp.types import TextContent

from backlog_mcp.server import create_server
from backlog_mcp.settings import Settings


class FakeApi:
    async def list_issues(
        self, domain: str, access_token: str, *, status_id: int | None, count: int
    ) -> list[dict[str, object]]:
        del status_id, count
        return [
            {
                "id": 1,
                "issueKey": "A-1",
                "summary": "demo",
                "status": {"name": "未対応"},
                "assignee": None,
            }
        ]


def _result_text(result: object) -> str:
    structured = getattr(result, "structured_content", None)
    if structured is not None:
        return json.dumps(structured, ensure_ascii=False)
    blocks = [b.text for b in getattr(result, "content", []) if isinstance(b, TextContent)]
    return "\n".join(blocks)


@pytest.mark.anyio
async def test_client_lists_and_calls_list_issues() -> None:
    server = create_server(Settings(), api=FakeApi())
    async with Client(server) as client:
        listed = await client.list_tools()
        names = [tool.name for tool in listed.tools]
        assert names == ["list_issues"]
        result = await client.call_tool(
            "list_issues",
            {"space": "acme.backlog.com", "access_token": "tok-1"},
        )
    assert result.is_error is False
    text = _result_text(result)
    assert "A-1" in text
    assert "acme.backlog.com" in text


def test_settings_has_no_bind_port() -> None:
    loaded = Settings()
    assert loaded.issue_limit == 20
    assert not hasattr(loaded, "port")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
