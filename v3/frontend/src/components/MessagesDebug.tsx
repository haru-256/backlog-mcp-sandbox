import type { ChatMessage } from "../types";

/**
 * MessagesDebug の入力。
 *
 * @property messages - tool 行を含む全履歴
 */
type Props = {
  messages: ChatMessage[];
};

/**
 * 全 messages を JSON で折りたたみ表示する。
 *
 * @param props - 会話履歴
 * @returns details 要素
 */
export function MessagesDebug({ messages }: Props) {
  return (
    <details>
      <summary>messages JSON（tool 行を含む全履歴）</summary>
      <pre>{JSON.stringify(messages, null, 2)}</pre>
    </details>
  );
}
