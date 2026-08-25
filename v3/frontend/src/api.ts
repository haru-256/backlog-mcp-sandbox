import axios from "axios";

import type { ChatMessage, ChatResponse, HealthResponse } from "./types";

/** Chat Host 向けの HTTP クライアント。baseURL は VITE_API_BASE_URL。 */
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

/**
 * 会話履歴を Host の Chat API に送り、更新後の履歴を受け取る。
 *
 * @param messages - クライアントが保持する全会話履歴
 * @param userId - Chat 上のユーザー ID。MCP JWT の sub になる
 * @param orgId - Chat テナント ID。MCP JWT の org になる
 * @returns 末尾の assistant 行と、tool 行を含む全 messages
 * @throws {import("axios").AxiosError} HTTP エラー、またはネットワーク失敗
 */
export async function postChat(
  messages: ChatMessage[],
  userId: string,
  orgId: string,
): Promise<ChatResponse> {
  const { data } = await api.post<ChatResponse>("/chat", {
    messages,
    user_id: userId,
    org_id: orgId,
  });
  return data;
}

/**
 * Host のヘルスチェックを取得する。
 *
 * @returns `ok` が true ならプロセスが応答できている
 * @throws {import("axios").AxiosError} HTTP エラー、またはネットワーク失敗
 */
export async function getHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>("/health");
  return data;
}
