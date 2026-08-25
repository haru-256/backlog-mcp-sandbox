# Backlog MCP Sandbox

学習用サンドボックス。公式 Backlog MCP と自前 Host をつなぐ Chat API を、v1 → v2 で段階的に理解する。
v3 は同じ Host の形のまま、MCP Server 側を自分で書く。

## 学習ガイド

`docs/guide` を読む。共通の地図が原理を持ち、各版はその版の手順だけを持つ。
v1 のあと、v2（Host を厚くする）と v3（Server を書く）はどちらからでもよい。

1. [`docs/guide/index.html`](docs/guide/index.html) — 共通の地図。tool loop、Host / Client / Server、二種類のセッションとストリーム、MCP を HTTP で常駐させる理由
2. [`docs/guide/v1.html`](docs/guide/v1.html) — v1。ステートレス Host。tool loop を書き、FastAPI で包む
3. [`docs/guide/v2.html`](docs/guide/v2.html) — v2。セッション永続化、SSE、制限と失敗の契約、監査。v1 を前提とする
4. [`docs/guide/v3.html`](docs/guide/v3.html) — v3。自作 MCP Server。明示接続と複数スペース。v1 を前提とする

ガイドは、**学習対象になるコードを渡さない**。`run_tool_loop` と `stream_turn` は、
満たすべき不変条件と、自分で通せるテストだけを置いてある。
SDK の型を捌くだけの雑務コードは全文を渡す。

HTML なのは、mermaid の図と組版を伴う読み物として扱いたいためである。
ブラウザで開くときは `mise run guide` を使う（`file://` では共通アセットが読めない）。

## 参考資料

- [設計メモ](docs/superpowers/specs/2026-08-08-backlog-mcp-chat-design.md) — ブレインストーミング時の合意。ガイドと食い違ったらガイドが正
- [引き継ぎ資料](docs/handsoff/2026-08-07-backlog-mcp-chat.md) — 歴史資料。現行の設計に置き換わっている

## 起動

秘密情報はリポジトリ直下の `.envrc` を direnv で読み込む。値をコミットしない。

```bash
mise install          # node / pnpm / python / uv
cd v1 && docker compose up
```

### v3（自作 Backlog MCP）

公式 MCP は使わず、OAuth 接続と課題一覧を自前の MCP が持つ。Chat API は `8003`、MCP は `3333`。

役割分担とシーケンスは [v3/README.md](v3/README.md) と [docs/guide/v3.html](docs/guide/v3.html) にある。

```bash
cd v3 && docker compose up
cd v3/frontend && pnpm install && pnpm dev
```

検証 UI で `user_id` / `org_id` を入れ、「Backlog を接続」からスペースを追加してからチャットする。
