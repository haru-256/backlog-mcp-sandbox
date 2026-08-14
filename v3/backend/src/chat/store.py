"""Host がメモリに持つ二つの表。再起動で消える。

Host は connections に (user_id, domain) → Backlog token を持つ。
OAuth アプリ（client_id / secret）は Settings が環境変数から読む。ここには置かない。

+------------------+----------------------------------+
| 表               | キー → 値                        |
+------------------+----------------------------------+
| connections      | (user_id, domain) →              |
|                  | その人が同意した Backlog token   |
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
        org_id: Chat テナント ID。JWT の `org`。
        domain: 接続したスペースのホスト名。
        access_token: その人が同意した Backlog token。
        refresh_token: 更新用。無いときは None。
    """

    user_id: str
    org_id: str
    domain: str
    access_token: str
    refresh_token: str | None = None


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
        self.connections: dict[tuple[str, str], Connection] = {}
        self.pending: dict[str, PendingOAuth] = {}

    def put_connection(self, connection: Connection) -> None:
        """ユーザーとスペースの組に Backlog token を紐づける。

        Args:
            connection: 覚える接続。
        """
        self.connections[(connection.user_id, connection.domain)] = connection

    def list_connections(self, user_id: str) -> list[Connection]:
        """その Chat ユーザーが OAuth した接続だけを返す。他人の分は入らない。

        Args:
            user_id: Chat 上のユーザー ID。

        Returns:
            そのユーザーの Connection のリスト。無ければ空。
        """
        return [item for item in self.connections.values() if item.user_id == user_id]

    def get_connection(self, user_id: str, domain: str) -> Connection | None:
        """そのユーザーがそのスペースへ接続済みなら返す。

        Args:
            user_id: Chat 上のユーザー ID。
            domain: スペースのホスト名。

        Returns:
            接続済みなら Connection。未接続なら None。
        """
        return self.connections.get((user_id, domain))

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
