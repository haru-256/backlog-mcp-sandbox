import axios from "axios";

import type { ChatMessage, ChatResponse, HealthResponse } from "./types";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

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

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>("/health");
  return data;
}
