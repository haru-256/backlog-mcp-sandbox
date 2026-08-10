import { ChatComposer } from "./components/ChatComposer";
import { HealthStatus } from "./components/HealthStatus";
import { MessageList } from "./components/MessageList";
import { MessagesDebug } from "./components/MessagesDebug";
import { useChat } from "./hooks/useChat";

export default function App() {
  const { messages, pending, error, send, clear } = useChat();

  return (
    <main>
      <h1>Backlog MCP Chat (v1)</h1>
      <p>サーバーは履歴を持たない。次の発言には全 messages を送り返す。</p>

      <HealthStatus />

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
