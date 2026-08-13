import { useState, type FormEvent } from "react";

/**
 * ChatComposer の入力。
 *
 * @property pending - 送信中なら true。入力を無効化する
 * @property onSend - 送信する本文。空や送信中は呼び出し側が無視してよい
 * @property onClear - 会話履歴を捨てる
 * @property hasMessages - 履歴があるとき true。clear ボタンの活性に使う
 */
type Props = {
  pending: boolean;
  onSend: (content: string) => Promise<void>;
  onClear: () => void;
  hasMessages: boolean;
};

/**
 * メッセージ入力と送信 / clear。onSend の失敗は呼び出し側が扱う。
 *
 * @param props - 送信状態とハンドラ
 * @returns 入力フォームの React 要素
 */
export function ChatComposer({ pending, onSend, onClear, hasMessages }: Props) {
  const [draft, setDraft] = useState("");

  /**
   * フォーム送信を抑え、下書きを onSend に渡す。
   *
   * @param event - submit イベント
   * @throws onSend が送出した例外
   */
  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = draft;
    setDraft("");
    await onSend(content);
  }

  return (
    <form onSubmit={handleSubmit}>
      <label>
        message
        <br />
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          rows={3}
          cols={60}
          disabled={pending}
          placeholder="未完了課題を教えて"
        />
      </label>
      <br />
      <button type="submit" disabled={pending || draft.trim().length === 0}>
        {pending ? "sending…" : "send"}
      </button>{" "}
      <button type="button" onClick={onClear} disabled={pending || !hasMessages}>
        clear
      </button>
    </form>
  );
}
