"""Host がメモリに持つ二つの表。再起動で消える。

Host は connections に user_id → refresh token を持つ。1 ユーザー 1 スペース。
OAuth アプリ（client_id / secret）は Settings が環境変数から読む。ここには置かない。

+------------------+----------------------------------+
| 表               | キー → 値                        |
+------------------+----------------------------------+
| connections      | user_id → その人が同意した       |
|                  | refresh token（1 本。上書き）    |
| pending          | Backlog に渡した state →         |
|                  | 認可が戻ってくるまでの仮データ   |
+------------------+----------------------------------+
"""

from dataclasses import dataclass


@dataclass
class Connection:
    """Chat ユーザーが、あるスペースへ OAuth したあとの接続。

    Attributes:
        user_id: Chat 上のユーザー ID。
        org_id: Chat テナント ID。
        domain: 接続したスペースのホスト名。
        refresh_token: access token を取り直すための token。
    """

    user_id: str
    org_id: str
    domain: str
    refresh_token: str


@dataclass
class PendingOAuth:
    """Backlog の同意画面に飛ばしている途中。callback で connections に変わる。

    Attributes:
        user_id: 接続を始めた Chat ユーザー。
        org_id: Chat テナント。
        domain: 認可しようとしているスペース。
    """

    user_id: str
    org_id: str
    domain: str


class MemoryStore:
    """上の二表を dict で持つ。永続化はしない。"""

    def __init__(self) -> None:
        """空の二表で始める。"""
        self.connections: dict[str, Connection] = {}
        self.pending: dict[str, PendingOAuth] = {}

    def put_connection(self, connection: Connection) -> None:
        """ユーザーに Backlog token を紐づける。同じユーザーの旧行は置き換える。

        Args:
            connection: 覚える接続。
        """
        self.connections[connection.user_id] = connection

    def get_connection(self, user_id: str) -> Connection | None:
        """そのユーザーの接続を返す。

        Args:
            user_id: Chat 上のユーザー ID。

        Returns:
            接続済みなら Connection。未接続なら None。
        """
        return self.connections.get(user_id)

    def put_pending(self, state: str, pending: PendingOAuth) -> None:
        """Backlog に渡す state と、誰がどのスペースを認可中かを覚える。

        Args:
            state: 認可 URL の state。callback で戻ってくる。
            pending: 認可が終わるまでの仮データ。
        """
        self.pending[state] = pending

    def pop_pending(self, state: str) -> PendingOAuth | None:
        """callback の state に対応する仮データを取り出し、表から消す。

        Args:
            state: Backlog が返した state。

        Returns:
            覚えていた PendingOAuth。未知の state なら None。
        """
        return self.pending.pop(state, None)
