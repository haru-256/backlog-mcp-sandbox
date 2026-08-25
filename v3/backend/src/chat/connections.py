"""store を見て、どのスペースの token を渡すかを決める。Backlog HTTP は呼ばない。"""

from .space import resolve_space
from .store import Connection, MemoryStore

NOT_CONNECTED = "Backlog は未接続です。画面の接続ボタンから接続してください。"
NEED_SPACE = (
    "複数のスペースが接続されています。list_connected_spaces で確認し、space を指定してください。"
)
UNKNOWN_SPACE = "指定されたスペースはこのユーザーの接続にありません。"
REFRESH_FAILED = (
    "このスペースの再認証に失敗しました。画面の接続ボタンから接続し直してください。"
)


def connected_spaces(store: MemoryStore, user_id: str) -> list[dict[str, str]]:
    """そのユーザーが OAuth したスペースの一覧。

    Args:
        store: 接続表。
        user_id: Chat 上のユーザー ID。

    Returns:
        `domain` と `org_id` の dict のリスト。
    """
    return [
        {"domain": item.domain, "org_id": item.org_id} for item in store.list_connections(user_id)
    ]


def resolve_connection(store: MemoryStore, user_id: str, space: str | None) -> Connection | str:
    """接続一覧からスペースを一つ決め、その Connection を返す。

    Args:
        store: 接続表。
        user_id: Chat 上のユーザー ID。
        space: スペースのホスト名。1 本だけ接続していれば省略できる。

    Returns:
        成功時は Connection。失敗時は NOT_CONNECTED / NEED_SPACE / UNKNOWN_SPACE。
    """
    connected = [item.domain for item in store.list_connections(user_id)]
    if not connected:
        return NOT_CONNECTED
    try:
        domain = resolve_space(connected, space)
    except ValueError:
        return UNKNOWN_SPACE
    if domain is None:
        if space:
            return UNKNOWN_SPACE
        return NEED_SPACE
    connection = store.get_connection(user_id, domain)
    if connection is None:
        return UNKNOWN_SPACE
    return connection
