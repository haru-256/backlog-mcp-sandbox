import { useEffect, useState } from "react";

const USER_KEY = "v3.user_id";
const ORG_KEY = "v3.org_id";

export type Identity = {
  userId: string;
  orgId: string;
};

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
