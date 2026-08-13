"""自作 Backlog MCP Server。

このパッケージは MCP の **Server** である。Chat の Host は `v3/backend`、
検証 UI は `v3/frontend`。LLM はここを直接呼ばない。

読む順:

1. `server.py` — 入口が `/mcp`（tool）と `/connect`（ブラウザ）の二つであること
2. `store.py` — 覚える表が三つ（OAuth アプリ / 接続 / 認可途中）
3. `connect.py` — チャット外の OAuth
4. `tools.py` — JWT のユーザーからスペースを決めて課題を返す
"""

from .server import run


def main() -> None:
    """環境変数から設定を読み、Streamable HTTP で起動する。"""
    run()
