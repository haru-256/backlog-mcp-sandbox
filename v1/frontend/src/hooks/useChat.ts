import { useCallback, useState } from "react";

import { postChat } from "../api";
import type { ChatMessage } from "../types";

function errorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "不明なエラーが発生しました";
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const send = useCallback(
    async (content: string) => {
      const trimmed = content.trim();
      if (!trimmed || pending) {
        return;
      }

      setPending(true);
      setError(null);

      try {
        // クライアントが全履歴を保持し、次の発言に足して送る（v1 はサーバー側セッションなし）
        const next: ChatMessage[] = [...messages, { role: "user", content: trimmed }];
        const response = await postChat(next);
        setMessages(response.messages);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setPending(false);
      }
    },
    [messages, pending],
  );

  const clear = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  return { messages, pending, error, send, clear };
}
