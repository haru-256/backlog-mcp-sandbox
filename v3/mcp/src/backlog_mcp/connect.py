"""チャット外の Backlog OAuth。`/mcp` の JWT は使わない。

流れは三つだけである。

1. GET  /connect   Host が付けた typ=connect の JWT を検証し、フォームを出す
2. POST /connect   スペース（未登録なら OAuth アプリ）を受け、Backlog へ 302
3. GET  /callback  認可コードを token に換え、connections に保存する

`custom_route` は SDK の token_verifier を通さない。身元は query/form の `state` だけである。
"""

import secrets
from typing import Any
from urllib.parse import quote

import httpx
from mcp.server.mcpserver import MCPServer
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from .backlog import BacklogApi, authorize_url
from .connect_html import connect_form, error_page
from .jwt_tokens import TokenError, decode_token
from .settings import Settings
from .space import normalize_space_domain
from .store import Connection, MemoryStore, PendingOAuth, SpaceApp

_INVALID_STATE = "接続用の state が無効です。Chat の接続ボタンからやり直してください。"


def _connect_claims(state: str, settings: Settings) -> dict[str, Any]:
    """Host が接続ボタン用に署名した JWT を検証する。"""
    return decode_token(state, settings.mcp_jwt_secret, "connect", issuer=settings.host_public_url)


def register_connect_routes(
    server: MCPServer[None],
    settings: Settings,
    store: MemoryStore,
    api: BacklogApi,
) -> None:
    """`/connect` と `/callback` を MCP プロセスに載せる。`/health` は server.py。"""

    @server.custom_route("/connect", methods=["GET"])
    async def connect_get(request: Request) -> Response:
        return await handle_connect_get(request, settings)

    @server.custom_route("/connect", methods=["POST"])
    async def connect_post(request: Request) -> Response:
        return await handle_connect_post(request, settings, store)

    @server.custom_route("/callback", methods=["GET"])
    async def callback(request: Request) -> Response:
        return await handle_callback(request, settings, store, api)


async def handle_connect_get(request: Request, settings: Settings) -> Response:
    """接続ボタンからの到着。フォームを出す。"""
    state = request.query_params.get("state") or ""
    try:
        payload = _connect_claims(state, settings)
    except TokenError:
        return error_page(_INVALID_STATE)
    return connect_form(str(payload["org"]), str(payload["sub"]), state)


async def handle_connect_post(
    request: Request,
    settings: Settings,
    store: MemoryStore,
) -> Response:
    """フォーム送信。未登録スペースなら OAuth アプリを覚え、Backlog へ飛ばす。"""
    form = await request.form()
    state = str(form.get("state") or "")
    try:
        payload = _connect_claims(state, settings)
    except TokenError:
        return error_page(_INVALID_STATE)

    user_id = str(payload["sub"])
    org_id = str(payload["org"])
    try:
        domain = normalize_space_domain(str(form.get("space") or ""))
    except ValueError:
        return connect_form(org_id, user_id, state, "スペースを入力してください。")

    app = store.get_space_app(domain)
    if app is None:
        client_id = str(form.get("client_id") or "").strip()
        client_secret = str(form.get("client_secret") or "").strip()
        if not client_id or not client_secret:
            return connect_form(
                org_id,
                user_id,
                state,
                "このスペースは未登録です。Client ID と Client Secret を入力してください。",
            )
        app = SpaceApp(domain=domain, client_id=client_id, client_secret=client_secret)
        store.put_space_app(app)

    oauth_state = secrets.token_urlsafe(24)
    store.put_pending(oauth_state, PendingOAuth(user_id=user_id, org_id=org_id, domain=domain))
    location = authorize_url(domain, app.client_id, settings.oauth_redirect_uri(), oauth_state)
    return RedirectResponse(location, status_code=302)


async def handle_callback(
    request: Request,
    settings: Settings,
    store: MemoryStore,
    api: BacklogApi,
) -> Response:
    """Backlog から戻る。code を token に換え、検証 UI へ戻す。token は URL に載せない。"""
    error = request.query_params.get("error")
    if error:
        return error_page(f"Backlog の認可が拒否されました: {error}")

    oauth_state = request.query_params.get("state") or ""
    code = request.query_params.get("code") or ""
    pending = store.pop_pending(oauth_state)
    if pending is None or not code:
        return error_page("認可の state が無効か、期限切れです。接続ボタンからやり直してください。")

    app = store.get_space_app(pending.domain)
    if app is None:
        return error_page("このスペースの OAuth アプリが見つかりません。")

    try:
        access, refresh = await api.exchange_code(
            pending.domain,
            app.client_id,
            app.client_secret,
            code,
            settings.oauth_redirect_uri(),
        )
    except (httpx.HTTPError, RuntimeError):
        return error_page("Backlog のトークン交換に失敗しました。", status=502)

    store.put_connection(
        Connection(
            user_id=pending.user_id,
            org_id=pending.org_id,
            domain=pending.domain,
            access_token=access,
            refresh_token=refresh,
        )
    )
    done = f"{settings.frontend_public_url}/?connected=1&space={quote(pending.domain)}"
    return RedirectResponse(done, status_code=302)
