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
    """Host が接続ボタン用に署名した JWT を検証する。

    Args:
        state: `/connect?state=` または hidden field の JWT。
        settings: 秘密鍵と Host の公開 URL。

    Returns:
        `sub`（user_id）と `org`（org_id）を含む claims。

    Raises:
        TokenError: 署名・期限・typ が合わない場合。
    """
    return decode_token(state, settings.mcp_jwt_secret, "connect", issuer=settings.host_public_url)


def register_connect_routes(
    server: MCPServer[None],
    settings: Settings,
    store: MemoryStore,
    api: BacklogApi,
) -> None:
    """`/connect` と `/callback` を MCP プロセスに載せる。`/health` は server.py。

    Args:
        server: ルートを足す MCPServer。
        settings: Redirect URI と JWT 検証に使う設定。
        store: OAuth アプリと接続の表。
        api: 認可コードを token に換える Backlog クライアント。
    """

    @server.custom_route("/connect", methods=["GET"])
    async def connect_get(request: Request) -> Response:
        """GET /connect。処理は handle_connect_get。"""
        return await handle_connect_get(request, settings)

    @server.custom_route("/connect", methods=["POST"])
    async def connect_post(request: Request) -> Response:
        """POST /connect。処理は handle_connect_post。"""
        return await handle_connect_post(request, settings, store)

    @server.custom_route("/callback", methods=["GET"])
    async def callback(request: Request) -> Response:
        """GET /callback。処理は handle_callback。"""
        return await handle_callback(request, settings, store, api)


async def handle_connect_get(request: Request, settings: Settings) -> Response:
    """接続ボタンからの到着。フォームを出す。

    Args:
        request: `state` query を持つ GET。
        settings: connect JWT の検証に使う設定。

    Returns:
        フォーム、または state が無効ならエラー HTML。
    """
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
    """フォーム送信。未登録スペースなら OAuth アプリを覚え、Backlog へ飛ばす。

    Args:
        request: space と、未登録時は client_id / client_secret を含む POST。
        settings: Redirect URI と JWT 検証。
        store: アプリと pending の表。

    Returns:
        Backlog 同意画面への 302。入力不足ならフォームを 400 で返す。
    """
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
    """Backlog から戻る。code を token に換え、検証 UI へ戻す。token は URL に載せない。

    Args:
        request: `code` と `state` を持つ GET。拒否時は `error`。
        settings: Redirect URI とフロントの URL。
        store: pending を取り出し、connections に書く表。
        api: token 交換。

    Returns:
        検証 UI への 302。失敗ならエラー HTML。
    """
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
