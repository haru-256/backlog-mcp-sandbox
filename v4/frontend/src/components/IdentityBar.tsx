/**
 * IdentityBar の入力。
 *
 * @property userId - 表示中のユーザー ID
 * @property orgId - 表示中のテナント ID
 * @property onUserId - user_id 変更時
 * @property onOrgId - org_id 変更時
 */
type Props = {
  userId: string;
  orgId: string;
  onUserId: (value: string) => void;
  onOrgId: (value: string) => void;
};

/**
 * デモ用の user_id / org_id 入力と、Backlog 接続リンクを出す。
 *
 * @param props - 現在の身元と変更ハンドラ
 * @returns identity セクションの React 要素
 */
export function IdentityBar({ userId, orgId, onUserId, onOrgId }: Props) {
  const apiBase = import.meta.env.VITE_API_BASE_URL;
  const canConnect = userId.trim().length > 0 && orgId.trim().length > 0;
  const connectHref = canConnect
    ? `${apiBase}/backlog/connect?user_id=${encodeURIComponent(userId.trim())}&org_id=${encodeURIComponent(orgId.trim())}`
    : undefined;

  return (
    <section>
      <h2>identity</h2>
      <p>デモ用。本格ログインはない。Chat テナントは org。Backlog スペースは 1 ユーザー 1 本。再接続すると上書きする。</p>
      <p>
        <label>
          user_id{" "}
          <input value={userId} onChange={(event) => onUserId(event.target.value)} />
        </label>{" "}
        <label>
          org_id{" "}
          <input value={orgId} onChange={(event) => onOrgId(event.target.value)} />
        </label>
      </p>
      <p>
        {connectHref ? (
          <a href={connectHref}>Backlog を接続（既存があれば上書き）</a>
        ) : (
          <span>user_id と org_id を入れてから接続できます。</span>
        )}
      </p>
    </section>
  );
}
