# backlog-mcp

Chat API 向けの自作 Backlog MCP **Server**。Host は `v3/backend`。

接続はチャット外の OAuth。tool は `list_connected_spaces` と `list_issues` の二つ。

## 入口

| パス | 誰が呼ぶか | 認証 |
|---|---|---|
| `/mcp` | Host の MCP Client | Bearer JWT（`typ=mcp`） |
| `/connect` | ブラウザ（接続ボタン） | query の JWT（`typ=connect`） |
| `/callback` | Backlog からの 302 | OAuth の `state` |
| `/health` | Compose | なし |

## ファイル（読む順）

| ファイル | 役割 |
|---|---|
| `server.py` | 配線。tool 登録と起動 |
| `store.py` | OAuth アプリ / 接続 / 認可途中の三表 |
| `connect.py` | `/connect` と `/callback` |
| `auth.py` | `/mcp` の JWT |
| `tools.py` | スペース解決と課題一覧 |
| `backlog.py` | Backlog REST |
| `space.py` | スペース名の正規化 |
| `jwt_tokens.py` | `connect` / `mcp` 共通の検証 |
| `settings.py` | 環境変数 |

永続化はメモリのみ。再起動で接続は消える。
