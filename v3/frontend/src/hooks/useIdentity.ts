import { useEffect, useState } from "react";

const USER_KEY = "v3.user_id";
const ORG_KEY = "v3.org_id";

/**
 * デモ用の Chat 身元。
 *
 * @property userId - Chat 上のユーザー ID
 * @property orgId - Chat テナント ID
 */
export type Identity = {
  userId: string;
  orgId: string;
};

/**
 * user_id / org_id を localStorage と同期する。本格ログインではない。
 * localStorage が使えない環境では setter 側が例外になり得る。
 *
 * @returns 現在の ID と setter。初回マウント前は空文字、その後 demo-user / demo-org または保存値
 */
export function useIdentity() {
  const [userId, setUserId] = useState("");
  const [orgId, setOrgId] = useState("");

  useEffect(() => {
    setUserId(localStorage.getItem(USER_KEY) ?? "demo-user");
    setOrgId(localStorage.getItem(ORG_KEY) ?? "demo-org");
  }, []);

  useEffect(() => {
    if (userId) {
      localStorage.setItem(USER_KEY, userId);
    }
  }, [userId]);

  useEffect(() => {
    if (orgId) {
      localStorage.setItem(ORG_KEY, orgId);
    }
  }, [orgId]);

  return { userId, orgId, setUserId, setOrgId };
}
