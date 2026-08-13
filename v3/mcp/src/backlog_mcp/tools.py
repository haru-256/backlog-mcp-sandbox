"""tool の本体。JWT のユーザーから、その人の接続だけを見る。

未接続の案内に URL を載せない。チャットが OAuth の入口にならないためである。
"""

import json
from typing import Any

from .backlog import BacklogApi
from .space import resolve_space
from .store import MemoryStore

NOT_CONNECTED = "Backlog は未接続です。画面の接続ボタンから接続してください。"
NEED_SPACE = (
    "複数のスペースが接続されています。list_connected_spaces で確認し、space を指定してください。"
)
UNKNOWN_SPACE = "指定されたスペースはこのユーザーの接続にありません。"


def connected_spaces(store: MemoryStore, user_id: str) -> list[dict[str, str]]:
    """そのユーザーが OAuth したスペースの一覧。

    Args:
        store: 接続表。
        user_id: Chat 上のユーザー ID。JWT の `sub`。

    Returns:
        `domain` と `org_id` の dict のリスト。
    """
    return [
        {"domain": item.domain, "org_id": item.org_id} for item in store.list_connections(user_id)
    ]


def summarize_issue(issue: dict[str, Any]) -> dict[str, Any]:
    """Backlog の課題 JSON から、LLM に渡す項目だけを残す。

    Args:
        issue: `/api/v2/issues` の 1 件。

    Returns:
        id / issueKey / summary / status / assignee。
    """
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
    """そのユーザーの接続からスペースを一つ決め、課題の JSON 文字列を返す。

    Args:
        store: 接続表。
        api: Backlog REST。
        user_id: Chat 上のユーザー ID。
        space: Backlog のホスト名。1 本だけ接続していれば省略できる。
        status_id: 指定時だけその状態。省略時は未完了相当（1, 2, 3）。
        count: 取得件数の上限。

    Returns:
        成功時は `{"space": ..., "issues": ...}`。失敗時は日本語の案内（URL なし）。
    """
    connected = [item.domain for item in store.list_connections(user_id)]
    if not connected:
        return NOT_CONNECTED

    try:
        domain = resolve_space(connected, space)
    except ValueError:
        return UNKNOWN_SPACE

    if domain is None:
        if space:
            return UNKNOWN_SPACE
        return NEED_SPACE

    connection = store.get_connection(user_id, domain)
    if connection is None:
        return UNKNOWN_SPACE

    issues = await api.list_issues(
        domain, connection.access_token, status_id=status_id, count=count
    )
    summarized = [summarize_issue(issue) for issue in issues]
    return json.dumps({"space": domain, "issues": summarized}, ensure_ascii=False)
