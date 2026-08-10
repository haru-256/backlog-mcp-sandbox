# 引き継ぎ資料: Backlog MCP 連携 Chat API

> **これは歴史資料である。現行の設計ではない。**
> 本資料の後に合意が更新されており、内容の一部はすでに正しくない。
> 具体的には、v2 の簡易 API 認証は成功条件から外れ（差し込み点のみ）、
> Compose はリポジトリ直下の共通ファイルではなく各版直下に置く方式へ変わった。
> 現行の What は [設計メモ](../superpowers/specs/2026-08-08-backlog-mcp-chat-design.md)、
> How は [学習ガイド](../guide/index.html) にある。
> この資料は「なぜこの切り方になったか」の経緯を追うときだけ読む。

作成日: 2026-08-07  
リポジトリ: `backlog-mcp-sandbox`  
前セッションの状態: 要件ブレインストーミングまで完了。実装未着手。実装ガイド HTML（`docs/guide/v1.html`, `v2.html`）の作成を依頼されたが、本引き継ぎ作成へ切り替えられたため未作成。

この資料は、別エージェントが途中から作業を再開できるよう、合意事項と未完了作業を残すためのものである。
読み手が最初に押さえるべきなのは「何を作りたいか」ではなく「なぜこの切り方になったか」である。
実装の細部は後から決めてもよいが、目的を取り違えると v1 / v2 の境界がすぐに崩れる。

---

## 目的

このリポジトリで実現したいものは、フロントエンドを持たない **Chat API サーバー** である。
ユーザーが自然言語で Backlog の操作を依頼し、サーバー側が LLM と Backlog MCP を仲介して回答を返す。

典型的な依頼は次のようなものだ。

> Backlog の未完了課題を教えて

この一文の裏では、次の連鎖が起きなければならない。

1. Chat API（MCP Host）がユーザー発話を受け取る
2. Host が OpenCode Go（LLM）へ messages と tool schemas を渡す
3. LLM が tool call を返す
4. Host が MCP Client 経由で Backlog MCP Server の `tools/call` を実行する
5. Backlog MCP Server が Backlog API を呼び、結果を返す
6. Host が tool result を LLM に戻す
7. LLM が最終回答を返し、Host がユーザーへ返す

前セッションで共有された構成図は、次のとおりである。

```text
User → Chat Application / MCP Host
         ├─ Messages + Tool schemas → OpenCode Go (LLM)
         │                              └─ Tool Call → Host
         └─ MCP Client → tools/call → Backlog MCP Server → Backlog API
                              ↑              │
                              └─ Tool Result ┘
         Host → Tool Result → LLM → Final Answer → User
```

最終的に欲しいのは、デモ用の薄いスクリプトではない。
**本番稼働を意識した構成の Chat アプリ**であり、Backlog MCP 連携がその中核にある。

ただし「本番」という言葉は、ここで無制限に膨らませてはならない。
高度な cache は不要である。
インフラは Docker Compose だけでよい。
Kubernetes、サービスメッシュ、マルチリージョン、本格的なマルチテナント基盤は範囲外である。

本番を意識する、とは次を意味する。

- 公式の Backlog MCP Server を外付けサービスとして常駐させる
- Host が子プロセスとして MCP を都度起動する構成を避ける（stdio 依存の運用複雑さを避ける）
- MCP は HTTP（Streamable HTTP）でつなぐ
- 会話は最終的にサーバー側で保持し、PostgreSQL に永続化する
- timeout、tool 呼び出し回数上限、ヘルスチェック、構造化ログ、簡易 API 認証、書き込み tool の監査ログを備える

逆に言えば、これらが欠けたまま「セッション機能だけある Chat」を本番相当と呼ぶわけにはいかない。

---

## 背景

### なぜこのリポジトリが始まったか

リポジトリ名は `backlog-mcp-sandbox` である。
名前どおり、最初の動機は Backlog の MCP 接続を試すことにある。

しかし「試す」だけなら、Claude Desktop や Cursor に公式 MCP を足すだけで足りる。
実際、Nulab 公式の `nulab/backlog-mcp-server` は、その用途を主眼に公開されている。

それでも自前の Chat API を立てようとしている理由は、接続確認で終わりたくないからである。
ユーザー（このリポジトリの所有者）が欲しいのは、自分たちで Host を持ち、LLM 呼び出しと tool 実行の境界を自分たちのコードとして理解し、将来の本番アプリへ伸ばせる形である。

そのため、フロントエンドはいったん不要とされた。
最初に固めるべきは UI ではなく、Host の責任範囲である。

### MCP を自作しない、という判断

Backlog MCP Server をこのリポジトリで再実装する案もあった。
しかし公式があるなら公式を使う、という方針で合意した。

根拠は単純である。

- Nulab が `nulab/backlog-mcp-server` を公開している
- Docker イメージ（`ghcr.io/nulab/backlog-mcp-server`）と npx 起動がある
- 課題、Wiki、Git、通知など、Backlog 操作の tool 面をこちらで再発明する必要がない
- 本番寄りの責務分離では、Host と MCP Server を分けた方が自然である

注意点もある。
公式は MIT ライセンスであり、Nulab の製品サポート保証があるわけではない。
それでも「公式実装を外付けで使う」方が、自作 MCP より保守と追従の面で妥当だと判断した。

### stdio だけでは足りない、という懸念

議論の途中で、重要な疑念が出た。

公式は stdio だけなのか。
stdio だと Host がプロセス寿命を管理することになり、本番では複雑すぎないか。
本番では HTTP の方がよいのではないか。

調査の結果、公式は **デフォルトが stdio** だが、**HTTP（Streamable HTTP）もサポート**している。
`--transport http` または `MCP_TRANSPORT=http` で起動できる。

この事実で方針が固まった。
本番寄りの構成では、Backlog MCP を Compose 上の常駐サービスとし、Chat API から HTTP で接続する。
Host が MCP 子プロセスを管理する構成は採らない。

### LLM 側の前提

LLM には OpenCode Go の **DeepSeek V4 Flash**（`deepseek-v4-flash`）を使う。
これは OpenAI 互換の Chat Completions で呼べる。

- Endpoint: `https://opencode.ai/zen/go/v1/chat/completions`
- Model ID: `deepseek-v4-flash`
- Auth: Bearer API key

Python からは `openai` SDK の `base_url` 差し替えで呼ぶ想定である。
tool calling の実動作は実装時に確認する必要がある。
互換と書かれていても、個別モデルで tool の形が崩れることはあり得る。

### 「セッションがあれば本番」ではなかった

初期の整理では、次のように分けていた。

- v1: ステートレス（履歴はクライアントが毎回送る）
- v2: サーバー側セッション

これは学習順序としては悪くない。
しかし最終ゴールを「v2 = セッション追加」と置くと、本番相当に足りない。

足りないのはセッション機能そのものではなく、**プロダクトとして壊れにくい Host** である。

再定義後の整理は次のとおりである。

| ステップ | 位置づけ | 中身 |
|---|---|---|
| **v1** | 教材 | Host の中核（LLM ↔ tool loop ↔ MCP HTTP）。履歴はクライアント持ち。DB なし |
| **v2** | 最終成果物 | サーバー側セッション、PostgreSQL 永続化、timeout / max iterations、health、logging、簡易 API 認証、書き込み監査。任意で SSE |

v1 は本番トポロジ（Compose + HTTP MCP）を先に体験するための教材である。
v2 が、ユーザーが言う「本番稼働を意識した Chat アプリ」の本体である。

v3 は作らない。
hardening を別バージョンに逃がすと、最終形がどれか不明になる。

### なぜ v1 を残すか

最終形がマルチターンなら、最初から v2 だけ書けばよいのではないか。
その疑問は自然である。

それでも v1 を残す理由は、切り分けにある。

ステートレスな Host では、tool result が messages 配列のどこに入るかが最も見えやすい。
セッション実装のバグと、MCP / LLM ループのバグを同時に抱えない。
しかも Compose 上の MCP 常駐という本番トポロジは v1 から同じなので、あとで捨てる学習にはなりにくい。

コードは **v1 と v2 で共有しない**。
完全に独立した別アプリケーションとする。
学習のために差分を追いやすくするのが目的であり、共通ライブラリ化はしない。

### 書き込みを最初から許す理由

最初のマイルストーンで、Backlog への書き込み（課題作成・更新など）をどうするかも議論した。
結論は **読み書き両方を使う** である。

読み取り専用の方が安全ではある。
しかし最終ゴールが本番寄りの Chat である以上、書き込み系 tool を「後で足すもの」として過小評価したくない。
代わりに v2 で書き込みの監査ログを必須にし、誰のどのリクエストが何を書き込んだかを追えるようにする。

### 実装者について

実装はユーザー自身が行う想定だった。
そのため、前セッションでは `docs/guide/v1.html` と `docs/guide/v2.html` に実装ガイドを書く依頼が出ていた。

その後、別エージェントへの引き継ぎが優先され、本資料の作成に切り替わった。
ガイド HTML は **未作成** である。
次エージェントは、ユーザーの指示に応じてガイド作成または実装支援のどちらかへ進むことになる。

---

## 合意済みの決定事項（要約）

### プロダクト

- FastAPI による Chat API（フロントエンドなし）
- 公式 `nulab/backlog-mcp-server` を外付け利用（自作しない）
- MCP トランスポートは HTTP（Streamable HTTP）
- LLM は OpenCode Go の `deepseek-v4-flash`（OpenAI 互換）
- Backlog tool は読み書き両方
- 高度な cache は不要
- インフラは Docker Compose のみ

### 学習ロードマップと成果物

- `v1/`: ステートレス Chat Host（教材）。DB なし
- `v2/`: セッション付き Chat Host（最終成果物）。PostgreSQL + hardening
- `v1` と `v2` はコード共有なしの独立アプリ
- 推奨実装アプローチ: 手動エージェントループ（薄い Host）。LangChain 等は使わない

### 技術スタック

| 領域 | 選択 |
|---|---|
| 言語 | Python 3.12+ |
| パッケージ管理 | uv + `pyproject.toml`（v1 / v2 で独立） |
| Web | FastAPI + Uvicorn |
| 設定 | pydantic-settings |
| LLM | openai SDK（OpenCode Go 向けに base_url 差し替え） |
| MCP Client | 公式 `mcp` SDK（Streamable HTTP） |
| DB | PostgreSQL 16（**v2 のみ**） |
| ORM | SQLAlchemy 2.0（async + asyncpg） |
| マイグレーション | Alembic |
| ログ | 標準 logging（必要なら JSON 整形 / structlog） |
| 起動 | Docker Compose（`backlog-mcp`, `postgres`, `chat-v1`, `chat-v2`） |

Compose には最初から `postgres` を置いてよい。
ただし接続とマイグレーションは v2 だけが行う。
v1 が DB に依存すると教材の境界が濁る。

### リポジトリ構成（想定）

```text
backlog-mcp-sandbox/
├── docker-compose.yml
├── v1/                 # 独立アプリ（DB なし）
├── v2/                 # 独立アプリ（PostgreSQL）
├── docs/
│   ├── guide/          # 実装ガイド HTML（依頼済み・未作成）
│   │   ├── v1.html
│   │   └── v2.html
│   └── handsoff/       # 本資料
└── README.md
```

---

## v1 の成功条件

次を満たせば v1 は完成とみなしてよい。

1. `docker compose up` で `backlog-mcp` と `chat-v1` が起動する
2. `POST /chat`（名称は実装時に確定してよい）に messages を送ると、LLM が必要に応じて Backlog tool を呼び、最終回答を返す
3. 例: 「未完了課題を教えて」で実際に Backlog から取得した結果に基づく回答が返る
4. 履歴の永続化はしない。クライアントが毎回 messages を送る
5. DB を使わない

v1 に含めてよい本番寄りの要素:

- MCP を HTTP 常駐でつなぐこと
- Compose でサービスを並べること
- LLM / MCP 呼び出しの基本的なエラーを API レスポンスに載せること

v1 に含めないもの:

- セッション ID
- PostgreSQL
- API 認証（必須にはしない。付けてもよいが本命は v2）
- 監査ログテーブル
- SSE ストリーミング（任意。なくてもよい）

---

## v2 の成功条件

v2 は最終成果物である。
次を満たす必要がある。

1. サーバー側で会話セッションを作成・継続できる
2. メッセージ履歴を PostgreSQL に永続化する（SQLAlchemy + Alembic）
3. プロセス再起動後もセッションを再開できる
4. LLM / MCP に timeout を設ける
5. tool 呼び出し回数に上限を設ける
6. `/health`（または同等）で生死が分かる
7. 構造化ログで request / session を追える
8. Chat API に簡易認証（共有 API key 程度）がある
9. 書き込み系 tool 呼び出しを監査ログとして残す
10. `v1` とコードを共有しない

v2 に含めないもの:

- Redis 等の高度な cache
- Kubernetes
- 人間承認 UI（human-in-the-loop の承認画面）
- 本格的なマルチテナント / RBAC

---

## 実装アプローチ（推奨）

採用済みの方針は **手動エージェントループ（薄い Host）** である。

- FastAPI が MCP Host
- `openai` SDK で LLM を呼ぶ
- 公式 `mcp` Python SDK の Streamable HTTP Client で Backlog MCP に接続する
- `list_tools` → LLM → `tools/call` → 結果を messages に戻す、を自前で回す

却下した方針:

- LangGraph / LlamaIndex 等にループを任せる（Host の理解が隠れる）
- LLM / MCP を SDK なしで生 HTTP のみ叩く（壊れやすい）

MCP Client の参考（公式 Python SDK）:

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

async with streamable_http_client("http://backlog-mcp:3333/mcp") as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
```

Backlog MCP の HTTP 起動は、概ね次の環境変数で行う。

- `MCP_TRANSPORT=http`
- `MCP_HTTP_HOST=0.0.0.0`（コンテナ間通信する場合）
- `MCP_HTTP_PORT=3333`
- `MCP_HTTP_PATH=/mcp`
- `MCP_HTTP_ALLOWED_HOSTS=...`（`0.0.0.0` bind 時は設定を検討）
- `BACKLOG_DOMAIN=...`
- `BACKLOG_API_KEY=...`

公式 README では、HTTP を外部に晒す場合の認証と TLS が注意事項として書かれている。
Compose の内部ネットワークに閉じる前提が安全である。

---

## リポジトリの現状

調査時点の状態:

- Git リポジトリは存在するが、**コミットがまだない**（`main` に未コミット）
- 追跡対象になりうるファイル: `README.md`（見出しのみ）、`.gitignore`、`.envrc`
- `.envrc` に `OPENCODE_GO_API_KEY` と `BACKLOG_API_KEY` が入っている
- `.gitignore` は `.envrc` を無視する（direnv テンプレート由来）
- アプリケーションコード、Compose、docs/guide は未作成

### 秘密情報に関する注意

`.envrc` に実キーが入っている。
引き継ぎ資料やガイド、コミット、Issue、PR に **キーの値を書いてはならない**。
必要なら「env 名だけ」を案内する。

キーが会話ログやエージェント出力へ漏れた可能性がある場合は、ユーザーにローテーションを促すこと。

追加で必要になる想定の環境変数:

- `BACKLOG_DOMAIN`（例: `example.backlog.com`）
- `OPENCODE_GO_BASE_URL`（デフォルト `https://opencode.ai/zen/go/v1`）
- `OPENCODE_GO_MODEL`（デフォルト `deepseek-v4-flash`）
- `MCP_SERVER_URL`（例: `http://backlog-mcp:3333/mcp`）
- v2: `DATABASE_URL`, `CHAT_API_KEY`

---

## 未完了タスク

優先度はユーザー指示に従うこと。
前セッション末時点の候補は次のとおりである。

1. **実装ガイド HTML の作成**（ユーザー依頼済み・未着手）
   - `docs/guide/v1.html`
   - `docs/guide/v2.html`
   - ユーザー自身が実装するためのガイド
2. **設計の残りセクションの明文化**（ブレインストーミング途中で中断）
   - API スキーマ詳細
   - v2 データモデル（sessions / messages / tool_audit_logs など）
   - エラー処理とテスト方針
3. **`v1` 実装**（ユーザーが自分で行う想定だった）
4. **`v2` 実装**（v1 理解後）

ブレインストーミングの正規フローでは、設計承認後に `docs/superpowers/specs/` へ design doc を書き、`writing-plans` へ進む手順がある。
ただしユーザーは実装ガイド HTML と本引き継ぎを明示的に求めており、その指示が優先される。
コミットは、ユーザーが明示的に依頼するまで行わないこと。

---

## 次エージェントへの推奨手順

ユーザーの次メッセージに従うのが最優先である。
指示が「続きを進めて」程度に曖昧な場合の推奨順は次とする。

1. 本資料を読み、v1 / v2 の定義を崩していないか確認する
2. ユーザーがガイドを欲しがっているなら `docs/guide/v1.html` と `v2.html` を作成する
3. ユーザーが実装を欲しがっているなら、まず `v1` と `docker-compose.yml` から着手する
4. 設計の抜け（API 名・テーブル定義）は、実装前に短く確認してから進める

確認した方がよい未決定事項:

- Chat API のパス名（`POST /v1/chat` など）
- レスポンスを同期 JSON のみにするか、SSE を v2 で入れるか
- v2 のセッション ID の発行方法（UUID など）
- 監査ログに tool 引数全文を残すか、機微情報を赤くするか
- Backlog スペース（domain）の具体値（`.envrc` には API key のみ確認済み。domain は未確認）

---

## 前セッションの意思決定ログ（時系列）

1. ユーザーが Backlog MCP 連携の Chat API（FastAPI、フロントなし）をやりたいと説明
2. Backlog MCP Server は公式があれば使いたい、本番構成を意識したいと回答（選択肢 C → 公式利用を推奨し合意）
3. 公式の HTTP 対応を確認。stdio のみではない。HTTP 常駐を採用
4. OpenCode Go は DeepSeek V4 Flash。OpenAI 互換であることを確認
5. 会話は「まずステートレス、その後サーバーセッション」を学ぶ（C）
6. 書き込み系 tool も使う（B）
7. ディレクトリを `v1` / `v2` に分け、別アプリとして構築
8. コード共有なし（A）
9. Docker Compose で MCP と Chat API を並べる（A）
10. 実装方針は手動エージェントループ（案1）
11. クリティカルシンキングの結果、v2 を「セッション追加」から「最終成果物（永続化 + hardening）」へ再定義
12. 技術スタック合意。DB は PostgreSQL、ORM は SQLAlchemy、マイグレーションは Alembic
13. ユーザーが自分で実装するため guide HTML 作成を依頼
14. 別エージェント引き継ぎのため本資料作成へ切り替え

---

## 一言で言うと

このプロジェクトの本命は、公式 Backlog MCP を HTTP で常駐させ、FastAPI の薄い Host が OpenCode Go と tool loop でつなぐ Chat API を、Compose 上で本番寄りに育てることである。
v1 はそのループを理解するための独立教材、v2 が PostgreSQL 付きの最終成果物である。
