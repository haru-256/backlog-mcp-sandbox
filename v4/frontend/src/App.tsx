import { ChatComposer } from "./components/ChatComposer";
import { HealthStatus } from "./components/HealthStatus";
import { IdentityBar } from "./components/IdentityBar";
import { MessageList } from "./components/MessageList";
import { MessagesDebug } from "./components/MessagesDebug";
import { useChat } from "./hooks/useChat";
import { useIdentity } from "./hooks/useIdentity";

/**
 * v4 検証 UI。身元入力、Backlog 接続ボタン、ステートレスなチャットをまとめる。
 *
 * @returns ページ全体の React 要素
 */
export default function App() {
  const { userId, orgId, setUserId, setOrgId } = useIdentity();
  const { messages, pending, error, send, clear } = useChat(userId, orgId);
  const connected = new URLSearchParams(window.location.search).get("connected");

  return (
    <main>
      <h1>Backlog MCP Chat (v4)</h1>
      <p>
        サーバーは履歴を持たない。Backlog の接続は下のボタンから明示的に行う（チャット内では OAuth
        しない）。1 ユーザーは 1 スペース。もう一度接続すると上書きする。
      </p>

      {connected ? <p>Backlog スペースの接続が完了しました。</p> : null}

      <HealthStatus />
      <IdentityBar userId={userId} orgId={orgId} onUserId={setUserId} onOrgId={setOrgId} />

      <ChatComposer
        pending={pending}
        onSend={send}
        onClear={clear}
        hasMessages={messages.length > 0}
      />

      {error ? <p role="alert">error: {error}</p> : null}

      <h2>conversation</h2>
      <MessageList messages={messages} />

      <MessagesDebug messages={messages} />
    </main>
  );
}
