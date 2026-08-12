import type { ChatMessage } from "../types";

type Props = {
  messages: ChatMessage[];
};

function visibleText(message: ChatMessage): string | null {
  if (message.role === "user") {
    return message.content;
  }
  if (message.role === "assistant" && message.content) {
    return message.content;
  }
  return null;
}

export function MessageList({ messages }: Props) {
  const visible = messages.flatMap((message, index) => {
    const text = visibleText(message);
    if (text === null) {
      return [];
    }
    return [{ index, role: message.role, text }];
  });

  if (visible.length === 0) {
    return <p>まだ発言がありません。</p>;
  }

  return (
    <ol>
      {visible.map((item) => (
        <li key={`${item.role}-${item.index}`}>
          <strong>{item.role}</strong>
          <pre style={{ whiteSpace: "pre-wrap" }}>{item.text}</pre>
        </li>
      ))}
    </ol>
  );
}
