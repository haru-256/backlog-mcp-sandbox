"""渡された token で課題を取る。接続の有無は見ない。"""

import json
from typing import Any

from .backlog import BacklogApi


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


async def list_issues(
    api: BacklogApi,
    *,
    space: str,
    access_token: str,
    status_id: int | None,
    count: int,
) -> str:
    """渡されたスペースと token で課題の JSON 文字列を返す。

    Args:
        api: Backlog REST。
        space: Backlog のホスト名。
        access_token: Host が渡したそのスペースの token。
        status_id: 指定時だけその状態。省略時は未完了相当（1, 2, 3）。
        count: 取得件数の上限。

    Returns:
        `{"space": ..., "issues": ...}`。
    """
    issues = await api.list_issues(space, access_token, status_id=status_id, count=count)
    summarized = [summarize_issue(issue) for issue in issues]
    return json.dumps({"space": space, "issues": summarized}, ensure_ascii=False)
