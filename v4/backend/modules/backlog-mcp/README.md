# backlog-mcp

Chat API 向けの自作 Backlog MCP **Server**。Host は `v4/backend` が同一プロセスで `Client(server)` する。

接続と token は Host が持つ。MCP は渡された `space` と `access_token` で `list_issues` する。
HTTP の `/mcp` は持たない。

## ファイル（読む順）

| ファイル | 役割 |
|---|---|
| `server.py` | `create_server`。tool 登録 |
| `tools.py` | 渡された space と token で課題一覧 |
| `backlog.py` | Backlog REST |
| `settings.py` | 件数上限 |
