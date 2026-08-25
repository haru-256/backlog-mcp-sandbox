"""チャット外の Backlog OAuth。

流れは三つだけである。

1. GET  /backlog/connect   query の user_id / org_id でフォームを出す
2. POST /backlog/connect   スペースを受け、Backlog へ 302。client は環境変数
3. GET  /backlog/callback  認可コードを token に換え、connections に保存する
"""

import secrets
from urllib.parse import quote

import httpx
from fastapi import Request
from fastapi.responses import RedirectResponse, Response

from .backlog_oauth import authorize_url, exchange_code
from .connect_html import connect_form, error_page
from .settings import Settings
from .space import normalize_space_domain
from .store import Connection, MemoryStore, PendingOAuth


async def handle_connect_get(request: Request) -> Response:
    """接続ボタンからの到着。フォームを出す。

    Args:
        request: `user_id` と `org_id` query を持つ GET。

    Returns:
        フォーム、または query が足りなければエラー HTML。
    """
    user_id = request.query_params.get("user_id") or ""
    org_id = request.query_params.get("org_id") or ""
    if not user_id or not org_id:
        return error_page("user_id と org_id が必要です。")
    return connect_form(org_id, user_id)


async def handle_connect_post(
    request: Request,
    settings: Settings,
    store: MemoryStore,
) -> Response:
    """フォーム送信。スペースを受け、共有の OAuth アプリで Backlog へ飛ばす。

    Args:
        request: user_id / org_id / space を含む POST。
        settings: Redirect URI と OAuth アプリ。
        store: pending の表。

    Returns:
        Backlog 同意画面への 302。入力不足ならフォームを 400 で返す。
    """
    form = await request.form()
    user_id = str(form.get("user_id") or "")
    org_id = str(form.get("org_id") or "")
    if not user_id or not org_id:
        return error_page("user_id と org_id が必要です。")
    try:
        domain = normalize_space_domain(str(form.get("space") or ""))
    except ValueError:
        return connect_form(org_id, user_id, "スペースを入力してください。")

    oauth_state = secrets.token_urlsafe(24)
    store.put_pending(oauth_state, PendingOAuth(user_id=user_id, org_id=org_id, domain=domain))
    location = authorize_url(
        domain, settings.backlog_client_id, settings.oauth_redirect_uri(), oauth_state
    )
    return RedirectResponse(location, status_code=302)


async def handle_callback(
    request: Request,
    settings: Settings,
    store: MemoryStore,
) -> Response:
    """Backlog から戻る。code を token に換え、検証 UI へ戻す。token は URL に載せない。

    Args:
        request: `code` と `state` を持つ GET。拒否時は `error`。
        settings: Redirect URI とフロントの URL と OAuth アプリ。
        store: pending を取り出し、connections に書く表。

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

    try:
        async with httpx.AsyncClient() as http:
            _access, refresh = await exchange_code(
                http,
                pending.domain,
                settings.backlog_client_id,
                settings.backlog_client_secret,
                code,
                settings.oauth_redirect_uri(),
            )
    except (httpx.HTTPError, RuntimeError):
        return error_page("Backlog のトークン交換に失敗しました。", status=502)

    if refresh is None:
        return error_page("Backlog が refresh token を返しませんでした。接続ボタンからやり直してください。")

    store.put_connection(
        Connection(
            user_id=pending.user_id,
            org_id=pending.org_id,
            domain=pending.domain,
            refresh_token=refresh,
        )
    )
    done = f"{settings.frontend_public_url}/?connected=1&space={quote(pending.domain)}"
    return RedirectResponse(done, status_code=302)
