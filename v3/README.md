# v3: 自作 Backlog MCP

v1 は公式の Backlog MCP を **外から使う** 教材だった。v3 は同じ Chat から、**MCP サーバー側を自分たちで書く** 教材である。

目的は Backlog 製品を完成させることではない。次の問いに、コードで答えられるようにすることである。

- MCP の Host / Client / Server は、どのプロセスのどのファイルか
- LLM は Backlog API を直接呼ばない。なぜ tool を経由するのか
- 「接続」と「チャット」は、なぜ別の流れなのか
- Host がユーザーとスペースの組で token を持つとき、MCP には何を渡すのか

---

## MCP を三つの役割で見る

[Model Context Protocol (MCP)](https://modelcontextprotocol.io/) は、LLM アプリが外部ツールを呼ぶときの約束事である。HTTP の「クライアントとサーバー」に加え、**Host** という第三の役割がある。

| 役割 | このリポジトリでの実体 | 仕事 |
|---|---|---|
| **Host** | `backend/`（Chat API） | ユーザー発話を受け、LLM と MCP Client を回す。tool をいつ呼ぶかは LLM が決める |
| **Client** | `backend` 内の MCP SDK | Host の一部。MCP Server に `tools/list` と `tools/call` を送る |
| **Server** | `mcp/` | tool の定義と実行。ここでは Backlog の課題一覧 |

関係は次のとおりである。矢印の向きが「誰が誰を呼ぶか」である。

```mermaid
flowchart LR
  User[User]
  FE[frontend]
  Host[Host_Chat_API]
  LLM[LLM]
  Client[MCP_Client]
  Server[MCP_Server]
  Backlog[Backlog_API]

  User --> FE
  FE --> Host
  Host --> LLM
  Host --> Client
  Client --> Server
  Server --> Backlog
```

押さえる点は三つある。

1. **LLM は MCP を知らない。** Host が tool schema を OpenAI 形式に直し、LLM に渡す。
2. **LLM は Backlog を知らない。** 「課題を取れ」と tool 名を返すだけである。実行するのは Server。
3. **Server は会話を持たない。** チャットの履歴は Host（と検証 UI）側にある。

v1 では Server が公式コンテナだった。v3 では `mcp/` がその位置を占める。Host の loop の形は v1 と同じである。

---

## v3 が公式 MCP と違うところ

公式 Backlog MCP の OAuth は、**1 サーバー = 1 組織** である。複数スペースを API キーで載せる機能はあるが、OAuth とは両立しない。これは公式 MCP サーバーの実装制約である。Backlog の OAuth アプリ自体は 1 組で複数スペースの認可に使える。

v3 の Server は次を同時に持つ。

- Chat のテナント（`org_id`）は Host が知る。ユーザーと org は 1:1
- スペースと token は Host が知る。MCP は渡された space と token で API を叩く。1 ユーザーが複数スペースを接続できる
- 接続はチャットの外のボタンで明示的に行う。tool 結果から OAuth URL は出さない

Cursor からこの MCP につなぐ想定はない。クライアントは自前の Chat Host だけである。

---

## プロセスとディレクトリ

```text
v3/
  compose.yaml     mcp と api を常駐させる
  mcp/             MCP Server（tools のみ）
  backend/         MCP Host（Chat API + OAuth + token store）
  frontend/        検証 UI（身元入力 + 接続ボタン + チャット）
```

Compose 上のポートは次である。

| プロセス | ポート | 主なパス |
|---|---|---|
| MCP Server | 3333 | `/mcp`（tool）、`/health` |
| Chat Host | 8003 | `/chat`、`/backlog/connect`、`/backlog/callback`、`/health` |
| 検証 UI | 5173 | ブラウザ。Compose には載せない |

`/mcp` は Streamable HTTP である。Host が MCP を子プロセス（stdio）で都度起動しない。v1 と同じ判断である。

---

## コードの地図

読む順番は、役割の境界から中へ入るとよい。

```mermaid
flowchart TB
  subgraph fe [frontend]
    App[App.tsx]
    Identity[IdentityBar.tsx]
    ChatHook[useChat.ts]
  end

  subgraph host [backend]
    Api[api.py]
    Agent[agent.py]
    JwtHost[jwt_tokens.py]
    McpClient[mcp_client.py]
    Llm[llm.py]
    Connect[connect.py]
    Store[store.py]
  end

  subgraph server [mcp]
    Srv[server.py]
    Auth[auth.py]
    Tools[tools.py]
    BacklogMod[backlog.py]
  end

  App --> Identity
  App --> ChatHook
  Identity -->|"GET /backlog/connect"| Api
  ChatHook -->|"POST /chat"| Api
  Api --> Agent
  Agent --> JwtHost
  Agent --> McpClient
  Agent --> Llm
  McpClient -->|"Bearer JWT /mcp"| Srv
  Api --> Connect
  Connect --> Store
  McpClient --> Store
  Srv --> Auth
  Srv --> Tools
  Tools --> BacklogMod
```

| ファイル | 役割 |
|---|---|
| [frontend/src/components/IdentityBar.tsx](frontend/src/components/IdentityBar.tsx) | 「Backlog を接続」リンク。チャット API は呼ばない |
| [backend/src/chat/api.py](backend/src/chat/api.py) | HTTP の入口。接続フォームとチャット |
| [backend/src/chat/connect.py](backend/src/chat/connect.py) | `/backlog/connect` と `/backlog/callback`。チャット外の OAuth |
| [backend/src/chat/store.py](backend/src/chat/store.py) | 接続と認可途中の二表。token の置き場 |
| [backend/src/chat/agent.py](backend/src/chat/agent.py) | LLM ↔ tool loop。MCP セッションを開く |
| [backend/src/chat/mcp_client.py](backend/src/chat/mcp_client.py) | schema から token を隠し、store の token を注入する |
| [mcp/src/backlog_mcp/server.py](mcp/src/backlog_mcp/server.py) | 配線。`/mcp` の tool と `/health` |
| [mcp/src/backlog_mcp/tools.py](mcp/src/backlog_mcp/tools.py) | 渡された space と token で課題一覧 |

スペースと token は Host が持つ。MCP は渡された `space` と `access_token` で Backlog API を叩く。

---

## 流れ 1: 明示接続（チャットの外）

OAuth は「課題を教えて」の途中では始まらない。ユーザーが接続ボタンを押したときだけ始まる。

```mermaid
sequenceDiagram
  participant User
  participant FE as frontend
  participant Host as backend_api
  participant Backlog

  User->>FE: Backlog を接続
  FE->>Host: GET /backlog/connect?user_id&org_id
  User->>Host: スペースを入力
  Host->>Backlog: 302 OAuth2AccessRequest
  User->>Backlog: 同意
  Backlog->>Host: GET /backlog/callback?code
  Host->>Backlog: code を token に交換
  Host->>Host: connections に user と space を保存
  Host->>FE: 302 ?connected=1
```

接続フォームは Host 上にある。ブラウザが MCP へ身元を証明する必要は無い。接続用の JWT は発行しない。

Host が覚える表は接続だけである。メモリであり、再起動で消える。

- `connections` — `(user_id, domain) → Backlog access token`（ユーザーとスペースの組）

OAuth アプリは Host に 1 組である。`BACKLOG_CLIENT_ID` と `BACKLOG_CLIENT_SECRET` を環境変数から読む。Redirect URI は `{HOST_PUBLIC_URL}/backlog/callback` で、ローカル既定は `http://localhost:8003/backlog/callback` である。Backlog Developer サイトのアプリにこの URI を登録する。

2 本目のスペースも、同じボタンから同じ `/backlog/connect` に入る。チャットの tool には `connect` を置いていない。

---

## 流れ 2: チャットと tool loop

接続が済んだあと、「未完了課題を教えて」は次の loop になる。v1 の Host と同じ形である。

```mermaid
sequenceDiagram
  participant User
  participant FE as frontend
  participant Host as agent.py
  participant LLM
  participant Client as mcp_client.py
  participant MCP as mcp_server
  participant Backlog

  User->>FE: 未完了課題を教えて
  FE->>Host: POST /chat messages user_id org_id
  Host->>Host: typ=mcp の JWT を署名
  Host->>MCP: Streamable HTTP /mcp Bearer
  Host->>MCP: tools/list
  MCP-->>Host: list_issues
  Host->>Host: list_connected_spaces を schema に足す
  Host->>LLM: messages と tool schemas
  LLM-->>Host: tool_call list_issues
  Host->>Host: store から space と token を決める
  Host->>MCP: tools/call list_issues with space and token
  MCP->>Backlog: GET /api/v2/issues
  Backlog-->>MCP: issues
  MCP-->>Host: JSON 文字列
  Host->>LLM: tool 結果を messages に足す
  LLM-->>Host: 最終テキスト
  Host-->>FE: assistant 行
```

loop の不変条件は [backend/src/chat/agent.py](backend/src/chat/agent.py) の `run_tool_loop` にある。

- LLM が返した assistant 行は、tool を実行する **前に** messages へ足す
- tool 行の `tool_call_id` は、対応する `assistant.tool_calls[i].id` と一致する
- tool_calls が無ければ終了する

LLM から見える tool は二つである。実装の場所が違う。

| tool | 実装 | すること |
|---|---|---|
| `list_connected_spaces` | Host | そのユーザーが OAuth したスペースを返す |
| `list_issues` | MCP | 渡された `space` と `access_token` で課題を返す |

未接続の判定は Host がする。未接続なら「接続ボタンから」と返し、MCP は呼ばない（URL は付けない）。`list_issues` の `space` は、Chat の org ではない。そのユーザーが接続済みの Backlog ドメインである。接続が 1 本なら省略できる。2 本以上なら必須である。他人のスペースは拒否する。

---

## 認証が二重になっている理由

初学者が混同しやすいので、層を分ける。

```text
ブラウザ  --フォーム-->  Host /backlog/connect  --Backlog OAuth-->  そのスペースの token
Host     --mcp JWT + tool引数(space, token)-->  MCP /mcp  --渡された token-->  Backlog API
```

- **mcp JWT**: `/mcp` の呼び出し元が Host であることの証明。ユーザーの token を引くキーではない
- **Backlog token**: ユーザーが同意したあとの API トークン。Host の `connections` にある。MCP へは tool 引数で渡す

Host と MCP は同じ `MCP_JWT_SECRET` を持つ。これは自前 Host だけがクライアントだからである。Cursor 向けの Dynamic Client Registration は実装していない。

---

## 起動

秘密情報はリポジトリ直下の `.envrc` を direnv で読む。`OPENCODE_GO_API_KEY` が Host の LLM に必要である。Host には `BACKLOG_CLIENT_ID` と `BACKLOG_CLIENT_SECRET` が必要である。Backlog アプリの Redirect URI は `http://localhost:8003/backlog/callback` にすること。

```bash
cd v3 && docker compose up
cd v3/frontend && pnpm install && pnpm dev
```

1. ブラウザで検証 UI を開く（既定は `http://localhost:5173`）
2. `user_id` と `org_id` を入れる（デモ用。本格ログインではない）
3. 「Backlog を接続」からスペースを追加する
4. 「未完了課題を教えて」と送る

テストは Live Backlog を叩かない。

```bash
cd v3/mcp && uv run pytest
cd v3/backend && uv run pytest
```

---

## 次に読むとよい順

1. [backend/src/chat/agent.py](backend/src/chat/agent.py) — Host の loop。MCP を知らなくても「LLM が tool を要求する」形が見える
2. [backend/src/chat/mcp_client.py](backend/src/chat/mcp_client.py) — MCP の tool schema を LLM 向けに変換する薄い層
3. [mcp/src/backlog_mcp/server.py](mcp/src/backlog_mcp/server.py) — 入口が `/mcp` と `/health` であること
4. [backend/src/chat/store.py](backend/src/chat/store.py) — ユーザー token の置き場。OAuth アプリは Settings
5. [backend/src/chat/connect.py](backend/src/chat/connect.py) — チャットと切り離した OAuth
6. [mcp/src/backlog_mcp/tools.py](mcp/src/backlog_mcp/tools.py) — 渡された space と token で課題を返す

リポジトリ全体の地図は [docs/guide/index.html](../docs/guide/index.html) にある。手順は [docs/guide/v3.html](../docs/guide/v3.html) にある。v1 の Host を先に読むと、v3 で増えたのが Server 側だと対比しやすい。
