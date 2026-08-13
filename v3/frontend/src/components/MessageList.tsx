import type { ChatMessage } from "../types";

/**
 * MessageList の入力。
 *
 * @property messages - tool 行を含む全履歴
 */
type Props = {
  messages: ChatMessage[];
};

/**
 * 画面に出す本文だけを取り出す。tool 行は出さない。
 *
 * @param message - 1 行
 * @returns user の本文、または assistant の本文。それ以外は null
 */
function visibleText(message: ChatMessage): string | null {
  if (message.role === "user") {
    return message.content;
  }
  if (message.role === "assistant" && message.content) {
    return message.content;
  }
  return null;
}

/**
 * user / assistant の本文だけを並べる。
 *
 * @param props - 会話履歴
 * @returns 一覧、または空のときの案内
 */
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
