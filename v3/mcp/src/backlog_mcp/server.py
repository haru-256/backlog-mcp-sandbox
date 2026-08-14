"""MCP Server の組み立て。入口は二つある。

`/mcp`    tool。Host が付ける Bearer JWT（typ=mcp）が要る。
`/health` 認証なし。Compose の生存確認用。

読む順は tools.py → backlog.py。このファイルは配線だけである。
"""

from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .auth import HostJwtVerifier
from .backlog import BacklogApi, HttpxBacklogApi
from .settings import Settings
from .tools import list_issues as run_list_issues


def create_server(
    settings: Settings,
    api: BacklogApi | None = None,
) -> MCPServer[None]:
    """tool を載せた Server を返す。テストは api を差し替える。

    Args:
        settings: JWT と公開 URL。
        api: 省略時は実 Backlog HTTP。

    Returns:
        `/mcp`・`/health` を持つ MCPServer。
    """
    backlog = api or HttpxBacklogApi()
    verifier = HostJwtVerifier(
        settings.mcp_jwt_secret,
        issuer=settings.host_public_url,
    )

    server = MCPServer(
        name="backlog-mcp",
        instructions="Backlog 課題を、渡されたスペースと token に対して一覧する。",
        token_verifier=verifier,
        # SDK は token_verifier と AuthSettings をセットで要求する。OAuth メタデータは使わない。
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(settings.host_public_url),
            resource_server_url=AnyHttpUrl(settings.mcp_public_url),
            required_scopes=["mcp"],
        ),
    )

    @server.custom_route("/health", methods=["GET"])
    async def health(_request: Request) -> Response:
        """プロセスが応答できることを返す。JWT は見ない。"""
        return JSONResponse({"ok": True})

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


def run() -> None:
    """Streamable HTTP で `/mcp` を待受ける。stdio では起動しない。

    Raises:
        pydantic.ValidationError: 必須 env が無い場合。
    """
    settings = Settings.from_env()
    server = create_server(settings)
    server.run(
        transport="streamable-http",
        host=settings.host,
        port=settings.port,
        streamable_http_path="/mcp",
    )
