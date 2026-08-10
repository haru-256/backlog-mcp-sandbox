export type ToolCall = {
  id: string;
  type: string;
  function: {
    name: string;
    arguments: string;
  };
};

export type UserMessage = {
  role: "user";
  content: string;
};

export type AssistantMessage = {
  role: "assistant";
  content?: string | null;
  tool_calls?: ToolCall[];
};

export type ToolMessage = {
  role: "tool";
  tool_call_id: string;
  content: string;
};

export type ChatMessage = UserMessage | AssistantMessage | ToolMessage;

export type ChatResponse = {
  message: ChatMessage;
  messages: ChatMessage[];
};

export type HealthResponse = {
  ok: boolean;
};
