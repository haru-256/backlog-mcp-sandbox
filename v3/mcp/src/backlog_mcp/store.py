from dataclasses import dataclass


@dataclass
class SpaceApp:
    domain: str
    client_id: str
    client_secret: str


@dataclass
class Connection:
    user_id: str
    org_id: str
    domain: str
    access_token: str
    refresh_token: str | None = None


@dataclass
class PendingOAuth:
    user_id: str
    org_id: str
    domain: str


class MemoryStore:
    """スペースの OAuth アプリと、ユーザーごとの Backlog 接続をメモリに持つ。"""

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
        return [item for (uid, _), item in self.connections.items() if uid == user_id]

    def get_connection(self, user_id: str, domain: str) -> Connection | None:
        return self.connections.get((user_id, domain))

    def put_pending(self, state: str, pending: PendingOAuth) -> None:
        self.pending[state] = pending

    def pop_pending(self, state: str) -> PendingOAuth | None:
        return self.pending.pop(state, None)
