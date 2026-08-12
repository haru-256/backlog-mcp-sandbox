/**
 * LLM の tool 呼び出し 1 件。
 *
 * @property id - tool_call_id。対応する tool 行と一致させる
 * @property type - 通常は "function"
 * @property function.name - tool 名
 * @property function.arguments - JSON 文字列の引数
 */
export type ToolCall = {
  id: string;
  type: string;
  function: {
    name: string;
    arguments: string;
  };
};

/**
 * ユーザー発話。
 *
 * @property role - 常に "user"
 * @property content - 本文
 */
export type UserMessage = {
  role: "user";
  content: string;
};

/**
 * assistant の 1 行。
 *
 * @property role - 常に "assistant"
 * @property content - 最終回答の本文。tool 要求中は null になり得る
 * @property tool_calls - LLM が要求した tool。無いこともある
 */
export type AssistantMessage = {
  role: "assistant";
  content?: string | null;
  tool_calls?: ToolCall[];
};

/**
 * tool 実行結果の 1 行。
 *
 * @property role - 常に "tool"
 * @property tool_call_id - 対応する assistant.tool_calls[].id
 * @property content - tool の戻り文字列
 */
export type ToolMessage = {
  role: "tool";
  tool_call_id: string;
  content: string;
};

/** Chat API がやり取りする 1 行。 */
export type ChatMessage = UserMessage | AssistantMessage | ToolMessage;

/**
 * POST /chat の応答。
 *
 * @property message - 末尾の assistant 行
 * @property messages - tool 行を含む全履歴
 */
export type ChatResponse = {
  message: ChatMessage;
  messages: ChatMessage[];
};

/**
 * GET /health の応答。
 *
 * @property ok - プロセスが応答できるとき true
 */
export type HealthResponse = {
  ok: boolean;
};
