import json
from typing import Any

from mcp.server.auth.middleware.auth_context import get_access_token

from .backlog import BacklogApi
from .space import normalize_space_domain, resolve_space
from .store import MemoryStore

NOT_CONNECTED = "Backlog は未接続です。画面の接続ボタンから接続してください。"
NEED_SPACE = (
    "複数のスペースが接続されています。list_connected_spaces で確認し、space を指定してください。"
)
UNKNOWN_SPACE = "指定されたスペースはこのユーザーの接続にありません。"


def current_user_id() -> str:
    token = get_access_token()
    if token is None or not token.subject:
        raise RuntimeError("authenticated user is missing")
    return token.subject


def list_connected_spaces_payload(store: MemoryStore, user_id: str) -> list[dict[str, str]]:
    return [
        {"domain": item.domain, "org_id": item.org_id} for item in store.list_connections(user_id)
    ]


def summarize_issue(issue: dict[str, Any]) -> dict[str, Any]:
    status = issue.get("status")
    status_name = status.get("name") if isinstance(status, dict) else None
    assignee = issue.get("assignee")
    assignee_name = assignee.get("name") if isinstance(assignee, dict) else None
    return {
        "id": issue.get("id"),
        "issueKey": issue.get("issueKey"),
        "summary": issue.get("summary"),
        "status": status_name,
        "assignee": assignee_name,
    }


async def list_issues_for_user(
    store: MemoryStore,
    api: BacklogApi,
    user_id: str,
    *,
    space: str | None,
    status_id: int | None,
    count: int,
) -> str:
    connected = [item.domain for item in store.list_connections(user_id)]
    if not connected:
        return NOT_CONNECTED

    requested = None
    if space:
        try:
            requested = normalize_space_domain(space)
        except ValueError:
            return UNKNOWN_SPACE

    if requested is not None and requested not in connected:
        return UNKNOWN_SPACE

    domain = resolve_space(connected, requested)
    if domain is None:
        return NEED_SPACE

    connection = store.get_connection(user_id, domain)
    if connection is None:
        return UNKNOWN_SPACE

    issues = await api.list_issues(
        domain, connection.access_token, status_id=status_id, count=count
    )
    summarized = [summarize_issue(issue) for issue in issues]
    return json.dumps({"space": domain, "issues": summarized}, ensure_ascii=False)
