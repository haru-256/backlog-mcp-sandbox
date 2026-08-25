"""chat 1 回分の access token を、store の refresh から発行する。"""

import httpx
from loguru import logger

from .backlog_oauth import refresh_access_token
from .store import Connection, MemoryStore


async def issue_session_tokens(
    http: httpx.AsyncClient,
    store: MemoryStore,
    user_id: str,
    client_id: str,
    client_secret: str,
) -> dict[str, str]:
    """そのユーザーの全スペースを refresh し、domain → access_token を返す。

    Args:
        http: 差し込まれた HTTP クライアント。
        store: 接続表。成功時は refresh を更新する。
        user_id: Chat 上のユーザー ID。
        client_id: OAuth アプリ。
        client_secret: 同上。

    Returns:
        成功したスペースだけの dict。失敗したスペースは載せない。
    """
    tokens: dict[str, str] = {}
    for connection in store.list_connections(user_id):
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
            continue
        if refresh != connection.refresh_token:
            store.put_connection(
                Connection(
                    user_id=connection.user_id,
                    org_id=connection.org_id,
                    domain=connection.domain,
                    refresh_token=refresh,
                )
            )
        tokens[connection.domain] = access
    return tokens
