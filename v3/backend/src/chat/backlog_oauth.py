"""Host が Backlog OAuth の認可 URL と token 交換を行う。"""

from urllib.parse import urlencode

import httpx


def authorize_url(domain: str, client_id: str, redirect_uri: str, state: str) -> str:
    """ユーザーを Backlog の同意画面へ送る URL。

    Args:
        domain: 接続したいスペース。
        client_id: Host が環境変数から読む OAuth アプリ。
        redirect_uri: アプリ登録と同じ URI。`{HOST_PUBLIC_URL}/backlog/callback`。
        state: callback で本人確認するためのランダム値。

    Returns:
        `https://{domain}/OAuth2AccessRequest.action?...`
    """
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    return f"https://{domain}/OAuth2AccessRequest.action?{query}"


async def exchange_code(
    http: httpx.AsyncClient,
    domain: str,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> tuple[str, str | None]:
    """認可コードを access token に換える。

    Args:
        http: 差し込まれた HTTP クライアント。テストで偽応答を返すときに使う。
        domain: 同意したスペースのホスト名。
        client_id: Host が環境変数から読む OAuth アプリ。
        client_secret: 同上。
        code: callback が受け取った認可コード。
        redirect_uri: アプリ登録と同じ URI。

    Returns:
        (access_token, refresh_token)。refresh が無いときは None。

    Raises:
        httpx.HTTPError: HTTP が失敗した場合。
        RuntimeError: JSON に access_token が無い場合。
    """
    response = await http.post(
        f"https://{domain}/api/v2/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
    response.raise_for_status()
    body = response.json()
    access = body.get("access_token")
    if not isinstance(access, str) or not access:
        raise RuntimeError("Backlog token response did not include access_token")
    refresh = body.get("refresh_token")
    refresh_token = refresh if isinstance(refresh, str) else None
    return access, refresh_token


async def refresh_access_token(
    http: httpx.AsyncClient,
    domain: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> tuple[str, str]:
    """refresh token から access token を取り直す。

    Args:
        http: 差し込まれた HTTP クライアント。
        domain: そのスペースのホスト名。
        client_id: Host が環境変数から読む OAuth アプリ。
        client_secret: 同上。
        refresh_token: store が持っている refresh。

    Returns:
        (access_token, refresh_token)。レスポンスに refresh が無ければ引数の値。

    Raises:
        httpx.HTTPError: HTTP が失敗した場合。
        RuntimeError: JSON に access_token が無い場合。
    """
    response = await http.post(
        f"https://{domain}/api/v2/oauth2/token",
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        },
    )
    response.raise_for_status()
    body = response.json()
    access = body.get("access_token")
    if not isinstance(access, str) or not access:
        raise RuntimeError("Backlog token response did not include access_token")
    rotated = body.get("refresh_token")
    new_refresh = rotated if isinstance(rotated, str) and rotated else refresh_token
    return access, new_refresh
