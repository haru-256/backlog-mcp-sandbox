import { useState, type FormEvent } from "react";

type Props = {
  pending: boolean;
  onSend: (content: string) => Promise<void>;
  onClear: () => void;
  hasMessages: boolean;
};

export function ChatComposer({ pending, onSend, onClear, hasMessages }: Props) {
  const [draft, setDraft] = useState("");

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
