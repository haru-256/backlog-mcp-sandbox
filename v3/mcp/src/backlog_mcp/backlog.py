from typing import Any, Protocol
from urllib.parse import urlencode

import httpx


class BacklogApi(Protocol):
    async def exchange_code(
        self, domain: str, client_id: str, client_secret: str, code: str, redirect_uri: str
    ) -> tuple[str, str | None]: ...

    async def list_issues(
        self, domain: str, access_token: str, *, status_id: int | None, count: int
    ) -> list[dict[str, Any]]: ...


class HttpxBacklogApi:
    """Backlog REST API の薄いクライアント。"""

    def __init__(self, http: httpx.AsyncClient | None = None) -> None:
        self._http = http

    async def exchange_code(
        self, domain: str, client_id: str, client_secret: str, code: str, redirect_uri: str
    ) -> tuple[str, str | None]:
        client = self._http or httpx.AsyncClient()
        owns = self._http is None
        try:
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
        finally:
            if owns:
                await client.aclose()

        access = body.get("access_token")
        if not isinstance(access, str) or not access:
            raise RuntimeError("Backlog token response did not include access_token")
        refresh = body.get("refresh_token")
        refresh_token = refresh if isinstance(refresh, str) else None
        return access, refresh_token

    async def list_issues(
        self, domain: str, access_token: str, *, status_id: int | None, count: int
    ) -> list[dict[str, Any]]:
        params: dict[str, str | list[str]] = {"count": str(count)}
        if status_id is not None:
            params["statusId[]"] = str(status_id)
        else:
            params["statusId[]"] = ["1", "2", "3"]

        client = self._http or httpx.AsyncClient()
        owns = self._http is None
        try:
            response = await client.get(
                f"https://{domain}/api/v2/issues",
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            body = response.json()
        finally:
            if owns:
                await client.aclose()

        if not isinstance(body, list):
            raise TypeError("Backlog issues response was not a list")
        return [item for item in body if isinstance(item, dict)]


def authorize_url(domain: str, client_id: str, redirect_uri: str, state: str) -> str:
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    return f"https://{domain}/OAuth2AccessRequest.action?{query}"
