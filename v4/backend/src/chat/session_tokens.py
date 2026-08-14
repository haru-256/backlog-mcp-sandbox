"""chat 1 回分の access token を、store の refresh から発行する。"""

from dataclasses import dataclass

import httpx
from loguru import logger

from .backlog_oauth import refresh_access_token
from .store import Connection, MemoryStore


@dataclass(frozen=True)
class SessionAuth:
    """この chat で使う、1 本のスペースと access token。"""

    domain: str
    access_token: str


async def issue_session_auth(
    http: httpx.AsyncClient,
    store: MemoryStore,
    user_id: str,
    client_id: str,
    client_secret: str,
) -> SessionAuth | None:
    """そのユーザーの唯一の接続を refresh し、成功したら SessionAuth を返す。

    Args:
        http: 差し込まれた HTTP クライアント。
        store: 接続表。成功時は refresh を更新する。
        user_id: Chat 上のユーザー ID。
        client_id: OAuth アプリ。
        client_secret: 同上。

    Returns:
        成功時は SessionAuth。未接続または refresh 失敗なら None。失敗しても store の行は消さない。
    """
    connection = store.get_connection(user_id)
    if connection is None:
        return None
    try:
        access, refresh = await refresh_access_token(
            http,
            connection.domain,
            client_id,
            client_secret,
            connection.refresh_token,
        )
    except (httpx.HTTPError, RuntimeError) as exc:
        logger.debug(f"refresh failed for {connection.domain}: {exc}")
        return None
    if refresh != connection.refresh_token:
        store.put_connection(
            Connection(
                user_id=connection.user_id,
                org_id=connection.org_id,
                domain=connection.domain,
                refresh_token=refresh,
            )
        )
    return SessionAuth(domain=connection.domain, access_token=access)
