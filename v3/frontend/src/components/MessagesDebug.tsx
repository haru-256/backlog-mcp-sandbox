import type { ChatMessage } from "../types";

type Props = {
  messages: ChatMessage[];
};

export function MessagesDebug({ messages }: Props) {
  return (
    <details>
      <summary>messages JSON（tool 行を含む全履歴）</summary>
      <pre>{JSON.stringify(messages, null, 2)}</pre>
    </details>
  );
}
