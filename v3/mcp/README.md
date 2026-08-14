# backlog-mcp

Chat API 向けの自作 Backlog MCP **Server**。Host は `v3/backend`。

接続と token は Host が持つ。MCP は渡された `space` と `access_token` で `list_issues` する。

## 入口

| パス | 誰が呼ぶか | 認証 |
|---|---|---|
| `/mcp` | Host の MCP Client | Bearer JWT（`typ=mcp`） |
| `/health` | Compose | なし |

## ファイル（読む順）

| ファイル | 役割 |
|---|---|
| `server.py` | 配線。tool 登録と起動 |
| `auth.py` | `/mcp` の JWT。呼び出し元が Host であることの証明 |
| `tools.py` | 渡された space と token で課題一覧 |
| `backlog.py` | Backlog REST |
| `jwt_tokens.py` | `typ=mcp` の検証 |
| `settings.py` | JWT と公開 URL |

MCP は接続を持たない。token は Host が tool 引数で渡す。
