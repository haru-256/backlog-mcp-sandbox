"""MCP がメモリに持つ三つの表。再起動で消える。

Host は Backlog の token を持たない。置き場はこのプロセスだけである。

+------------------+----------------------------------+
| 表               | キー → 値                        |
+------------------+----------------------------------+
| space_apps       | スペース → OAuth アプリ          |
|                  | （client_id / secret。スペースに |
|                  |  つき一度）                      |
| connections      | (Chat ユーザー, スペース) →      |
|                  | その人が同意した Backlog token   |
| pending          | Backlog に渡した state →         |
|                  | 認可が戻ってくるまでの仮データ   |
+------------------+----------------------------------+
"""

from dataclasses import dataclass


@dataclass
class SpaceApp:
    """ある Backlog スペースに登録された OAuth アプリ。"""

    domain: str
    client_id: str
    client_secret: str


@dataclass
class Connection:
    """Chat ユーザーが、あるスペースへ OAuth したあとの接続。"""

    user_id: str
    org_id: str
    domain: str
    access_token: str
    refresh_token: str | None = None


@dataclass
class PendingOAuth:
    """Backlog の同意画面に飛ばしている途中。callback で connections に変わる。"""

    user_id: str
    org_id: str
    domain: str


class MemoryStore:
    """上の三表を dict で持つ。永続化はしない。"""

    def __init__(self) -> None:
        self.space_apps: dict[str, SpaceApp] = {}
        self.connections: dict[tuple[str, str], Connection] = {}
        self.pending: dict[str, PendingOAuth] = {}

    def get_space_app(self, domain: str) -> SpaceApp | None:
        return self.space_apps.get(domain)

    def put_space_app(self, app: SpaceApp) -> None:
        self.space_apps[app.domain] = app

    def put_connection(self, connection: Connection) -> None:
        self.connections[(connection.user_id, connection.domain)] = connection

    def list_connections(self, user_id: str) -> list[Connection]:
        return [item for item in self.connections.values() if item.user_id == user_id]

    def get_connection(self, user_id: str, domain: str) -> Connection | None:
        return self.connections.get((user_id, domain))

    def put_pending(self, state: str, pending: PendingOAuth) -> None:
        self.pending[state] = pending

    def pop_pending(self, state: str) -> PendingOAuth | None:
        return self.pending.pop(state, None)
