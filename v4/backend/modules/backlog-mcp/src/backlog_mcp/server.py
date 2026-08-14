"""MCP Server の組み立て。HTTP では待受けない。Host が Client(server) で開く。"""

from mcp.server.mcpserver import MCPServer

from .backlog import BacklogApi, HttpxBacklogApi
from .settings import Settings
from .tools import list_issues as run_list_issues


def create_server(
    settings: Settings,
    api: BacklogApi | None = None,
) -> MCPServer[None]:
    """tool を載せた Server を返す。テストは api を差し替える。

    Args:
        settings: 件数上限。
        api: 省略時は実 Backlog HTTP。

    Returns:
        list_issues を持つ MCPServer。
    """
    backlog = api or HttpxBacklogApi()
    server = MCPServer(
        name="backlog-mcp",
        instructions="Backlog 課題を、渡されたスペースと token に対して一覧する。",
    )

    @server.tool()
    async def list_issues(
        space: str, access_token: str, status_id: int | None = None
    ) -> str:
        """指定スペースの課題を一覧する。未完了相当がデフォルト。"""
        return await run_list_issues(
            backlog,
            space=space,
            access_token=access_token,
            status_id=status_id,
            count=settings.issue_limit,
        )

    return server
