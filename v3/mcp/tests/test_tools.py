from typing import Any

import pytest

from backlog_mcp.tools import list_issues, summarize_issue


class FakeBacklog:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def list_issues(
        self, domain: str, access_token: str, *, status_id: int | None, count: int
    ) -> list[dict[str, Any]]:
        del status_id, count
        self.calls.append((domain, access_token))
        return [{"id": 1, "issueKey": "A-1", "summary": "demo", "status": {"name": "未対応"}}]


@pytest.mark.anyio
async def test_list_issues_uses_given_token_and_space() -> None:
    api = FakeBacklog()
    text = await list_issues(
        api, space="acme.backlog.com", access_token="tok-1", status_id=None, count=20
    )
    assert "A-1" in text
    assert "acme.backlog.com" in text
    assert api.calls == [("acme.backlog.com", "tok-1")]


def test_summarize_issue() -> None:
    out = summarize_issue(
        {"id": 1, "issueKey": "A-1", "summary": "demo", "status": {"name": "未対応"}, "assignee": None}
    )
    assert out["issueKey"] == "A-1"
    assert out["status"] == "未対応"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
