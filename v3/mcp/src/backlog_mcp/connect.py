import secrets
from html import escape
from urllib.parse import quote

import httpx
from mcp.server.mcpserver import MCPServer
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from .backlog import BacklogApi, authorize_url
from .jwt_tokens import TokenError, decode_token
from .settings import Settings
from .space import normalize_space_domain
from .store import Connection, MemoryStore, PendingOAuth, SpaceApp

CONNECT_FORM = """<!doctype html>
<html lang="ja">
<head><meta charset="utf-8"><title>Backlog を接続</title></head>
<body>
  <h1>Backlog を接続</h1>
  <p>Chat のテナント <code>{org}</code> / ユーザー <code>{user}</code> に、Backlog スペースを追加します。</p>
  {error}
  <form method="post" action="/connect">
    <input type="hidden" name="state" value="{state}">
    <p>
      <label>スペース<br>
        <input name="space" size="40" placeholder="acme.backlog.com" required>
      </label>
    </p>
    <p>未登録のスペースでは、そのスペースに作った OAuth アプリの値も入力してください。</p>
    <p>
      <label>Client ID（未登録時のみ必須）<br>
        <input name="client_id" size="40">
      </label>
    </p>
    <p>
      <label>Client Secret（未登録時のみ必須）<br>
        <input name="client_secret" size="40" type="password">
      </label>
    </p>
    <button type="submit">Backlog で認可する</button>
  </form>
</body>
</html>
"""


def _page(org: str, user: str, state: str, error: str | None = None) -> HTMLResponse:
    error_html = f'<p role="alert">{escape(error)}</p>' if error else ""
    body = CONNECT_FORM.format(
        org=escape(org),
        user=escape(user),
        state=escape(state),
        error=error_html,
    )
    status = 400 if error else 200
    return HTMLResponse(body, status_code=status)


def _error_page(message: str, status: int = 400) -> HTMLResponse:
    return HTMLResponse(
        f"<!doctype html><html lang='ja'><body><p>{escape(message)}</p></body></html>",
        status_code=status,
    )


def register_connect_routes(
    server: MCPServer[None],
    settings: Settings,
    store: MemoryStore,
    api: BacklogApi,
) -> None:
    """MCPServer.custom_route に接続フローを載せる。"""

    @server.custom_route("/health", methods=["GET"])
    async def health(_request: Request) -> Response:
        return JSONResponse({"ok": True})

    @server.custom_route("/connect", methods=["GET"])
    async def connect_get(request: Request) -> Response:
        state = request.query_params.get("state") or ""
        try:
            payload = decode_token(
                state, settings.mcp_jwt_secret, "connect", issuer=settings.host_public_url
            )
        except TokenError:
            return _error_page("接続用の state が無効です。Chat の接続ボタンからやり直してください。")
        return _page(str(payload["org"]), str(payload["sub"]), state)

    @server.custom_route("/connect", methods=["POST"])
    async def connect_post(request: Request) -> Response:
        form = await request.form()
        state = str(form.get("state") or "")
        try:
            payload = decode_token(
                state, settings.mcp_jwt_secret, "connect", issuer=settings.host_public_url
            )
        except TokenError:
            return _error_page("接続用の state が無効です。Chat の接続ボタンからやり直してください。")

        user_id = str(payload["sub"])
        org_id = str(payload["org"])
        try:
            domain = normalize_space_domain(str(form.get("space") or ""))
        except ValueError:
            return _page(org_id, user_id, state, "スペースを入力してください。")

        app = store.get_space_app(domain)
        if app is None:
            client_id = str(form.get("client_id") or "").strip()
            client_secret = str(form.get("client_secret") or "").strip()
            if not client_id or not client_secret:
                return _page(
                    org_id,
                    user_id,
                    state,
                    "このスペースは未登録です。Client ID と Client Secret を入力してください。",
                )
            app = SpaceApp(domain=domain, client_id=client_id, client_secret=client_secret)
            store.put_space_app(app)

        oauth_state = secrets.token_urlsafe(24)
        store.put_pending(oauth_state, PendingOAuth(user_id=user_id, org_id=org_id, domain=domain))
        redirect_uri = f"{settings.mcp_public_url}/callback"
        location = authorize_url(domain, app.client_id, redirect_uri, oauth_state)
        return RedirectResponse(location, status_code=302)

    @server.custom_route("/callback", methods=["GET"])
    async def callback(request: Request) -> Response:
        error = request.query_params.get("error")
        if error:
            return _error_page(f"Backlog の認可が拒否されました: {error}")

        oauth_state = request.query_params.get("state") or ""
        code = request.query_params.get("code") or ""
        pending = store.pop_pending(oauth_state)
        if pending is None or not code:
            return _error_page("認可の state が無効か、期限切れです。接続ボタンからやり直してください。")

        app = store.get_space_app(pending.domain)
        if app is None:
            return _error_page("このスペースの OAuth アプリが見つかりません。")

        redirect_uri = f"{settings.mcp_public_url}/callback"
        try:
            access, refresh = await api.exchange_code(
                pending.domain, app.client_id, app.client_secret, code, redirect_uri
            )
        except (httpx.HTTPError, RuntimeError):
            return _error_page("Backlog のトークン交換に失敗しました。", status=502)

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
