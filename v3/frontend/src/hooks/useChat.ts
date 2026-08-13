import { useCallback, useState } from "react";

import { postChat } from "../api";
import type { ChatMessage } from "../types";

/**
 * 未知の失敗を画面表示用の文字列にする。
 *
 * @param error - catch した値
 * @returns Error なら message。それ以外は固定の日本語メッセージ
 */
function errorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "不明なエラーが発生しました";
}

/**
 * クライアント側で会話履歴を持ち、Chat API に全件を送り直す。API 失敗は error 文字列に載せる。
 *
 * @param userId - Chat 上のユーザー ID
 * @param orgId - Chat テナント ID
 * @returns messages / pending / error と、send / clear
 */
export function useChat(userId: string, orgId: string) {
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
        const next: ChatMessage[] = [...messages, { role: "user", content: trimmed }];
        const response = await postChat(next, userId.trim(), orgId.trim());
        setMessages(response.messages);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setPending(false);
      }
    },
    [messages, pending, userId, orgId],
  );

  const clear = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  return { messages, pending, error, send, clear };
}
