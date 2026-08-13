"""Backlog への HTTP。OAuth と課題取得だけを持つ。

MCP も Host も、このモジュール以外から Backlog の URL を組み立てない。
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx


class BacklogApi(Protocol):
    """実 HTTP とテスト用の偽クライアントが同じ操作を持つ。"""

    async def exchange_code(
        self, domain: str, client_id: str, client_secret: str, code: str, redirect_uri: str
    ) -> tuple[str, str | None]: ...

    async def list_issues(
        self, domain: str, access_token: str, *, status_id: int | None, count: int
    ) -> list[dict[str, Any]]: ...


class HttpxBacklogApi:
    """httpx で Backlog REST を叩く実装。"""

    def __init__(self, http: httpx.AsyncClient | None = None) -> None:
        self._http = http

    @asynccontextmanager
    async def _client(self) -> AsyncIterator[httpx.AsyncClient]:
        if self._http is not None:
            yield self._http
            return
        async with httpx.AsyncClient() as client:
            yield client

    async def exchange_code(
        self, domain: str, client_id: str, client_secret: str, code: str, redirect_uri: str
    ) -> tuple[str, str | None]:
        """認可コードを access token に換える。

        Args:
            domain: 同意したスペースのホスト名。
            client_id: そのスペースの OAuth アプリ。
            client_secret: 同上。
            code: callback が受け取った認可コード。
            redirect_uri: アプリ登録と同じ URI。

        Returns:
            (access_token, refresh_token)。refresh が無いときは None。

        Raises:
            httpx.HTTPError: HTTP が失敗した場合。
            RuntimeError: JSON に access_token が無い場合。
        """
        async with self._client() as client:
            response = await client.post(
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

    async def list_issues(
        self, domain: str, access_token: str, *, status_id: int | None, count: int
    ) -> list[dict[str, Any]]:
        """そのユーザーの token で課題を取る。権限は Backlog 側が決める。

        Args:
            domain: スペースのホスト名。
            access_token: そのユーザーが同意した token。
            status_id: 指定時だけその状態。省略時は未完了相当（1, 2, 3）。
            count: 件数上限。

        Returns:
            課題の dict のリスト。

        Raises:
            httpx.HTTPError: HTTP が失敗した場合。
            TypeError: レスポンスが list でない場合。
        """
        params: dict[str, str | list[str]] = {"count": str(count)}
        if status_id is not None:
            params["statusId[]"] = str(status_id)
        else:
            params["statusId[]"] = ["1", "2", "3"]

        async with self._client() as client:
            response = await client.get(
                f"https://{domain}/api/v2/issues",
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            body = response.json()

        if not isinstance(body, list):
            raise TypeError("Backlog issues response was not a list")
        return [item for item in body if isinstance(item, dict)]


def authorize_url(domain: str, client_id: str, redirect_uri: str, state: str) -> str:
    """ユーザーを Backlog の同意画面へ送る URL。

    Args:
        domain: 接続したいスペース。
        client_id: そのスペースの OAuth アプリ。
        redirect_uri: アプリ登録と同じ URI。v3 では `{MCP_PUBLIC_URL}/callback`。
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
