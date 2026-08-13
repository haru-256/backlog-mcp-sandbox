"""MCP Server の組み立て。入口は二つある。

`/mcp`     tool。Host が付ける Bearer JWT（typ=mcp）が要る。
`/connect` ブラウザの OAuth。typ=connect。チャットの tool からは呼ばない。
`/health`  認証なし。Compose の生存確認用。

読む順は store.py → connect.py → tools.py。このファイルは配線だけである。
"""

from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .auth import HostJwtVerifier, current_user_id
from .backlog import BacklogApi, HttpxBacklogApi
from .connect import register_connect_routes
from .settings import Settings
from .store import MemoryStore
from .tools import connected_spaces, list_issues_for_user


def create_server(
    settings: Settings,
    store: MemoryStore | None = None,
    api: BacklogApi | None = None,
) -> MCPServer[None]:
    """tool と接続ルートを載せた Server を返す。テストは store と api を差し替える。

    Args:
        settings: JWT と公開 URL。
        store: 省略時は空のメモリ。
        api: 省略時は実 Backlog HTTP。
    """
    memory = store or MemoryStore()
    backlog = api or HttpxBacklogApi()
    verifier = HostJwtVerifier(
        settings.mcp_jwt_secret,
        audience=settings.mcp_public_url,
        issuer=settings.host_public_url,
    )

    server = MCPServer(
        name="backlog-mcp",
        instructions="Backlog 課題を、接続済みスペースに対して一覧する。",
        token_verifier=verifier,
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(settings.host_public_url),
            resource_server_url=AnyHttpUrl(settings.mcp_public_url),
            required_scopes=["mcp"],
        ),
    )

    @server.custom_route("/health", methods=["GET"])
    async def health(_request: Request) -> Response:
        return JSONResponse({"ok": True})

    @server.tool()
    async def list_connected_spaces() -> list[dict[str, str]]:
        """このユーザーが OAuth 接続した Backlog スペースを返す。"""
        return connected_spaces(memory, current_user_id())

    @server.tool()
    async def list_issues(space: str | None = None, status_id: int | None = None) -> str:
        """接続済みスペースの課題を一覧する。未完了相当がデフォルト。

        接続が 2 本以上あるときは space（例: acme.backlog.com）が必須。
        未接続なら、画面の接続ボタンから接続するよう案内する（URL は返さない）。
        """
        return await list_issues_for_user(
            memory,
            backlog,
            current_user_id(),
            space=space,
            status_id=status_id,
            count=settings.issue_limit,
        )

    register_connect_routes(server, settings, memory, backlog)
    return server


def transport_security(settings: Settings) -> TransportSecuritySettings:
    """Docker の Host ヘッダ（`mcp:3333` など）を許可する。"""
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=settings.allowed_host_list(),
        allowed_origins=settings.allowed_origin_list(),
    )


def run() -> None:
    """Streamable HTTP で `/mcp` を待受ける。stdio では起動しない。"""
    settings = Settings.from_env()
    server = create_server(settings)
    server.run(
        transport="streamable-http",
        host=settings.host,
        port=settings.port,
        streamable_http_path="/mcp",
        transport_security=transport_security(settings),
    )
