"""Backlog への HTTP。課題取得だけを持つ。

MCP も Host も、このモジュール以外から Backlog の URL を組み立てない。
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Protocol

import httpx


class BacklogApi(Protocol):
    """実 HTTP とテスト用の偽クライアントが同じ操作を持つ。

    `list_issues` はその token で課題を取る。
    """

    async def list_issues(
        self, domain: str, access_token: str, *, status_id: int | None, count: int
    ) -> list[dict[str, Any]]: ...


class HttpxBacklogApi:
    """httpx で Backlog REST を叩く実装。"""

    def __init__(self, http: httpx.AsyncClient | None = None) -> None:
        """HTTP クライアントを任意で差し込む。テストで偽応答を返すときに使う。

        Args:
            http: 省略時は呼び出しごとに AsyncClient を開いて閉じる。
        """
        self._http = http

    @asynccontextmanager
    async def _client(self) -> AsyncIterator[httpx.AsyncClient]:
        """差し込まれた client があればそれを使い、無ければ短命の client を開く。"""
        if self._http is not None:
            yield self._http
            return
        async with httpx.AsyncClient() as client:
            yield client

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
